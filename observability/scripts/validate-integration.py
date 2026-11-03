"""Read-only checks for the integrated real Chatwoot metrics and David's dashboard."""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parents[1]
password = (root / '.runtime/grafana-admin-password.txt').read_text().strip()
auth = 'Basic ' + base64.b64encode(('admin:' + password).encode()).decode()


def get(url, authenticated=False):
    headers = {'Authorization': auth} if authenticated else {}
    with urlopen(Request(url, headers=headers), timeout=20) as response:
        return json.load(response)


def query(expression):
    result = get('http://127.0.0.1:3005/api/datasources/proxy/uid/prometheus-unal/api/v1/query?' +
                 urlencode({'query': expression}), True)
    assert result['status'] == 'success', result
    return result['data']['result']


rules = get('http://127.0.0.1:9090/api/v1/rules')['data']['groups']
flat = [rule for group in rules for rule in group['rules']]
assert len(flat) == 45, len(flat)
assert all(rule['health'] == 'ok' for rule in flat), [(r['name'], r['health']) for r in flat]
print('PASS: 40 recording rules and 5 alert rules healthy')
valid = query('unal_chatwoot:http_telemetry_valid:ratio')
assert len(valid) == 1 and float(valid[0]['value'][1]) == 1, valid
assert len(query('unal_chatwoot:slo_sli:ratio{window="5m"}')) == 2
assert len(query('unal_chatwoot:slo_budget_remaining:ratio')) == 2
assert len(query('unal_container_memory_working_set_bytes')) == 4
assert len(query('unal_dependency_probe_success == 1')) == 2
print('PASS: valid classified HTTP telemetry, two SLIs/budgets, four memory series and two dependencies')
dashboard = get('http://127.0.0.1:3005/api/dashboards/uid/chatwoot-sre-unal', True)['dashboard']
assert dashboard['uid'] == 'chatwoot-sre-unal'
results = []
for panel in dashboard['panels']:
    for target in panel.get('targets', []):
        expression = target['expr'].replace('$project', 'devops-grupo7').replace('$environment', 'lab')
        samples = query(expression)
        results.append({'panel': panel['title'], 'series': len(samples)})
assert len(results) == 28, len(results)
notifications = get('http://127.0.0.1:3006/healthz')
assert notifications['status'] == 'ok'
manager = get('http://127.0.0.1:9090/api/v1/alertmanagers')['data']['activeAlertmanagers']
assert len(manager) == 1
print('PASS: dashboard provisioned; all 28 panel queries execute through Grafana without API errors')
print('PASS: notification receiver healthy and Alertmanager discovered by Prometheus')
output = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
          'rules': len(flat), 'dashboard_uid': dashboard['uid'], 'panels': results,
          'alerts': get('http://127.0.0.1:9090/api/v1/alerts')['data']['alerts']}
(root / '.runtime/integration-check.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
print('Local verification: .runtime/integration-check.json')
