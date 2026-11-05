#!/usr/bin/env bash
# Arranque de la VM. No contiene secretos ni despliega una versión de Chatwoot.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

# Se monta exclusivamente el disco de datos creado por esta configuración.
data_device=/dev/disk/by-id/google-chatwoot-data
test -b "$data_device"
fs_type=$(lsblk -dn -o FSTYPE "$data_device" | tr -d '[:space:]')
if [ -z "$fs_type" ]; then
  # Rechazar discos con particiones o firmas: nunca reformatear datos existentes.
  test "$(lsblk -nr -o NAME "$data_device" | wc -l)" -eq 1
  test -z "$(wipefs -n --noheadings -o TYPE "$data_device")"
  mkfs.ext4 -L chatwoot-data "$data_device"
elif [ "$fs_type" != ext4 ]; then
  echo "Disco con formato inesperado; requiere revisión manual." >&2
  exit 1
fi
install -d -m 0755 /srv/chatwoot
data_uuid=$(blkid -s UUID -o value "$data_device")
if ! grep -q "^UUID=$data_uuid " /etc/fstab; then
  printf 'UUID=%s /srv/chatwoot ext4 defaults 0 2\n' "$data_uuid" >> /etc/fstab
fi
mountpoint -q /srv/chatwoot || mount /srv/chatwoot

# Instalar desde el repositorio oficial Docker solo durante la preparación inicial.
if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' \
    "$(dpkg --print-architecture)" "$VERSION_CODENAME" > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

# Todos los volúmenes Docker se conservan en el disco de datos independiente.
if [ ! -f /etc/docker/daemon.json ]; then
  systemctl stop docker.service docker.socket
  install -d -m 0755 /etc/docker /srv/chatwoot/docker
  printf '{"data-root":"/srv/chatwoot/docker","log-driver":"json-file","log-opts":{"max-size":"10m","max-file":"3"}}\n' > /etc/docker/daemon.json
fi
install -d -m 0755 /etc/systemd/system/docker.service.d
printf '[Unit]\nRequiresMountsFor=/srv/chatwoot\n' > /etc/systemd/system/docker.service.d/data.conf
systemctl daemon-reload
systemctl enable --now docker.service
docker info --format '{{.DockerRootDir}}'
docker compose version
install -d -m 0700 /srv/chatwoot/config
date -Is > /srv/chatwoot/bootstrap-ready
