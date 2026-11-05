#!/usr/bin/env bash
# Ejecutar con sudo en la VM; no ejecutar en Cloud Shell ni en el PC local.
set -euo pipefail
test "$(id -u)" -eq 0 || { echo 'Ejecutar con sudo en la VM.' >&2; exit 1; }
mountpoint -q /srv/chatwoot
test "$(docker info --format '{{.DockerRootDir}}')" = /srv/chatwoot/docker
app_dir=$(cd -- "$(dirname -- "$0")" && pwd)
env_file=/srv/chatwoot/config/app.env
install -d -m 0700 /srv/chatwoot/config
umask 077
if [ ! -f "$env_file" ]; then
  secret_file=$(mktemp /srv/chatwoot/config/app.env.XXXXXX)
  {
    printf 'SECRET_KEY_BASE=%s\n' "$(openssl rand -hex 64)"
    printf 'POSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 32)"
    printf 'REDIS_PASSWORD=%s\n' "$(openssl rand -hex 32)"
    printf 'FRONTEND_URL=http://localhost:3000\n'
    printf 'FORCE_SSL=false\n'
    # Registro inicial solo con localhost. Deshabilitar antes de exposición pública.
    printf 'ENABLE_ACCOUNT_SIGNUP=true\n'
  } > "$secret_file"
  mv "$secret_file" "$env_file"
fi
chmod 0600 "$env_file"
compose=(docker compose --env-file "$env_file" -f "$app_dir/compose.yml")
"${compose[@]}" config --quiet
"${compose[@]}" pull
"${compose[@]}" up -d --wait postgres redis
"${compose[@]}" run --rm prepare
"${compose[@]}" up -d rails sidekiq
for attempt in $(seq 1 60); do
  # Una instalación nueva redirige al onboarding. Exigir 200 final, no aceptar
  # cualquier 302 como salud, y limitar redirecciones/tiempo para evitar bucles.
  status=$(curl -s -L --max-redirs 3 -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:3000/ || true)
  if [ "$status" = 200 ]; then
    "${compose[@]}" ps
    printf 'Chatwoot devuelve HTTP 200 tras seguir redirecciones desde localhost:3000. Falta completar onboarding, prueba funcional y monitoreo.\n'
    exit 0
  fi
  sleep 5
done
"${compose[@]}" ps -a
echo 'No se obtuvo HTTP 200 dentro del tiempo previsto. Revisar logs de Rails y Sidekiq.' >&2
exit 1
