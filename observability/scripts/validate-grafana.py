"""Validate local Grafana and its provisioned Prometheus datasource without printing credentials."""
import base64
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parents[1]
password = (root / ".runtime/grafana-admin-password.txt").read_text(encoding="utf-8").strip()
token = base64.b64encode(("admin:" + password).encode()).decode()


def get(path):
    request = Request("http://127.0.0.1:3005" + path, headers={"Authorization": "Basic " + token})
    with urlopen(request, timeout=15) as response:
        return json.load(response)


health = get("/api/health")
assert health["database"] == "ok", health
print("PASS: Grafana database healthy; version", health["version"])
source = get("/api/datasources/uid/prometheus-unal")
assert source["url"] == "http://prometheus:9090" and source["type"] == "prometheus", source
print("PASS: datasource Prometheus UNAL provisioned with UID prometheus-unal")
check = get("/api/datasources/uid/prometheus-unal/health")
assert check["status"] == "OK", check
print("PASS: Grafana connects to Prometheus")
query = get("/api/datasources/proxy/uid/prometheus-unal/api/v1/query?" + urlencode({"query": "up"}))
assert query["status"] == "success", query
samples = query["data"]["result"]
expected = {"chatwoot-http", "chatwoot-dependencies", "chatwoot-resources"}
healthy = {value["metric"]["job"] for value in samples if float(value["value"][1]) == 1}
assert expected <= healthy, healthy
print("PASS: queries through Grafana reach all three Prometheus jobs")
print("NOTE: final dashboard belongs to David and has not been created or validated here")
