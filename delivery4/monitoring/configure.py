"""Configure monitoring on the VM without displaying credentials."""
import json
import os
from pathlib import Path
import secrets
import subprocess

if os.geteuid() != 0:
    raise SystemExit("Ejecutar con sudo en la VM.")
root = Path(__file__).resolve().parents[2]
obs = root / "observability"
runtime = obs / ".runtime"
runtime.mkdir(mode=0o700, exist_ok=True)
runtime.chmod(0o700)
(runtime / "resources").mkdir(mode=0o755, exist_ok=True)


def write_private(path, value, mode=0o600):
    if path.exists():
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(value)


settings = dict(line.split("=", 1) for line in
                Path("/srv/chatwoot/config/app.env").read_text().splitlines()
                if line and not line.startswith("#"))
for key in ("POSTGRES_PASSWORD", "REDIS_PASSWORD"):
    if not settings.get(key):
        raise SystemExit("Falta configuración de dependencia: " + key)
write_private(obs / ".env.prober", "\n".join([
    "PGHOST=devops-grupo7-gcp-postgres-1",
    "PGDATABASE=chatwoot_production", "PGUSER=postgres",
    "PGPASSWORD=" + settings["POSTGRES_PASSWORD"],
    "REDIS_HOST=devops-grupo7-gcp-redis-1",
    "REDIS_PASSWORD=" + settings["REDIS_PASSWORD"], "",
]))
cd_state = Path('/srv/chatwoot/cd/state.json')
upstream = 'http://grupo7-router:8080' if cd_state.exists() else 'http://devops-grupo7-gcp-rails-1:3000'
write_private(obs / ".env.gcp", "\n".join([
    "CHATWOOT_NETWORK=devops-grupo7-gcp-network",
    "CHATWOOT_UPSTREAM_URL=" + upstream, "",
]))
# Bind-mount legible para Grafana; directorio padre 0700 protege acceso en host.
write_private(runtime / "grafana-admin-password.txt", secrets.token_hex(24) + "\n", 0o444)

client = runtime / "chatwoot-client.json"
if not client.exists():
    # Read existing demo user/token/conversation; do not create users or rotate tokens.
    ruby = ("u=User.find_by!(email: 'admin@example.com'); a=u.accounts.first!; "
            "c=a.conversations.first!; puts '__CLIENT__'+"
            "{token:u.access_token.token,account_id:a.id,conversation_id:c.display_id}.to_json")
    slot = json.loads(cd_state.read_text())['active']['slot'] if cd_state.exists() else 'legacy'
    rails = 'devops-grupo7-gcp-rails-1' if slot == 'legacy' else f'devops-grupo7-{slot}-rails-1'
    result = subprocess.run(["docker", "exec", rails,
                             "bundle", "exec", "rails", "runner", ruby],
                            capture_output=True, text=True, timeout=120)
    lines = [line[len("__CLIENT__"):] for line in result.stdout.splitlines()
             if line.startswith("__CLIENT__")]
    if result.returncode != 0 or len(lines) != 1:
        raise SystemExit("No se pudo leer cliente existente. Verificar usuario y conversación; no se muestran tokens.")
    parsed = json.loads(lines[0])
    if not all(parsed.get(key) for key in ("token", "account_id", "conversation_id")):
        raise SystemExit("Cliente incompleto.")
    write_private(client, json.dumps(parsed))
print("Configuración local preparada sin mostrar credenciales.")
