"""Read-only verification of the first Prometheus target and HTTP contract."""
import json
from urllib.parse import urlencode
from urllib.request import urlopen

base = "http://prometheus:9090"
targets = json.load(urlopen(base + "/api/v1/targets"))["data"]["activeTargets"]
http = [target for target in targets if target["labels"]["job"] == "chatwoot-http"]
assert len(http) == 1 and http[0]["health"] == "up", http
queries = {
    'up{job="chatwoot-http"}': 1,
    'count(unal_chatwoot_http_requests_total{availability_result=~"good|bad|excluded"})': 96,
    'count(unal_chatwoot_http_request_duration_seconds_bucket{le="0.5"})': 96,
}
for query, expected in queries.items():
    response = json.load(urlopen(base + "/api/v1/query?" + urlencode({"query": query})))
    assert response["status"] == "success", response
    values = response["data"]["result"]
    assert len(values) == 1 and float(values[0]["value"][1]) == expected, (query, values)
    print("PASS:", query, "=", expected)
print("PASS: HTTP target healthy; classified series and 500 ms buckets available")
