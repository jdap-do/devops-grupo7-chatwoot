# GameDay: indisponibilidad del Rails activo en GCP

`rails-outage.py` identifica el Rails que recibe trafico, lo detiene y permite
recuperarlo manualmente. Se ejecuta con Python 3 y sudo **dentro de la VM**.
No instala dependencias. No modifica imagenes, rutas del proxy, configuracion de
Chatwoot, PostgreSQL, Redis, volumenes ni estado Terraform.

La inyeccion reproduce la indisponibilidad de Rails del Pre-Mortem; no introduce
una configuracion incompatible ni demuestra un despliegue defectuoso. Blue/green
ya valida una candidata antes de cambiar trafico. La falla residual demostrada
es la perdida del unico destino activo, sin conmutacion automatica general.

## Preparacion previa de la VM

Coordinar el uso del entorno y no hacer despliegues o merges a main entre
`inject` y el cierre del ejercicio. Cada comando comparte el bloqueo de CD,
pero no mantiene ese bloqueo entre comandos. Si cambia el despliegue, el script
rechaza intervenir y requiere revisar el estado real.

El codigo debe estar disponible en Cloud Shell mediante una copia revisada del
repositorio o una carga de archivos. La creacion local de la rama no la publica
en GitHub. El pipeline actual tampoco instala este directorio en la VM.

Desde la raiz de esa copia en Cloud Shell, transferir los scripts antes del ensayo:

```bash
gcloud compute scp delivery4/gameday/rails-outage.py delivery4/gameday/common.py \
  delivery4/gameday/latency.py delivery4/gameday/latency_proxy.py grupo7-chatwoot:~/ \
  --project=project-45d258e3-00bf-4e6f-bbe \
  --zone=us-central1-a --tunnel-through-iap

gcloud compute ssh grupo7-chatwoot \
  --project=project-45d258e3-00bf-4e6f-bbe \
  --zone=us-central1-a --tunnel-through-iap
```

Dentro de la VM, instalar la copia revisada en una carpeta propia del ejercicio:

```bash
sudo install -d -m 700 /srv/chatwoot/gameday/v1
sudo install -m 600 ~/rails-outage.py ~/common.py ~/latency.py /srv/chatwoot/gameday/v1/
sudo install -m 644 ~/latency_proxy.py /srv/chatwoot/gameday/v1/latency_proxy.py
sudo -n docker ps
```

`v1` identifica esta copia; no reemplazarla durante un ejercicio.
Para una revision posterior usar otra carpeta y registrar el commit utilizado.
La cuenta Google accede por IAP/OS Login y necesita sudo en la VM. Docker no
requiere contrasenas de la aplicacion ni de PostgreSQL.

El script utiliza estos archivos existentes y no imprime el token:

- `/srv/chatwoot/cd/state.json`: slot y revision activos.
- `/srv/chatwoot/repo/observability/.runtime/chatwoot-client.json`: cuenta y token
  de API para lecturas autenticadas por el gateway local, puerto 3011.

Prometheus debe responder en el puerto local 9090. Abrir previamente Grafana,
Prometheus, Alertmanager y el receptor de notificaciones mediante el acceso
autorizado del laboratorio. Confirmar la conexion del gateway al router estable.

## Ejecucion

En una primera terminal SSH, mantener trafico autenticado antes, durante y despues
del incidente. El generador existente admite hasta 1800 segundos y solo imprime
su resumen al finalizar; observar las solicitudes en Grafana durante el ejercicio:

```bash
sudo python3 /srv/chatwoot/repo/observability/scripts/generate-traffic.py --duration 1800
```

En otra terminal SSH, cuando se haya mostrado el estado nominal, comprobar e
inyectar con un unico comando:

```bash
sudo python3 /srv/chatwoot/gameday/v1/rails-outage.py inject
```

`inject` exige Rails ejecutandose, una lectura de conversaciones HTTP 200 con
JSON y revision esperada, los tres targets de telemetria saludables y ninguna
alerta pendiente o activa en Prometheus. Si alguna comprobacion falla, no detiene
Rails. No hay un comando `prepare` ni una pausa de confirmacion adicional.

Tras las comprobaciones, guarda el slot, revision e ID exacto del contenedor y
ejecuta `docker stop --time 10` sobre ese ID, dentro del mismo comando. Docker
permite hasta diez segundos de cierre antes de terminar el proceso. La detencion
explicita mantiene la caida con la politica `unless-stopped`. Luego comprueba que
Rails esta detenido y que una lectura por el gateway devuelve 5xx.

**No hay recuperacion automatica ni temporizador.** Un error del comando despues
de detener Rails tampoco lo inicia. Si se pierde la terminal, reconectarse y
ejecutar `recover` usando la misma copia del script.

## Diagnostico en vivo

Conservar la hora UTC que imprime el script y correlacionarla con el dashboard:

1. Ver errores 5xx y reduccion de disponibilidad en las lecturas autenticadas.
2. Revisar burn rate y presupuesto de disponibilidad; sin exitos recientes,
   la latencia puede quedar sin poblacion evaluable.
3. Contrastar Rails detenido con dependencias disponibles y sus metricas.
4. Mostrar el estado y logs del Rails identificado, ademas de los errores del
   router. Estos comandos se ejecutan en la VM, usando el nombre registrado:

```bash
sudo docker inspect --format '{{json .State}}' <rails-identificado>
sudo docker logs --since 5m --tail 50 <rails-identificado>
sudo docker logs --since 5m --tail 50 grupo7-router
```

No copiar literalmente `<rails-identificado>`. Consultar el campo `container`
emitido por `inject`. Los eventos del script son JSON estructurado; no sustituyen
los logs HTTP del recorrido. Revisar y ocultar datos privados antes de compartir
logs de aplicacion.

Mostrar activacion y recepcion de alertas si se producen. Sus ventanas incorporan
el historial: no hay tiempo de disparo garantizado. Ensayar ese tiempo con trafico
real antes de la presentacion; no borrar metricas ni modificar SLOs para acelerarlo.

## Recuperacion manual

Despues de verificar la degradacion y explicar el diagnostico:

```bash
sudo python3 /srv/chatwoot/gameday/v1/rails-outage.py recover
```

`recover` inicia el mismo contenedor si esta detenido y espera hasta 180 segundos
para confirmar HTTP 200, JSON de conversaciones y revision correcta por el
gateway. Esta espera verifica el arranque **despues de la orden manual**. No utiliza
rollback ni cambia el destino del proxy. Se puede repetir si fallo la comprobacion
anterior; no reinicia un contenedor que ya esta ejecutandose.

Si no recupera, inspeccionar el contenedor y sus logs, corregir la causa y repetir
`recover`. El evento `command_failed` no equivale a restauracion. Si el script no
esta disponible, comprobar el ID guardado y arrancar ese contenedor manualmente
con `sudo docker start <id-registrado>`; verificar despues la lectura autenticada.

Mantener trafico nominal y observar al menos cinco minutos de estabilidad,
acceso funcional, ausencia de errores sostenidos y telemetria valida. Verificar
aparte la resolucion en Prometheus y la notificacion `resolved` en el receptor.
El evento `functionally_recovered` confirma una lectura funcional; no acredita
estabilidad sostenida ni resolucion de alertas. El presupuesto consumido permanece.

## Evidencias y alcance de validacion

El estado actual queda en `/srv/chatwoot/gameday/runtime/rails-outage.json` y los
eventos acumulados en `rails-outage-events.jsonl`, dentro de la misma carpeta
privada. Los eventos tienen fecha UTC e identificador del ejercicio; no contienen
credenciales ni cuerpos de respuesta. Registrar tambien commit del script,
capturas, notificaciones, tiempos de deteccion y recuperacion e impacto observado
en el SLI y presupuesto. No publicar carpetas `.runtime` completas.

Este procedimiento debe ensayarse sobre la VM antes de considerarse listo para
la presentacion. Agregar el script al repositorio no acredita una caida real,
el disparo de alertas ni su entrega.

## Ejercicio de latencia

El segundo ejercicio usa `latency.py inject --delay-ms 800` y `latency.py recover`.
Consultar [LATENCY.md](LATENCY.md) para parametros, recorrido y recuperacion.
Ambos ejercicios comparten comprobaciones en `common.py` y rechazan una nueva
inyeccion mientras el otro ejercicio tenga una recuperacion pendiente.
