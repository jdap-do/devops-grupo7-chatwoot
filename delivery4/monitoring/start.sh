#!/usr/bin/env bash
# Ejecutar con sudo en la VM; conserva el laboratorio local sin cambios.
set -euo pipefail
test "$(id -u)" -eq 0
test "$(docker info --format '{{.DockerRootDir}}')" = /srv/chatwoot/docker
root=/srv/chatwoot/repo
python3 "$root/delivery4/monitoring/configure.py"
mkdir -p "$root/observability/prometheus/adapters"
cat > /etc/systemd/system/grupo7-resource-sampler.service <<'UNIT'
[Unit]
Description=Grupo 7 - muestras de memoria de contenedores GCP
After=docker.service
Requires=docker.service
RequiresMountsFor=/srv/chatwoot

[Service]
Type=simple
WorkingDirectory=/srv/chatwoot/repo
ExecStart=/usr/bin/python3 /srv/chatwoot/repo/observability/scripts/collect-resources.py --prefix devops-grupo7-gcp --suffix=-1 --directory /srv/chatwoot/repo/observability/.runtime/resources --deployment-state /srv/chatwoot/cd/state.json
Restart=on-failure
RestartSec=10
UMask=0022

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now grupo7-resource-sampler.service
compose=(docker compose --env-file "$root/observability/.env.gcp"
  -f "$root/observability/compose.yml" -f "$root/delivery4/monitoring/compose.gcp.yml")
"${compose[@]}" config --quiet
"${compose[@]}" up -d --build
for attempt in $(seq 1 60); do
  if curl -fsS --max-time 5 http://127.0.0.1:9090/-/ready >/dev/null &&
     curl -fsS --max-time 5 http://127.0.0.1:3005/api/health >/dev/null; then
    "${compose[@]}" ps
    echo 'Prometheus y Grafana responden. Falta validar targets y datos bajo tráfico autenticado.'
    exit 0
  fi
  sleep 5
done
echo 'No se confirmó disponibilidad del monitoreo. Revisar estado y logs.' >&2
exit 1
