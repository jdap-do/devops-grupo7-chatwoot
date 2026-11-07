"""GameDay en GCP: detencion de Rails activo y recuperacion exclusivamente manual."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
import subprocess
import time
from urllib.error import URLError

from common import CD, CLIENT, RUNTIME, active_target, docker, ensure_no_pending_exercise, inspect, monitoring, read_api, timestamp

STATE = RUNTIME / 'rails-outage.json'
STOP_GRACE_SECONDS = 10
RECOVERY_TIMEOUT_SECONDS = 180
POLL_SECONDS = 2


def event(name, **fields):
    record = {'at_utc': timestamp(), 'event': name, **fields}
    line = json.dumps(record, ensure_ascii=False)
    with (RUNTIME / 'rails-outage-events.jsonl').open('a') as output:
        output.write(line + '\n')
    print(line, flush=True)


def save(state):
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2), encoding='utf-8')
    os.replace(temporary, STATE)


def inject(client):
    ensure_no_pending_exercise()
    target, name = active_target()
    details = inspect(name)
    if not details['State']['Running']:
        raise RuntimeError('Rails activo ya esta detenido; no inyectar una nueva falla')
    read = read_api(client, target['revision'])
    if read['status'] != 200:
        raise RuntimeError('La lectura autenticada inicial no responde HTTP 200')
    alerts = monitoring()
    if alerts:
        event('initial_alerts', alerts=alerts)
        raise RuntimeError('Hay alertas pendientes o activas; revisar antes de inyectar')
    # Guardar antes de detener: recover funciona aunque se interrumpa esta terminal.
    state = {'exercise': datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'),
             'phase': 'injecting', 'injection_started_at_utc': timestamp(), 'target': target,
             'container': name, 'container_id': details['Id']}
    save(state)
    event('baseline_verified', **state, initial_read=read, initial_alerts=alerts)
    event('injection_started', exercise=state['exercise'], container=state['container'])
    docker('stop', '--time', str(STOP_GRACE_SECONDS), state['container_id'])
    if inspect(state['container_id'])['State']['Running']:
        raise RuntimeError('Rails sigue ejecutandose despues de la detencion')
    state.update(phase='injected', stopped_at_utc=timestamp())
    save(state)
    read = read_api(client, state['target']['revision'])
    event('injected', exercise=state['exercise'], measured_read=read,
          next_action='Observar degradacion y ejecutar recover manualmente')
    if not 500 <= read['status'] < 600:
        raise RuntimeError('No se observa un 5xx por el gateway; revisar el recorrido. Ejecutar recover para restaurar Rails')


def exercise_target(state):
    target, name = active_target()
    if target != state['target'] or name != state['container']:
        raise RuntimeError('El despliegue cambio desde la inyeccion; revisar el ejercicio antes de intervenir')
    details = inspect(state['container_id'])
    if inspect(name)['Id'] != state['container_id']:
        raise RuntimeError('El contenedor fue reemplazado desde la inyeccion')
    return details


def recover(state, client):
    if state['phase'] not in ('injecting', 'injected', 'recovering'):
        raise RuntimeError('El ejercicio ya fue recuperado')
    details = exercise_target(state)
    state.update(phase='recovering', recovery_started_at_utc=timestamp())
    save(state)
    event('recovery_started', exercise=state['exercise'], container=state['container'])
    if not details['State']['Running']:
        docker('start', state['container_id'])
    # Nginx debe resolver de nuevo el nombre si Docker cambio la IP de Rails.
    docker('exec', 'grupo7-router', 'nginx', '-t')
    docker('exec', 'grupo7-router', 'nginx', '-s', 'reload')
    event('router_reloaded', exercise=state['exercise'])
    deadline = time.monotonic() + RECOVERY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            read = read_api(client, state['target']['revision'])
            if read['status'] == 200:
                state.update(phase='recovered', recovered_at_utc=timestamp())
                save(state)
                event('functionally_recovered', exercise=state['exercise'], measured_read=read,
                      next_action='Mantener trafico y observar estabilidad al menos 5 minutos; verificar alertas y notificaciones')
                return
        except (URLError, TimeoutError, ValueError, RuntimeError):
            pass  # Rails puede estar iniciando; la espera solo comienza tras recover manual.
        time.sleep(POLL_SECONDS)
    raise RuntimeError('No se confirma recuperacion funcional en 180 s; revisar logs y repetir recover tras corregir la causa')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inject', 'recover'])
    args = parser.parse_args()
    if os.geteuid() != 0 or not os.path.ismount('/srv/chatwoot'):
        parser.error('Ejecutar con sudo dentro de la VM GCP con el disco /srv/chatwoot montado')
    os.umask(0o077)
    RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Compartir el bloqueo del despliegue durante cada comando, sin modificar CD.
    with (CD / 'deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        client = json.loads(CLIENT.read_text(encoding='utf-8'))
        try:
            if args.action == 'inject':
                inject(client)
            else:
                state = json.loads(STATE.read_text())
                recover(state, client)
        except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
            event('command_failed', action=args.action, error_type=type(error).__name__)
            # No imprimir respuestas HTTP ni credenciales del cliente.
            message = str(error) if isinstance(error, RuntimeError) else 'Revisar archivos locales, conectividad y Docker'
            parser.exit(1, message + '\n')


if __name__ == '__main__':
    main()
