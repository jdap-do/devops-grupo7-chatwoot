"""Exercise real Prometheus -> Alertmanager -> local webhook delivery with synthetic data.

Run from the repository root: python observability/validation/validate-alert-delivery.py
Uses the default localhost ports from compose.yml. Requires the isolated stack running.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SOURCE = 'http://127.0.0.1:18091'
PROMETHEUS = 'http://127.0.0.1:19090'
ALERTMANAGER = 'http://127.0.0.1:19093'
RECEIVER = 'http://127.0.0.1:18093'
EVIDENCE = Path(__file__).parent.parent / 'evidence' / 'david' / 'alerts' / 'alert-delivery.json'
RESULT = {'synthetic': True, 'started_at': datetime.now(timezone.utc).isoformat(), 'checks': []}


def fetch(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=10) as response:
        body = response.read()
        return json.loads(body) if body else None


def scenario(name):
    fetch(SOURCE + '/scenario', {'scenario': name})
    print('Escenario:', name, flush=True)


def wait_for(label, condition, timeout=240):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = condition()
        if value:
            RESULT['checks'].append({'check': label, 'at': datetime.now(timezone.utc).isoformat(), 'evidence': value})
            print('OK:', label, flush=True)
            return value
        time.sleep(3)
    raise TimeoutError(label)


def active(name):
    return [a for a in fetch(PROMETHEUS + '/api/v1/alerts')['data']['alerts']
            if a['labels']['alertname'] == name and a['state'] == 'firing']


def notification(name, status, since):
    events = fetch(RECEIVER + '/notifications?' + urlencode({'since_id': since}))['events']
    return [e for e in events if any(a['labels']['alertname'] == name and a['status'] == status
                                   for a in e['payload']['alerts'])]


def last_id():
    return max((e['id'] for e in fetch(RECEIVER + '/notifications')['events']), default=0)


def query(expression):
    return fetch(PROMETHEUS + '/api/v1/query?' + urlencode({'query': expression}))['data']['result']


def exercise(slo, failure):
    name = 'Chatwoot' + slo.capitalize() + 'BudgetBurn'
    baseline = last_id()
    scenario(failure)
    wait_for(name + ' firing', lambda: active(name))
    wait_for(name + ' webhook firing', lambda: notification(name, 'firing', baseline))
    wait_for(name + ' inhibits ticket', lambda: [a for a in fetch(ALERTMANAGER + '/api/v2/alerts')
             if a['labels']['alertname'] == name + 'Slow' and a['status']['inhibitedBy']])
    baseline = last_id()
    scenario('recovery')
    wait_for(name + ' inactive', lambda: not active(name))
    wait_for(name + ' webhook resolved', lambda: notification(name, 'resolved', baseline))


def main():
    assert fetch(SOURCE + '/scenario')['synthetic'] is True
    assert fetch(RECEIVER + '/healthz')['synthetic'] is True
    # Recovery observations dilute previous burns without deleting stored history.
    scenario('recovery')
    wait_for('initial pages inactive', lambda: not any(
        a['state'] == 'firing' and a['labels']['severity'] == 'page'
        for a in fetch(PROMETHEUS + '/api/v1/alerts')['data']['alerts']))
    exercise('availability', 'availability_failure')
    exercise('latency', 'latency_failure')
    name = 'ChatwootTelemetryMissing'
    baseline = last_id()
    scenario('telemetry_missing')
    wait_for('HTTP endpoint up despite missing metrics', lambda: query(
        'up{project="devops-grupo7",environment="lab",job="chatwoot-http"} == 1')
        if not query('unal_chatwoot:http_telemetry_valid:ratio') else [])
    wait_for(name + ' firing after 2m', lambda: active(name))
    wait_for(name + ' webhook firing', lambda: notification(name, 'firing', baseline))
    baseline = last_id()
    scenario('healthy')
    wait_for(name + ' inactive', lambda: not active(name))
    wait_for(name + ' webhook resolved', lambda: notification(name, 'resolved', baseline))


if __name__ == '__main__':
    try:
        main()
        RESULT['passed'] = True
    except Exception as error:
        RESULT.update(passed=False, error=str(error))
        raise
    finally:
        scenario('healthy')
        RESULT['finished_at'] = datetime.now(timezone.utc).isoformat()
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(json.dumps(RESULT, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
