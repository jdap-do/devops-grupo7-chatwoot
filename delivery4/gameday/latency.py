"""GameDay de latencia: inject --delay-ms MILISEGUNDOS y recover manual."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

from common import CD, CLIENT, RUNTIME, active_target, docker, ensure_no_pending_exercise, inspect, monitoring, read_api, timestamp

STATE = RUNTIME / 'latency.json'
ROUTE = CD / 'routes/active.conf'
SOURCE = Path(__file__).resolve().parent
GATEWAY_CONTAINER = 'devops-grupo7-observability-http-gateway-1'
NETWORK = 'devops-grupo7-gcp-network'
READINESS_TIMEOUT_SECONDS = 20
POLL_SECONDS = 0.2


def event(name, **fields):
    record = {'at_utc': timestamp(), 'event': name, **fields}
    line = json.dumps(record, ensure_ascii=False)
    with (RUNTIME / 'latency-events.jsonl').open('a') as output:
        output.write(line + '\n')
    print(line, flush=True)


def atomic(path, content, mode=0o600):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(content, encoding='utf-8')
    temporary.chmod(mode)
    os.replace(temporary, path)


def save(state):
    atomic(STATE, json.dumps(state, indent=2))


def settings(state, delay_ms):
    atomic(Path(state['settings_directory']) / 'config.json', json.dumps({'delay_ms': delay_ms}), mode=0o644)


def delayed_route(original, name, rails):
    if f'upstream chatwoot_active {{ server {rails}:3000; }}' not in original:
        raise RuntimeError('La ruta actual no apunta al Rails activo esperado')
    directive = 'proxy_pass http://chatwoot_active;'
    if original.count(directive) != 1:
        raise RuntimeError('La ruta del router no corresponde al formato de CD esperado')
    mapping = f'''upstream gameday_latency {{ server {name}:8080; }}
map "$request_method:$uri" $gameday_backend {{
  default chatwoot_active;
  ~^GET:/api/v1/accounts/[0-9]+/(conversations(/search|/[0-9]+/messages)?|contacts)$ gameday_latency;
}}
'''
    return mapping + original.replace(directive, 'proxy_pass http://$gameday_backend;')


def switch_route(content):
    previous = ROUTE.read_text()
    atomic(ROUTE, content)
    try:
        docker('exec', 'grupo7-router', 'nginx', '-t')
        docker('exec', 'grupo7-router', 'nginx', '-s', 'reload')
    except subprocess.CalledProcessError:
        atomic(ROUTE, previous)
        docker('exec', 'grupo7-router', 'nginx', '-t')
        docker('exec', 'grupo7-router', 'nginx', '-s', 'reload')
        raise


def injector_health(state, expected_delay):
    deadline = time.monotonic() + READINESS_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            result = docker('exec', state['injector'], 'python', '-c',
                            'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2).read().decode())')
            if json.loads(result)['delay_ms'] == expected_delay:
                return
        except subprocess.CalledProcessError:
            pass  # Esperar el arranque o la lectura del archivo de configuracion.
        time.sleep(POLL_SECONDS)
    raise RuntimeError('El inyector no confirma su configuracion; revisar sus logs y ejecutar recover')


def inject(client, delay_ms):
    ensure_no_pending_exercise()
    target, rails = active_target()
    details = inspect(rails)
    if not details['State']['Running']:
        raise RuntimeError('Rails activo esta detenido; no inyectar latencia')
    baseline = read_api(client, target['revision'])
    if baseline['status'] != 200:
        raise RuntimeError('La lectura autenticada inicial no responde HTTP 200')
    alerts = monitoring()
    if alerts:
        event('initial_alerts', alerts=alerts)
        raise RuntimeError('Hay alertas pendientes o activas; revisar antes de inyectar')
    image = inspect(GATEWAY_CONTAINER)['Image']
    exercise = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    name = f'grupo7-latency-{exercise.lower()}'
    original = ROUTE.read_text()
    route = delayed_route(original, name, rails)
    directory = RUNTIME / exercise
    directory.mkdir(mode=0o755)
    directory.chmod(0o755)  # El proceso 10001 del contenedor lee este bind mount.
    state = {'exercise': exercise, 'phase': 'injecting', 'injection_started_at_utc': timestamp(),
             'target': target, 'container': rails, 'container_id': details['Id'],
             'injector': name, 'settings_directory': str(directory), 'delay_ms': delay_ms,
             'original_route': original, 'injected_route': route, 'baseline_read': baseline}
    save(state)
    settings(state, delay_ms)
    event('baseline_verified', exercise=exercise, container=rails, delay_ms=delay_ms, initial_read=baseline)
    docker('run', '-d', '--name', name, '--network', NETWORK, '--restart', 'unless-stopped',
           '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--memory', '128m',
           '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', f'UPSTREAM_URL=http://{rails}:3000',
           '--mount', f'type=bind,src={SOURCE / "latency_proxy.py"},dst=/app/latency_proxy.py,readonly',
           '--mount', f'type=bind,src={directory},dst=/gameday,readonly',
           image, 'python', '/app/latency_proxy.py')
    injector_health(state, delay_ms)
    switch_route(route)
    state.update(phase='injected', injected_at_utc=timestamp())
    save(state)
    read = read_api(client, target['revision'])
    event('injected', exercise=exercise, delay_ms=delay_ms, measured_read=read,
          next_action='Observar latencia y ejecutar recover manualmente')
    if read['status'] != 200:
        raise RuntimeError('La demora produce errores HTTP; revisar el impacto y ejecutar recover manualmente')
    if read['duration_seconds'] < delay_ms / 1000:
        raise RuntimeError('La consulta no muestra la demora solicitada; revisar el recorrido y ejecutar recover')


def recover(state, client):
    if state['phase'] not in ('injecting', 'injected', 'recovering'):
        raise RuntimeError('El ejercicio ya fue recuperado')
    target, rails = active_target()
    if target != state['target'] or inspect(rails)['Id'] != state['container_id']:
        raise RuntimeError('El despliegue cambio desde la inyeccion; revisar la ruta antes de recuperar')
    if ROUTE.read_text() not in (state['original_route'], state['injected_route']):
        raise RuntimeError('La ruta fue modificada externamente; no sobrescribirla')
    state.update(phase='recovering', recovery_started_at_utc=timestamp())
    save(state)
    # Retirar tambien la demora de solicitudes en curso antes de restaurar Nginx.
    settings(state, 0)
    switch_route(state['original_route'])
    read = read_api(client, target['revision'])
    if read['status'] != 200:
        raise RuntimeError('Ruta restaurada, pero la lectura no responde HTTP 200; revisar y repetir recover')
    # Los workers viejos pueden conservar conexiones WebSocket. No cortar conexiones.
    workers = docker('top', 'grupo7-router', '-eo', 'pid,args')
    containers = docker('ps', '-a', '--filter', f'name=^/{state["injector"]}$', '--format', '{{.Names}}').splitlines()
    if state['injector'] in containers:
        injector_health(state, 0)
        if 'worker process is shutting down' not in workers:
            docker('stop', '--time', '10', state['injector'])
            docker('rm', state['injector'])
        else:
            event('cleanup_deferred', injector=state['injector'], delay_ms=0,
                  reason='Workers anteriores drenando; conservar inyector sin demora')
    state.update(phase='recovered', recovered_at_utc=timestamp())
    save(state)
    event('functionally_recovered', exercise=state['exercise'], baseline_read=state['baseline_read'], measured_read=read,
          next_action='Comparar latencia con la inicial; observar al menos 5 minutos y verificar alertas y notificaciones')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    injection = actions.add_parser('inject', help='Comprobar e inyectar una demora')
    injection.add_argument('--delay-ms', type=int, required=True, help='Demora adicional, entero positivo en milisegundos')
    actions.add_parser('recover', help='Retirar la demora y restaurar la ruta original')
    args = parser.parse_args()
    if args.action == 'inject' and args.delay_ms <= 0:
        parser.error('--delay-ms debe ser un entero positivo')
    if os.geteuid() != 0 or not os.path.ismount('/srv/chatwoot'):
        parser.error('Ejecutar con sudo dentro de la VM GCP con el disco /srv/chatwoot montado')
    os.umask(0o077)
    RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (CD / 'deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        client = json.loads(CLIENT.read_text(encoding='utf-8'))
        try:
            if args.action == 'inject':
                inject(client, args.delay_ms)
            else:
                recover(json.loads(STATE.read_text()), client)
        except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
            event('command_failed', action=args.action, error_type=type(error).__name__)
            message = str(error) if isinstance(error, RuntimeError) else 'Revisar archivos locales, conectividad y Docker; usar recover si hubo inyeccion'
            parser.exit(1, message + '\n')


if __name__ == '__main__':
    main()
