"""Una sola vez, despues de init: llevar telemetria al proxy estable."""
import json
from pathlib import Path
import shutil
import subprocess
import os

if os.geteuid() != 0:
    raise SystemExit('Ejecutar con sudo en la VM')
state = Path('/srv/chatwoot/cd/state.json')
json.loads(state.read_text())
repo = Path('/srv/chatwoot/repo')
env = repo / 'observability/.env.gcp'
lines = env.read_text().splitlines()
lines = [line for line in lines if not line.startswith('CHATWOOT_UPSTREAM_URL=')]
lines.append('CHATWOOT_UPSTREAM_URL=http://grupo7-router:8080')
temporary = env.with_suffix('.tmp')
temporary.write_text('\n'.join(lines) + '\n')
temporary.chmod(0o600)
os.replace(temporary, env)
source = Path(__file__).resolve().parents[2]
shutil.copyfile(source / 'observability/scripts/collect-resources.py',
                repo / 'observability/scripts/collect-resources.py')
dropin = Path('/etc/systemd/system/grupo7-resource-sampler.service.d')
dropin.mkdir(exist_ok=True)
(dropin / 'cd.conf').write_text('''[Service]
ExecStart=
ExecStart=/usr/bin/python3 /srv/chatwoot/repo/observability/scripts/collect-resources.py --prefix devops-grupo7-gcp --suffix=-1 --directory /srv/chatwoot/repo/observability/.runtime/resources --deployment-state /srv/chatwoot/cd/state.json
''')
subprocess.run(['systemctl', 'daemon-reload'], check=True)
subprocess.run(['systemctl', 'restart', 'grupo7-resource-sampler.service'], check=True)
subprocess.run(['docker', 'compose', '--env-file', str(env),
                '-f', str(repo / 'observability/compose.yml'),
                '-f', str(repo / 'delivery4/monitoring/compose.gcp.yml'),
                'up', '-d', '--no-deps', 'http-gateway'], check=True)
print('Gateway apunta al proxy; muestreador sigue el slot activo. Validar integracion.')
