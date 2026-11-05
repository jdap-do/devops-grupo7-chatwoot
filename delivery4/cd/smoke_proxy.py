"""Prueba real de recarga Nginx con dos APIs ficticias, aisladas de Chatwoot."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

SOURCE = Path(__file__).resolve().parent
REPO = SOURCE.parents[1]
NGINX = 'nginx:1.28-alpine@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236'
PREFIX = 'grupo7-cd-test-' + uuid.uuid4().hex[:10]
containers = []


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def config(slot):
    return docker('run', '--rm', '--network=none',
                  '--mount', f'type=bind,source={REPO},target=/workspace,readonly',
                  '--workdir', '/workspace', 'python:3.12-slim', 'python', '-c',
                  f"import runpy; m=runpy.run_path('delivery4/cd/deploy.py'); print(m['route']('{slot}', '{('a' if slot == 'blue' else 'b') * 40}'))")


try:
    docker('network', 'create', PREFIX)
    for slot in ('blue', 'green'):
        name = PREFIX + '-' + slot
        docker('run', '-d', '--name', name, '--network', PREFIX,
               '--network-alias', f'devops-grupo7-{slot}-rails-1',
               'python:3.12-slim', 'python', '-u', '-c',
               'from http.server import BaseHTTPRequestHandler,HTTPServer\n'
               'class Handler(BaseHTTPRequestHandler):\n'
               ' def do_GET(self):\n'
               '  if self.headers.get("api_access_token") != "fixture-token":\n'
               '   self.send_response(401); self.end_headers(); return\n'
               '  self.send_response(200); self.end_headers(); self.wfile.write(b"{\\\"fixture\\\":true}")\n'
               ' def log_message(self,*args): pass\n'
               'HTTPServer(("0.0.0.0",3000),Handler).serve_forever()')
        containers.append(name)
    with tempfile.TemporaryDirectory(prefix='grupo7-cd-') as directory:
        path = Path(directory)
        (path / 'active.conf').write_text(config('blue'), encoding='utf-8')
        router = PREFIX + '-router'
        docker('run', '-d', '--name', router, '--network', PREFIX,
               '--network-alias', 'router',
               '--mount', f'type=bind,source={SOURCE / "nginx.conf"},target=/etc/nginx/nginx.conf,readonly',
               '--mount', f'type=bind,source={path},target=/etc/nginx/conf.d,readonly', NGINX)
        containers.append(router)
        docker('exec', router, 'nginx', '-t')
        processes = docker('top', router, '-eo', 'pid,args')
        assert 'PID' in processes and 'nginx' in processes, processes
        # Esperar a los servidores antes de iniciar la medicion de cambio.
        docker('exec', containers[0], 'python', '-c',
               'import time,urllib.request\n'
               'for n in range(40):\n'
               ' try:\n'
               '  req=urllib.request.Request("http://router:8080/",headers={"api_access_token":"fixture-token"})\n'
               '  urllib.request.urlopen(req,timeout=2).read(); break\n'
               ' except Exception: time.sleep(.25)\n'
               'else: raise SystemExit("proxy not ready")')
        probe = subprocess.Popen(['docker', 'exec', containers[0], 'python', '-c',
            'import time,json,urllib.request\n'
            'seen={}; failed=0; end=time.monotonic()+8\n'
            'while time.monotonic()<end:\n'
            ' try:\n'
            '  req=urllib.request.Request("http://router:8080/",headers={"api_access_token":"fixture-token"})\n'
            '  with urllib.request.urlopen(req,timeout=2) as r:\n'
            '   json.loads(r.read()); key=r.headers["X-Group7-Revision"]; seen[key]=seen.get(key,0)+1\n'
            ' except Exception: failed+=1\n'
            ' time.sleep(.05)\n'
            'print(json.dumps({"seen":seen,"failed":failed}))'], stdout=subprocess.PIPE, text=True)
        time.sleep(2)
        temporary = path / 'active.tmp'
        temporary.write_text(config('green'), encoding='utf-8')
        temporary.replace(path / 'active.conf')
        docker('exec', router, 'nginx', '-t')
        docker('exec', router, 'nginx', '-s', 'reload')
        output, _ = probe.communicate(timeout=20)
        if probe.returncode:
            raise RuntimeError('Probe failed')
        result = json.loads(output)
        assert result['failed'] == 0, result
        assert set(result['seen']) == {'a' * 40, 'b' * 40}, result
        print('PASS: Nginx cambio blue -> green; cero errores HTTP/JSON en la prueba aislada')
        print(json.dumps(result))
finally:
    for name in reversed(containers):
        subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, check=False)
    subprocess.run(['docker', 'network', 'rm', PREFIX], stdout=subprocess.DEVNULL, check=False)
