# Infraestructura GCP — Entrega 4

Estado: configuración validada localmente; todavía sin plan autenticado ni apply.
Esta fase prepara el anfitrión, no acredita Chatwoot desplegado ni CD funcionando.

## Relación con el laboratorio existente

`terraform/` conserva el despliegue Docker local de la Entrega 2, sin cambios.
`infra/gcp/` es una raíz Terraform independiente para GCP y necesita un workspace
HCP nuevo en modo de ejecución **Local**. No reutilizar un workspace que contenga
el estado del laboratorio. No ejecutar `terraform init -migrate-state` entre ellos.

El modo Local significa que Cloud Shell ejecuta Terraform y HCP guarda el estado;
no significa que los recursos se creen en el computador. La VM se crea en GCP.

## Qué crea y por qué

| Recurso | Configuración | Propósito |
| --- | --- | --- |
| VM | e2-standard-2, Ubuntu 24.04 LTS, 2 vCPU y 8 GB | Ejecutar los contenedores existentes |
| Disco de arranque | 20 GB pd-balanced | Sistema operativo y herramientas |
| Disco de datos | 60 GB pd-balanced | Conservar datos y volúmenes Docker entre sesiones |
| Red/subred | Red propia, rango 10.77.0.0/24 | Separar el laboratorio del proyecto por defecto |
| Firewall | TCP 22 solo desde IAP | Acceso SSH sin abrir administración a Internet |
| IPv4 | Efímera | Salida para descargar paquetes e imágenes sin Cloud NAT |
| APIs | Compute, IAP y OS Login | Aprovisionamiento y acceso autenticado |

La IP puede cambiar al detener y encender la VM. La URL estable y HTTPS se
resolverán antes de abrir la aplicación al público; no se fija una IP estática
en esta fase. PostgreSQL, Redis, Prometheus y Grafana no tienen puertos públicos.

La VM no lleva cuenta de servicio adjunta. El acceso de operadores mediante
OS Login/IAP requiere permisos de usuario que se comprobarán al conectar; esta
configuración no otorga roles a personas ni crea claves de servicio.

## Preparación en Cloud Shell

Prerrequisito de bootstrap: habilitar Cloud Resource Manager antes del primer
apply. En este proyecto, la activación de IAP devolvió 403 SERVICE_DISABLED hasta
que esta API esté habilitada. Este paso permite a Terraform habilitar el resto;
no crea una VM ni sustituye la configuración de infraestructura:

```bash
gcloud services enable cloudresourcemanager.googleapis.com
```

Si un apply termina parcialmente, conservar el workspace y su estado, habilitar
el requisito faltante y generar un plan nuevo. No reutilizar el plan ya aplicado
parcialmente ni borrar el estado para comenzar otra vez.

Requisitos confirmados por el usuario: Terraform 1.17.1, proyecto
`project-45d258e3-00bf-4e6f-bbe`, facturación habilitada y API Compute habilitada.
La cuota regional reporta 24 E2 CPU, con uso cero; no garantiza capacidad zonal.

1. Confirmar la organización HCP existente y crear un workspace exclusivo, por
   ejemplo `grupo7-e4-gcp-infra`, con ejecución Local y sin conexión VCS automática.
2. Autenticarse personalmente con `terraform login`; no publicar tokens.
3. Disponer de estos archivos en el clon de Cloud Shell. La rama local de
   preparación aún no está publicada: un clone de main no los incluye todavía.
4. Exportar organización y workspace confirmados, y crear las entradas locales:

```bash
export TF_CLOUD_ORGANIZATION='ORGANIZACION_CONFIRMADA'
export TF_WORKSPACE='grupo7-e4-gcp-infra'
cp infra/gcp/terraform.tfvars.example infra/gcp/terraform.tfvars
terraform -chdir=infra/gcp init -input=false
terraform -chdir=infra/gcp validate
terraform -chdir=infra/gcp plan -out=gcp.tfplan
```

Revisar el plan y la estimación de costo antes de aplicar. Debe afectar solo los
recursos nuevos de GCP; ningún recurso Docker o workspace anterior debe aparecer.
No ejecutar apply si cambia la cuenta, el proyecto o la base acordada.

```bash
terraform -chdir=infra/gcp apply gcp.tfplan
terraform -chdir=infra/gcp output
```

El plan guardado queda ignorado por Git. En Cloud Shell se utiliza la identidad
autorizada de la sesión; si el proveedor solicita credenciales, completar la
autenticación oficial, sin exportar claves JSON ni copiar tokens al repositorio.

## Arranque y comprobación

`startup.sh` prepara solo el disco identificado como `chatwoot-data`. Rechaza
formatos inesperados y nunca reformatea un volumen ext4 existente. Monta los
datos en `/srv/chatwoot` y configura Docker para almacenarlos allí. Instala Docker
desde su repositorio oficial y habilita su arranque con systemd. La primera
ejecución puede tardar varios minutos; la creación de la VM no acredita que haya
terminado esta preparación.

```bash
gcloud compute ssh grupo7-chatwoot --zone=us-central1-a --tunnel-through-iap
```

Dentro de la VM:

```bash
sudo cat /srv/chatwoot/bootstrap-ready
sudo docker info --format '{{.DockerRootDir}}'
sudo docker compose version
findmnt /srv/chatwoot
```

La raíz Docker debe ser `/srv/chatwoot/docker`. Revisar errores de preparación con
`sudo journalctl -u google-startup-scripts.service --no-pager -n 100`.
La instalación inicial resuelve paquetes e imagen Ubuntu desde canales oficiales;
no fija sus revisiones exactas. Registrar las versiones instaladas en la evidencia.

## Encender, detener y conservar datos

El usuario acordó pagar con créditos solo durante trabajo y sustentación. La
detención no se programa todavía: antes debe comprobarse el cierre seguro de la
aplicación. Se puede declarar `desired_status = "TERMINATED"` en el tfvars local,
revisar plan y aplicar para detener; `RUNNING` permite encender. En Compute Engine,
TERMINATED significa detenida y conserva discos.

La VM también puede detenerse desde la consola. Antes de un apply posterior,
ajustar `desired_status` al estado que se desea conservar: un apply con RUNNING
puede encenderla de nuevo. El futuro CD de aplicación no debe aplicar esta raíz
de infraestructura ni encender automáticamente el laboratorio detenido.

Discos y otros recursos conservados pueden seguir consumiendo créditos. Antes
del sábado, encender con tiempo y comprobar aplicación, telemetría y alertas.
Los apagados no equivalen a disponibilidad ni a cobertura de monitoreo.

## Protección y retiro final

La VM tiene protección de eliminación y el disco de datos `prevent_destroy`.
Estas opciones evitan borrados accidentales, no son respaldos. Para retirar el
proyecto se requiere guardar lo necesario, revisar el inventario y desactivar
conscientemente las protecciones antes del destroy. No usar destroy para ahorrar
entre sesiones.

## Validaciones realizadas

- `terraform fmt -check`: correcto.
- `terraform init -backend=false`: proveedor oficial Google 7.0.0 descargado;
  lockfile creado. No conecta HCP ni crea recursos.
- `terraform validate`: correcto con el proveedor.
- Script de arranque: revisión de sintaxis; ejecución real pendiente.
- Pendientes: organización/workspace HCP, autenticación, plan GCP, permisos IAP,
  costo final, apply y comprobación real del arranque.

La fase siguiente reutilizará la configuración de Chatwoot y observabilidad,
añadirá los accesos de aplicación y el CD. El presente conjunto no sustituye esas
pruebas ni las evidencias de actualización sin pérdida de disponibilidad.
