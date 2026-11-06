"""Acceso y comprobaciones compartidas de los ejercicios GameDay en GCP."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CD = Path('/srv/chatwoot/cd')
RUNTIME = Path('/srv/chatwoot/gameday/runtime')
CLIENT = Path('/srv/chatwoot/repo/observability/.runtime/chatwoot-client.json')
GATEWAY = 'http://127.0.0.1:3011'
PROMETHEUS = 'http://127.0.0.1:9090'
JOBS = {'chatwoot-http', 'chatwoot-dependencies', 'chatwoot-resources'}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def docker(*args):
    return subprocess.run(['docker', *args], check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def inspect(container):
    return json.loads(docker('inspect', container))[0]


def active_target():
    target = json.loads((CD / 'state.json').read_text())['active']
    slot = target['slot']
    if slot not in ('legacy', 'blue', 'green'):
        raise RuntimeError('Slot activo desconocido')
    name = 'devops-grupo7-gcp-rails-1' if slot == 'legacy' else f'devops-grupo7-{slot}-rails-1'
    return target, name


def fetch_json(url):
    with urlopen(url, timeout=7) as response:
        return json.loads(response.read())


def read_api(client, revision):
    url = f'{GATEWAY}/api/v1/accounts/{int(client["account_id"])}/conversations'
    request = Request(url, headers={'api_access_token': client['token'], 'Connection': 'close'})
    started = time.monotonic()
    try:
        with urlopen(request, timeout=7) as response:
            body = json.loads(response.read())
            if response.status != 200 or not isinstance(body, dict) or 'data' not in body:
                raise RuntimeError('La lectura no devuelve conversaciones validas')
            if response.headers.get('X-Group7-Revision') != revision:
                raise RuntimeError('La lectura no corresponde a la revision del ejercicio')
            return {'status': 200, 'duration_seconds': round(time.monotonic() - started, 3)}
    except HTTPError as error:
        status = error.code
        error.close()
        return {'status': status, 'duration_seconds': round(time.monotonic() - started, 3)}


def monitoring():
    query = urlencode({'query': 'up{job=~"chatwoot-http|chatwoot-dependencies|chatwoot-resources"}'})
    result = fetch_json(f'{PROMETHEUS}/api/v1/query?{query}')
    if result['status'] != 'success':
        raise RuntimeError('Prometheus no permite consultar los targets')
    targets = result['data']['result']
    if {item['metric']['job'] for item in targets} != JOBS or any(float(item['value'][1]) != 1 for item in targets):
        raise RuntimeError('Falta un target de telemetria o no esta saludable')
    alerts = fetch_json(f'{PROMETHEUS}/api/v1/alerts')
    if alerts['status'] != 'success':
        raise RuntimeError('No se pueden consultar las alertas iniciales')
    return [{'name': alert['labels']['alertname'], 'state': alert['state']}
            for alert in alerts['data']['alerts']]


def ensure_no_pending_exercise():
    for name in ('rails-outage', 'latency'):
        path = RUNTIME / f'{name}.json'
        if path.exists() and json.loads(path.read_text())['phase'] != 'recovered':
            raise RuntimeError(f'El ejercicio {name} sigue pendiente; ejecutar su recover antes de otra inyeccion')
