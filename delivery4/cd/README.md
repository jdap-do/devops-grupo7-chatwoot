# Despliegue por versiones alternas en GCP

Estado: implementacion preparada y pruebas locales aprobadas. Falta inicializar
el proxy en la VM y comprobar despliegue, reversion y conversacion en GCP.
No afirmar continuidad real hasta conservar las evidencias de esas pruebas.

## Que cambia

El CI existente construye, escanea y publica en GHCR. Un nuevo job, solo para
push a main y con `GCP_CD_ENABLED=true`, despliega el digest publicado por esa
misma ejecucion mediante el workflow reutilizable `grupo7-gcp-deploy.yml`.
No acepta imagenes elegidas desde un PR ni crea claves de cuenta de servicio.
La VM debe estar encendida; el workflow falla si esta detenida y no la enciende.

El proxy Nginx escucha solamente en `127.0.0.1:3001` y comparte la red existente.
El puerto anterior 3000 se conserva para la instalacion original. No existe un
puerto publico nuevo. El tunel y el gateway de monitoreo deben apuntar al proxy
para medir y observar la version activa, no una version fija.

Cada slot (`blue` o `green`) contiene Rails y Sidekiq. Comparten PostgreSQL,
Redis, configuracion privada y el volumen de adjuntos originales. No se ejecuta
`db:prepare`, `db:migrate` ni `down -v` durante CD. Las imagenes que tengan
migraciones pendientes se rechazan antes de cambiar trafico. Cambios de esquema
requieren un procedimiento especifico y compatibilidad entre versiones.

## Preparacion unica

Revisar el PR de esta fase. Hasta terminar la preparacion, dejar la variable
`GCP_CD_ENABLED` ausente o en `false`. Integrar archivos no habilita CD por si solo.

Copiar desde la revision revisada a un directorio nuevo de la VM:
`delivery4/cd/`, `delivery4/app/demo-gcp.html` y
`observability/scripts/collect-resources.py`, conservando la estructura del repo.
No reemplazar `/srv/chatwoot/config/app.env` ni archivos `.runtime` del monitoreo.
En los ejemplos, `RELEASE_ROOT` representa ese directorio, no la carpeta personal.

Con VM encendida y aplicacion original operativa, ejecutar en la VM:

```bash
sudo python3 "$RELEASE_ROOT/delivery4/cd/deploy.py" init
sudo python3 "$RELEASE_ROOT/delivery4/cd/connect-monitoring.py"
sudo python3 /srv/chatwoot/repo/observability/scripts/generate-traffic.py --duration 60
sudo python3 /srv/chatwoot/repo/observability/scripts/validate-integration.py
```

`init` comprueba API autenticada a traves del proxy y registra el slot `legacy`.
No detiene la aplicacion original ni cambia su puerto. Si ya hay estado CD,
se niega a sobrescribirlo. `connect-monitoring.py` cambia solo el origen del
gateway y adapta el muestreo de memoria al slot activo; conserva las etiquetas
`rails`, `sidekiq`, `postgres` y `redis`. Las muestras no suman la memoria de
Rails de reserva: no son una medicion del consumo total de la VM.

Abrir Chatwoot con un tunel nuevo, por ejemplo desde Cloud Shell:

```bash
gcloud compute ssh grupo7-chatwoot \
  --project=project-45d258e3-00bf-4e6f-bbe --zone=us-central1-a \
  --tunnel-through-iap \
  -- -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8080:127.0.0.1:3001
```

La vista previa 8080 sirve ahora el proxy. Si el tunel anterior ocupa 8080,
cerrarlo con Ctrl+C primero. Grafana conserva el puerto remoto 3005.

## Activacion y evidencia

Despues de validar el proxy, configurar la variable de repositorio
`GCP_CD_ENABLED=true`. El siguiente push revisado a main construye, escanea,
publica y despliega. Los PR solo validan y prueban; no acceden a GCP.
Las ejecuciones de main se serializan sin cancelacion del despliegue en curso.

El despliegue verifica el SHA contenido en la imagen, rechaza migraciones
pendientes, espera lecturas API autenticadas de conversaciones, mensajes y
contactos, y comprueba que Sidekiq siga encendido. Inicia sondeo secuencial del
proxy cada 200 ms alrededor del cambio (timeout 5 s). Prueba Nginx y recarga
sus workers conservando las solicitudes abiertas. Confirma la cabecera de
revision y observa 15 segundos antes de registrar exito. Detiene el Sidekiq
anterior con tiempo de gracia; Rails anterior permanece disponible para drenar
conexiones HTTP/WebSocket y como reserva.

Cada intento que llega a la fase de cambio escribe
`/srv/chatwoot/cd/deployment-<fecha>.json`: versiones, cantidad de muestras
exitosas/fallidas y si quedo confirmado. Tambien aparece en el log de Actions.
No contiene el token API ni cuerpos de conversaciones. Unas muestras sin fallos
demuestran el resultado observado del ensayo, no una garantia de disponibilidad
absoluta ni el cumplimiento del SLO de 30 dias.

El test local de Nginx con dos APIs ficticias obtuvo 155 respuestas validas en
8 segundos y observo ambas revisiones sin errores. Las pruebas unitarias
cubren destino invalido, rechazo de Nginx, migraciones pendientes, conexiones
drenando y reversion tras fallo posterior al cambio. CI repite estas pruebas.

## Reversion y conexiones existentes

Si la candidata falla antes del cambio, el proxy conserva el destino anterior.
Si falla la verificacion posterior, se restaura la ruta anterior y su worker;
el workflow falla. Para una reversion deliberada, ejecutar en la VM el script
de la ultima release revisada con `rollback` en vez de `deploy`. No revierte
datos ni esquema. El mismo control de conexiones pendientes se aplica.

Antes de reciclar un slot, el script verifica que no queden workers de Nginx
drenando conexiones de una recarga previa. Si los hay, rechaza el nuevo cambio;
no corta WebSockets por un timeout arbitrario. Cerrar las sesiones de prueba
anteriores y reintentar cuando hayan drenado. Al reciclar un slot, deja de
ofrecerlo como version previa hasta confirmar el nuevo despliegue.

El pipeline no realiza una prueba completa de conversacion visitante-agente ni
un ensayo WebSocket prolongado; esos pasos se comprueban en GCP. Tampoco ofrece
alta disponibilidad ante falla de la VM o de PostgreSQL, pues todo sigue en una
sola VM. Las copias de seguridad y las migraciones mayores quedan fuera de este
procedimiento. Los incidentes siguen pendientes de coordinacion con David.

## Ahorro

Detener la VM al terminar. CD no programa encendidos ni crea recursos GCP.
Discos y otros recursos retenidos pueden seguir generando costo. No ejecutar
el arranque manual original para actualizar Rails despues de activar CD: ese
script administra la instalacion `legacy`, no el slot activo.

## Referencias

- [Recarga gradual de Nginx](https://nginx.org/en/docs/control.html).
- [Volumenes externos de Compose](https://docs.docker.com/reference/compose-file/volumes/).
