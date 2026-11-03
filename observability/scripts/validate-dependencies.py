"""Checks healthy probes, isolated connection failures and recovery without stopping services."""
import asyncio
import json
import os
import sys
from urllib.parse import urlencode
from urllib.request import urlopen

sys.path.insert(0, "/app")
import dependency_prober as prober


async def main():
    for dependency, port_key in (("postgres", "PGPORT"), ("redis", "REDIS_PORT")):
        await prober.sample(dependency)
        labels = {"project": prober.COMMON[0], "environment": prober.COMMON[1], "dependency": dependency}
        assert prober.registry.get_sample_value("unal_dependency_probe_success", labels) == 1
        assert prober.registry.get_sample_value("unal_dependency_collection_success", labels) == 1
        assert dependency in prober.snapshots
        print("PASS:", dependency, "basic probe and statistics")
        original = os.environ.get(port_key)
        os.environ[port_key] = "1"  # Only this isolated validation process uses the bad endpoint.
        try:
            await prober.sample(dependency)
            assert prober.registry.get_sample_value("unal_dependency_probe_success", labels) == 0
            assert dependency not in prober.snapshots, "Stale statistics must be removed"
            assert prober.registry.get_sample_value("unal_dependency_probes_total",
                                                    {**labels, "result": "failure"}) == 1
        finally:
            if original is None:
                os.environ.pop(port_key)
            else:
                os.environ[port_key] = original
        await prober.sample(dependency)
        assert prober.registry.get_sample_value("unal_dependency_probe_success", labels) == 1
        assert dependency in prober.snapshots
        for result in ("success", "failure"):
            selected = {**labels, "result": result}
            assert prober.registry.get_sample_value("unal_dependency_probes_total", selected) == (
                prober.registry.get_sample_value("unal_dependency_probe_duration_seconds_count", selected))
        print("PASS:", dependency, "isolated connection failure, no stale values, recovery, histogram/count parity")

    def query(expression):
        response = json.load(urlopen("http://prometheus:9090/api/v1/query?" + urlencode({"query": expression})))
        assert response["status"] == "success", response
        return response["data"]["result"]

    for expression, expected, expected_count in (
        ('up{job="chatwoot-dependencies"}', 1, 1),
        ('unal_dependency_probe_success{project="devops-grupo7",environment="lab"}', 1, 2),
        ('unal_dependency_collection_success{project="devops-grupo7",environment="lab"}', 1, 2),
        ('count(unal_dependency_probe_duration_seconds_bucket{le="1"})', 4, 1),
    ):
        samples = query(expression)
        assert len(samples) == expected_count, (expression, samples)
        assert all(float(sample["value"][1]) == expected for sample in samples), (expression, samples)
        print("PASS: Prometheus", expression)
    for name, expected_count in (("unal_postgres_transactions_total", 2),
                                  ("unal_redis_commands_processed_total", 1),
                                  ("unal_postgres_connections", 1),
                                  ("unal_postgres_max_connections", 1)):
        assert len(query(name)) == expected_count, name
        print("PASS: live series", name)
    print("NOTE: validation used its own process; no Chatwoot dependency was stopped or modified")


asyncio.run(main())
