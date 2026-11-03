"""Validate exact cgroup conversion, stale samples and the live Prometheus interface."""
import json
import sys
import time
from urllib.parse import urlencode
from urllib.request import urlopen

sys.path.insert(0, "/app")
import resource_exporter as module

now = time.time()
fixture = {"rails": {"timestamp": now, "working_set_bytes": 1024, "limit_bytes": 0},
           "postgres": {"timestamp": now, "working_set_bytes": 256, "limit_bytes": 512}}
lines = module.exposition(fixture, now).splitlines()
assert not any(line.startswith("unal_container_memory_limit_bytes{") and
               'component="rails"' in line for line in lines)
stale = module.exposition(fixture, now + 46)
assert not any(line.startswith("unal_container_memory_working_set_bytes{") for line in stale.splitlines())
print("PASS: absent/unlimited containers have no fictional limit; stale samples omit memory values")
base = "http://prometheus:9090/api/v1/query?"
for expression, expected in (
    ('up{job="chatwoot-resources"}', 1),
    ('count(unal_container_memory_working_set_bytes)', 4),
    ('count(unal_container_memory_limit_bytes)', 2),
    ('sum(unal_container_memory_collection_success)', 4),
):
    result = json.load(urlopen(base + urlencode({"query": expression})))["data"]["result"]
    assert len(result) == 1 and float(result[0]["value"][1]) == expected, (expression, result)
    print("PASS:", expression, "=", expected)
for expression in ('unal_container_memory_working_set_bytes / 1024 / 1024',
                   'unal_container_memory_working_set_bytes / unal_container_memory_limit_bytes * 100'):
    result = json.load(urlopen(base + urlencode({"query": expression})))["data"]["result"]
    print(expression, [(sample["metric"]["component"], sample["value"][1]) for sample in result])
