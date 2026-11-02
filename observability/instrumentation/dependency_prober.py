"""Read-only dependency probes. No Docker socket or Terraform state access."""
import asyncio
import contextlib
import os
import time

import psycopg
import redis.asyncio as redis
from redis.exceptions import RedisError
from aiohttp import web
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily

BUCKETS = (.05, .1, .25, .5, 1, 2.5, 5, 10, float("inf"))
COMMON = (os.getenv("PROJECT", "devops-grupo7"), os.getenv("ENVIRONMENT", "lab"))
LABELS = ("project", "environment", "dependency")
registry = CollectorRegistry()
success = Gauge("unal_dependency_probe_success", "Last basic probe result", LABELS, registry=registry)
duration = Histogram("unal_dependency_probe_duration_seconds", "Connection and basic query duration",
                     (*LABELS, "result"), buckets=BUCKETS, registry=registry)
probes = Counter("unal_dependency_probes_total", "Completed basic probes",
                 (*LABELS, "result"), registry=registry)
collection = Gauge("unal_dependency_collection_success", "Statistics collection succeeded",
                   LABELS, registry=registry)
last_probe = Gauge("unal_dependency_probe_timestamp_seconds", "Last completed probe timestamp",
                   LABELS, registry=registry)
# Before the first completed probe, success is intentionally absent.
for dependency in ("postgres", "redis"):
    for result in ("success", "failure"):
        probes.labels(*COMMON, dependency, result)
        duration.labels(*COMMON, dependency, result)
snapshots = {}


class Statistics:
    def collect(self):
        pg = snapshots.get("postgres")
        if pg is not None:
            counter = CounterMetricFamily("unal_postgres_transactions", "Database transactions",
                                          labels=["project", "environment", "outcome"])
            for outcome, value in (("commit", pg[0]), ("rollback", pg[1])):
                counter.add_metric([*COMMON, outcome], value)
            yield counter
            for name, help_text, value in (
                ("unal_postgres_connections", "Connections to the Chatwoot database", pg[2]),
                ("unal_postgres_max_connections", "Server connection limit", pg[3]),
            ):
                gauge = GaugeMetricFamily(name, help_text, labels=["project", "environment"])
                gauge.add_metric(list(COMMON), value)
                yield gauge
        value = snapshots.get("redis")
        if value is not None:
            counter = CounterMetricFamily("unal_redis_commands_processed", "Redis instance commands",
                                          labels=["project", "environment"])
            counter.add_metric(list(COMMON), value)
            yield counter


registry.register(Statistics())


async def postgres_probe():
    connection = await psycopg.AsyncConnection.connect(
        host=os.environ["PGHOST"], port=int(os.getenv("PGPORT", "5432")),
        dbname=os.environ["PGDATABASE"], user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"], autocommit=True,
        options="-c default_transaction_read_only=on -c statement_timeout=2000",
        application_name="unal-observability-prober",
    )
    try:
        cursor = await connection.execute("SELECT 1")
        assert (await cursor.fetchone())[0] == 1
    except BaseException:
        await connection.close()
        raise
    return connection


async def redis_probe():
    client = redis.Redis(host=os.environ["REDIS_HOST"], port=int(os.getenv("REDIS_PORT", "6379")),
                         password=os.environ["REDIS_PASSWORD"], socket_connect_timeout=2,
                         socket_timeout=2, decode_responses=True)
    try:
        assert await client.ping()
    except BaseException:
        await client.aclose()
        raise
    return client


async def sample(dependency):
    started = time.monotonic()
    client = None
    result = "failure"
    try:
        async with asyncio.timeout(2):
            client = await (postgres_probe() if dependency == "postgres" else redis_probe())
        result = "success"
    except (psycopg.Error, RedisError, OSError, TimeoutError):
        pass  # The result is exported; exception text may contain connection details.
    elapsed = time.monotonic() - started
    success.labels(*COMMON, dependency).set(result == "success")
    probes.labels(*COMMON, dependency, result).inc()
    duration.labels(*COMMON, dependency, result).observe(elapsed)
    last_probe.labels(*COMMON, dependency).set(time.time())
    snapshots.pop(dependency, None)  # Never publish stale successful statistics after a failure.
    collection.labels(*COMMON, dependency).set(0)
    if client is None:
        return
    try:
        async with asyncio.timeout(2):
            if dependency == "postgres":
                cursor = await client.execute(
                    "SELECT xact_commit, xact_rollback, numbackends, "
                    "current_setting('max_connections')::int "
                    "FROM pg_stat_database WHERE datname = current_database()")
                snapshots[dependency] = await cursor.fetchone()
            else:
                snapshots[dependency] = (await client.info("stats"))["total_commands_processed"]
        collection.labels(*COMMON, dependency).set(1)
    except (psycopg.Error, RedisError, OSError, TimeoutError):
        pass
    finally:
        if dependency == "postgres":
            await client.close()
        else:
            await client.aclose()


async def poll():
    while True:
        started = time.monotonic()
        await asyncio.gather(sample("postgres"), sample("redis"))
        await asyncio.sleep(max(0, 15 - (time.monotonic() - started)))


async def metrics(_request):
    return web.Response(body=generate_latest(registry),
                        headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})


async def run():
    for required in ("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD", "REDIS_HOST", "REDIS_PASSWORD"):
        if not os.getenv(required):
            raise RuntimeError(f"Missing required setting: {required}")
    app = web.Application()
    app.router.add_get("/metrics", metrics)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", 9100).start()
    task = asyncio.create_task(poll())
    try:
        await task
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(run())
