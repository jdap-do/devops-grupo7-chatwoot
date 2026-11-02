"""Deterministic synthetic telemetry. Does not contact Chatwoot or its dependencies."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST

BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
SCENARIOS = ("healthy", "degraded", "telemetry_missing", "no_memory_limit", "dependencies_missing")
REQUESTS_PER_TICK = 10
PROBE_INTERVAL_SECONDS = 15
COMPONENTS = ("rails", "sidekiq", "postgres", "redis")
MEMORY_LIMITS = (1024, 512, 1024, 256)
HEALTHY_MEMORY_FRACTIONS = (0.35, 0.45, 0.3, 0.2)
DEGRADED_MEMORY_FRACTIONS = (0.95, 0.9, 0.85, 0.92)
MIB = 1024 * 1024


class SyntheticTelemetry:
    def __init__(self):
        self.lock = threading.Lock()
        self.scenario = "healthy"
        self.sequence = 0
        self.ticks = 0
        self.registries = {name: CollectorRegistry() for name in ("http", "dependencies", "resources")}
        self.requests = Counter(
            "unal_chatwoot_http_requests_total", "Synthetic completed requests",
            ("method", "status_class", "availability_result"), registry=self.registries["http"],
        )
        self.duration = Histogram(
            "unal_chatwoot_http_request_duration_seconds", "Synthetic request duration",
            ("method", "status_class", "availability_result"), buckets=BUCKETS, registry=self.registries["http"],
        )
        self.in_flight = Gauge("unal_chatwoot_http_in_flight_requests", "Synthetic concurrent requests", registry=self.registries["http"])
        for status, result in (("2xx", "good"), ("5xx", "bad"), ("4xx", "bad"), ("4xx", "excluded"), ("3xx", "excluded")):
            self.requests.labels("GET", status, result)
            self.duration.labels("GET", status, result)

        registry = self.registries["dependencies"]
        self.probe_success = Gauge("unal_dependency_probe_success", "Synthetic last probe result", ("dependency",), registry=registry)
        self.probe_duration = Histogram("unal_dependency_probe_duration_seconds", "Synthetic probe duration", ("dependency", "result"), buckets=BUCKETS, registry=registry)
        self.probes = Counter("unal_dependency_probes_total", "Synthetic completed probes", ("dependency", "result"), registry=registry)
        self.transactions = Counter("unal_postgres_transactions_total", "Synthetic transactions", ("outcome",), registry=registry)
        self.commands = Counter("unal_redis_commands_processed_total", "Synthetic Redis commands", registry=registry)
        self.connections = Gauge("unal_postgres_connections", "Synthetic application connections", registry=registry)
        self.max_connections = Gauge("unal_postgres_max_connections", "Synthetic server connection limit", registry=registry)
        for dependency in ("postgres", "redis"):
            for result in ("success", "failure"):
                self.probes.labels(dependency, result)
                self.probe_duration.labels(dependency, result)

        registry = self.registries["resources"]
        self.memory = Gauge("unal_container_memory_working_set_bytes", "Synthetic working set", ("component",), registry=registry)
        self.memory_limit = Gauge("unal_container_memory_limit_bytes", "Synthetic finite limit", ("component",), registry=registry)

    def set_scenario(self, scenario):
        if scenario not in SCENARIOS:
            raise ValueError("Escenario desconocido")
        with self.lock:
            self.scenario = scenario

    def tick(self):
        with self.lock:
            degraded = self.scenario == "degraded"
            self.ticks += 1
            for _ in range(REQUESTS_PER_TICK):
                self.sequence += 1
                if self.scenario == "telemetry_missing":
                    continue
                position = self.sequence % 10
                if degraded and position in (0, 1):
                    status, result, duration = "4xx", "bad", 0.02
                elif degraded and position == 2:
                    status, result, duration = "5xx", "bad", 0.03
                elif self.sequence % 100 == 3:
                    status, result, duration = "4xx", "excluded", 0.01
                else:
                    status, result = "2xx", "good"
                    duration = 0.8 if (degraded and position in (4, 5, 6)) or self.sequence % 50 == 7 else 0.15
                self.requests.labels("GET", status, result).inc()
                self.duration.labels("GET", status, result).observe(duration)
            self.in_flight.set(8 if degraded else 1)

            if self.ticks % PROBE_INTERVAL_SECONDS == 1:
                for dependency in ("postgres", "redis"):
                    failed = degraded and dependency == "postgres"
                    result = "failure" if failed else "success"
                    self.probe_success.labels(dependency).set(0 if failed else 1)
                    self.probes.labels(dependency, result).inc()
                    self.probe_duration.labels(dependency, result).observe(1.5 if failed else 0.03)
            self.transactions.labels("commit").inc(4)
            self.transactions.labels("rollback").inc(1 if degraded else 0)
            self.commands.inc(20)
            self.connections.set(90 if degraded else 12)
            self.max_connections.set(100)
            fractions = DEGRADED_MEMORY_FRACTIONS if degraded else HEALTHY_MEMORY_FRACTIONS
            for component, limit, fraction in zip(COMPONENTS, MEMORY_LIMITS, fractions):
                self.memory.labels(component).set(limit * MIB * fraction)
                if self.scenario == "no_memory_limit" and component == "redis":
                    self.memory_limit.remove(component)
                else:
                    self.memory_limit.labels(component).set(limit * MIB)

    def render(self, group):
        with self.lock:
            if (group == "http" and self.scenario == "telemetry_missing") or (group == "dependencies" and self.scenario == "dependencies_missing"):
                return b"# Synthetic scenario: required metrics intentionally omitted.\n"
            return generate_latest(self.registries[group])


telemetry = SyntheticTelemetry()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/metrics/") and path.rsplit("/", 1)[-1] in telemetry.registries:
            payload = telemetry.render(path.rsplit("/", 1)[-1])
            content_type = CONTENT_TYPE_LATEST
        elif path == "/scenario":
            payload = json.dumps({"scenario": telemetry.scenario, "synthetic": True, "available": SCENARIOS}).encode()
            content_type = "application/json"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        if urlparse(self.path).path != "/scenario":
            self.send_error(404)
            return
        try:
            request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            telemetry.set_scenario(request["scenario"])
        except (ValueError, KeyError, TypeError):
            self.send_error(422)
            return
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_):
        pass


def generate():
    while True:
        telemetry.tick()
        time.sleep(1)


if __name__ == "__main__":
    threading.Thread(target=generate, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
