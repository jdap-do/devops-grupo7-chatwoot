"""CD en una VM existente. No crea infraestructura ni ejecuta migraciones."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from urllib.request import Request, urlopen

ROOT = Path('/srv/chatwoot/cd')
SOURCE = Path(__file__).resolve().parent
CLIENT = Path('/srv/chatwoot/repo/observability/.runtime/chatwoot-client.json')
PORTS = {'legacy': 3000, 'blue': 3002, 'green': 3003}


def run(*args, capture=False, **kwargs):
    return subprocess.run(list(args), check=True, text=True,
                          stdout=subprocess.PIPE if capture else None, **kwargs).stdout


def container(slot, service='rails'):
    return f'devops-grupo7-gcp-{service}-1' if slot == 'legacy' else f'devops-grupo7-{slot}-{service}-1'


def atomic(path, text):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(text)
    os.replace(temporary, path)


def route(slot, revision):
    if slot not in PORTS or not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Destino o revision no valido')
    return f'''upstream chatwoot_active {{ server {container(slot)}:3000; }}
server {{
  listen 8080;
  client_max_body_size 40m;
  add_header X-Group7-Revision {revision} always;
  location / {{
    proxy_pass http://chatwoot_active;
    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $original_scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_read_timeout 3600s;
  }}
}}
'''


def switch(target):
    path = ROOT / 'routes/active.conf'
    previous = path.read_text()
    atomic(path, route(target['slot'], target['revision']))
    try:
        run('docker', 'exec', 'grupo7-router', 'nginx', '-t')
        run('docker', 'exec', 'grupo7-router', 'nginx', '-s', 'reload')
    except Exception:
        atomic(path, previous)
        run('docker', 'exec', 'grupo7-router', 'nginx', '-t')
        run('docker', 'exec', 'grupo7-router', 'nginx', '-s', 'reload')
        raise


def compose(slot, *args):
    settings = dict(line.split('=', 1) for line in (ROOT / f'{slot}.env').read_text().splitlines())
    return run('docker', 'compose', '-p', f'devops-grupo7-{slot}',
               '-f', str(SOURCE / 'slots.yml'), *args,
               env={**os.environ, **settings, 'CHATWOOT_ENV_FILE': '/srv/chatwoot/config/app.env'})


def read_api(port, client, path='/conversations', revision=None):
    request = Request(f'http://127.0.0.1:{port}/api/v1/accounts/{int(client["account_id"])}{path}',
                      headers={'api_access_token': client['token'], 'Connection': 'close'})
    with urlopen(request, timeout=5) as response:
        if response.status != 200:
            raise ValueError('HTTP distinto de 200')
        json.loads(response.read())
        if revision and response.headers.get('X-Group7-Revision') != revision:
            raise ValueError('El proxy aun no sirve la revision esperada')


def ready(target, client):
    paths = ['/conversations', '/contacts',
             f'/conversations/{int(client["conversation_id"])}/messages']
    for attempt in range(90):
        try:
            for path in paths:
                read_api(PORTS[target['slot']], client, path)
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError('La candidata no supera las lecturas API autenticadas')


class Continuity:
    def __init__(self, client):
        self.client, self.counts, self.stop = client, Counter(), threading.Event()
        self.thread = threading.Thread(target=self.watch, daemon=True)

    def watch(self):
        while not self.stop.is_set():
            try:
                read_api(3001, self.client)
                self.counts['200_json'] += 1
            except Exception:
                self.counts['failed'] += 1
            self.stop.wait(0.2)

    def finish(self):
        self.stop.set()
        self.thread.join(timeout=7)
        return dict(self.counts)


def init():
    if (ROOT / 'state.json').exists():
        raise RuntimeError('CD ya inicializado; no sobrescribir el estado')
    revision = run('docker', 'exec', container('legacy'), 'cat', '/app/.git_sha', capture=True).strip()
    image = run('docker', 'inspect', '--format', '{{.Config.Image}}', container('legacy'), capture=True).strip()
    (ROOT / 'routes').mkdir(exist_ok=True)
    shutil.copyfile(SOURCE / 'nginx.conf', ROOT / 'nginx.conf')
    shutil.copyfile(SOURCE.parent / 'app/demo-gcp.html', ROOT / 'demo-gcp.html')
    target = {'slot': 'legacy', 'revision': revision, 'image': image}
    atomic(ROOT / 'routes/active.conf', route('legacy', revision))
    run('docker', 'compose', '-f', str(SOURCE / 'proxy.yml'), 'up', '-d')
    client = json.loads(CLIENT.read_text())
    for attempt in range(30):
        try:
            read_api(3001, client, revision=revision)
            break
        except Exception:
            time.sleep(2)
    else:
        raise RuntimeError('Proxy no validado; la aplicacion original sigue en puerto 3000')
    atomic(ROOT / 'state.json', json.dumps({'active': target, 'previous': None}, indent=2))
    print('Proxy inicializado: puerto 3001; original conservada en 3000')


def deploy(image, revision, rollback=False):
    state = json.loads((ROOT / 'state.json').read_text())
    old = state['active']
    client = json.loads(CLIENT.read_text())
    if not rollback and old['image'] == image and old['revision'] == revision:
        read_api(3001, client, revision=revision)
        print('La revision ya esta activa y responde; no recrear contenedores')
        return
    # No reciclar una version a la que aun apuntan conexiones de workers anteriores.
    # Docker necesita PID en la salida de ps para identificar los procesos.
    workers = run('docker', 'top', 'grupo7-router', '-eo', 'pid,args', capture=True)
    if 'worker process is shutting down' in workers:
        raise RuntimeError('Quedan conexiones anteriores drenando; no reciclar slots todavia')
    if rollback:
        target = state.get('previous')
        if not target:
            raise RuntimeError('No existe version anterior registrada')
        run('docker', 'start', container(target['slot']))
    else:
        slot = 'green' if old['slot'] == 'blue' else 'blue'
        target = {'slot': slot, 'image': image, 'revision': revision}
        if state.get('previous') and state['previous']['slot'] == slot:
            # El slot anterior se recicla. No ofrecer rollback a una imagen ya reemplazada.
            state['previous'] = None
            atomic(ROOT / 'state.json', json.dumps(state, indent=2))
        # Instalar la configuracion inmutable de esta candidata, sin cargarla como shell.
        atomic(ROOT / f'{slot}.env', f'CHATWOOT_IMAGE={image}\nSLOT_PORT={PORTS[slot]}\n')
        compose(slot, 'pull')
        # Fallar antes de arrancar si requiere migraciones; no alterar el esquema compartido.
        compose(slot, 'run', '--rm', '--no-deps', 'rails', 'db:abort_if_pending_migrations')
        compose(slot, 'up', '-d', '--no-deps', 'rails')
        actual = run('docker', 'exec', container(slot), 'cat', '/app/.git_sha', capture=True).strip()
        if actual != revision:
            raise RuntimeError('El SHA de la imagen no coincide con el commit de CI')
    ready(target, client)
    watch = Continuity(client)
    watch.thread.start()
    switched = False
    try:
        time.sleep(3)
        if watch.counts['failed']:
            raise RuntimeError('La version actual ya tiene errores; no cambiar trafico')
        # Iniciar el worker nuevo antes de detener el anterior (misma DB y colas).
        if target['slot'] == 'legacy':
            run('docker', 'start', container('legacy', 'sidekiq'))
        else:
            compose(target['slot'], 'up', '-d', '--no-deps', 'sidekiq')
        time.sleep(8)
        if run('docker', 'inspect', '--format', '{{.State.Running}}',
               container(target['slot'], 'sidekiq'), capture=True).strip() != 'true':
            raise RuntimeError('Sidekiq candidato no permanece encendido')
        switch(target)
        switched = True
        for attempt in range(20):
            try:
                read_api(3001, client, revision=target['revision'])
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError('No se confirma el cambio de revision en el proxy')
        time.sleep(15)
        if watch.counts['failed']:
            raise RuntimeError('Se detectaron errores HTTP durante el cambio')
        # Rails anterior permanece encendido para solicitudes/WebSockets en curso.
        run('docker', 'stop', '--time', '60', container(old['slot'], 'sidekiq'))
        atomic(ROOT / 'state.json', json.dumps({'active': target, 'previous': old}, indent=2))
    except Exception:
        # Incluso si fallo la escritura de estado despues de detener el worker viejo.
        run('docker', 'start', container(old['slot'], 'sidekiq'))
        if switched:
            switch(old)
        # No detener Rails: puede haber peticiones en curso aunque se haya revertido.
        if target['slot'] != old['slot']:
            run('docker', 'stop', '--time', '60', container(target['slot'], 'sidekiq'))
        raise
    finally:
        counts = watch.finish()
        evidence = {'utc': datetime.now(timezone.utc).isoformat(), 'from': old,
                    'to': target, 'samples': counts,
                    'committed': json.loads((ROOT / 'state.json').read_text())['active'] == target}
        output = ROOT / ('deployment-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
        atomic(output, json.dumps(evidence, indent=2))
        print(json.dumps(evidence, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['init', 'deploy', 'rollback'])
    parser.add_argument('--image')
    parser.add_argument('--revision')
    args = parser.parse_args()
    if os.geteuid() != 0 or not os.path.ismount('/srv/chatwoot'):
        raise SystemExit('Ejecutar con sudo en la VM con disco montado')
    if run('docker', 'info', '--format', '{{.DockerRootDir}}', capture=True).strip() != '/srv/chatwoot/docker':
        raise SystemExit('Docker no utiliza el disco persistente esperado')
    ROOT.mkdir(mode=0o700, exist_ok=True)
    os.umask(0o077)
    with (ROOT / 'deploy.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'init':
            init()
        elif args.action == 'rollback':
            deploy(None, None, rollback=True)
        else:
            if not re.fullmatch(r'ghcr\.io/jdap-do/devops-grupo7-chatwoot@sha256:[0-9a-f]{64}', args.image or ''):
                parser.error('Se requiere el digest inmutable de la imagen propia')
            if not re.fullmatch(r'[0-9a-f]{40}', args.revision or ''):
                parser.error('Se requiere el SHA completo del commit')
            deploy(args.image, args.revision)


if __name__ == '__main__':
    main()
