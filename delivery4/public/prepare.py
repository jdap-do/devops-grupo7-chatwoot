"""Stage public HTTPS on the VM. Does not open the firewall or start Caddy."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from urllib.request import urlopen

ROOT = Path('/srv/chatwoot/public')
SOURCE = Path(__file__).resolve().parent


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def prepare():
    if os.geteuid() != 0 or not os.path.ismount('/srv/chatwoot'):
        raise SystemExit('Ejecutar con sudo dentro de la VM con disco montado.')
    result = run('docker', 'info', '--format', '{{.DockerRootDir}}', capture_output=True)
    if result.stdout.strip() != '/srv/chatwoot/docker':
        raise SystemExit('Docker no utiliza el disco persistente esperado.')
    token = Path('/srv/chatwoot/config/duckdns-token')
    permissions = token.stat()
    if permissions.st_uid != 0 or stat.S_IMODE(permissions.st_mode) != 0o600 or not token.read_text().strip():
        raise SystemExit('El token debe existir, ser privado (0600) y pertenecer a root.')
    state = json.loads(Path('/srv/chatwoot/cd/state.json').read_text())
    slot = state['active']['slot']
    if slot not in ('legacy', 'blue', 'green'):
        raise SystemExit('Slot activo no valido.')
    for port, endpoint in ((3001, '/'), (3005, '/api/health')):
        with urlopen(f'http://127.0.0.1:{port}{endpoint}', timeout=10) as response:
            if response.status != 200:
                raise SystemExit('La aplicacion no supera la comprobacion previa.')
    ROOT.mkdir(mode=0o700, exist_ok=True)
    for name in ('Caddyfile', 'compose.yml', 'update-dns.py'):
        shutil.copyfile(SOURCE / name, ROOT / name)
    for name in ('data', 'config'):
        (ROOT / name).mkdir(mode=0o700, exist_ok=True)
    run('docker', 'compose', '-f', str(ROOT / 'compose.yml'), 'config', '--quiet')
    run('docker', 'compose', '-f', str(ROOT / 'compose.yml'), 'pull')
    run('docker', 'compose', '-f', str(ROOT / 'compose.yml'), 'run', '--rm', '--no-deps',
        'caddy', 'caddy', 'validate', '--config', '/etc/caddy/Caddyfile')
    for name in ('grupo7-duckdns.service', 'grupo7-duckdns.timer'):
        shutil.copyfile(SOURCE / name, Path('/etc/systemd/system') / name)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'start', 'grupo7-duckdns.service')
    run('systemctl', 'enable', '--now', 'grupo7-duckdns.timer')
    print('Preparacion correcta: Caddy validado y actualizacion DNS activada.')
    print('Pendiente: configurar URLs de aplicaciones, abrir 80/443 y activar HTTPS.')


if __name__ == '__main__':
    with Path('/srv/chatwoot/cd/deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prepare()
