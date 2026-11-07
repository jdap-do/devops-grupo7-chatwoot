# GameDay: latencia configurable en consultas reales

Instalar los cuatro archivos Python siguiendo [README.md](README.md). Ejecutar
desde una sesion SSH dentro de la VM, con sudo. `latency.py` utiliza `common.py`
y monta `latency_proxy.py` en un contenedor temporal. El proxy debe ser legible
por el usuario 10001 del contenedor: instalar ese archivo con modo 644.

El inyector reutiliza el ID de imagen del gateway existente
`devops-grupo7-observability-http-gateway-1`, con su dependencia aiohttp. No descarga
imagenes ni instala paquetes en la VM. Se conecta a la red Docker existente y no
publica puertos adicionales. No requiere cambios en Rails, PostgreSQL o Redis.

## Inyeccion con demora elegida

Mantener el generador de trafico en otra terminal y mostrar el estado nominal.
Para comprobar el entorno e inyectar 800 milisegundos adicionales:

```bash
sudo python3 /srv/chatwoot/gameday/v1/latency.py inject --delay-ms 800
```

`--delay-ms` es obligatorio y acepta un entero positivo en milisegundos. Por
ejemplo, para ensayos posteriores pueden usarse `300` o `1500`. Para cambiar la
demora, recuperar el ejercicio actual y volver a ejecutar `inject` con otro valor.
Cero, negativos, decimales y parametros de demora para `recover` se rechazan.

El valor es una demora **adicional**, no una latencia total garantizada. Con 300 ms,
la respuesta podria seguir cumpliendo 500 ms. Demoras cercanas o superiores a
5000 ms pueden provocar timeouts en el gateway y consumir tambien el presupuesto
de disponibilidad. No existe un limite superior impuesto por el script.

`inject` comprueba una lectura autenticada exitosa, la revision activa, Rails
ejecutandose y los targets de telemetria. Al igual que el ejercicio de Rails,
requiere ausencia de alertas pendientes o activas; su resolucion depende del
historial y puede impedir ejecutar ambos ejercicios inmediatamente uno tras otro.
Ensayar y coordinar las ventanas antes de la presentacion.

Despues guarda el estado y la configuracion original del router en disco privado,
inicia el inyector y valida su salud. Cambia temporalmente `active.conf`, valida
Nginx y lo recarga. Si falla la validacion o recarga, intenta restaurar la ruta
anterior y deja el ejercicio pendiente de `recover`.

```text
Lecturas GET cubiertas: gateway -> router -> inyector -> Rails activo
Otras operaciones:     router -> Rails activo
```

La demora afecta conversaciones, busquedas, mensajes y contactos. Las respuestas
son las de Rails, incluidos sus errores reales. No altera las otras rutas,
metodos de escritura ni WebSocket. El cambio tambien afecta esas lecturas desde
la interfaz que accede por el router. El script comprueba una lectura por el
gateway y registra estado y duracion; con una demora excesiva puede observar un
5xx y terminar con error, dejando la retirada exclusivamente manual.

No ejecutar despliegues ni modificar rutas durante el ejercicio. Los dos scripts
usan el bloqueo de CD durante cada comando y rechazan inyecciones simultaneas.
El bloqueo no permanece adquirido mientras se observa la degradacion.

## Diagnostico y evidencias

Observar p95, proporcion de respuestas exitosas en <=500 ms, burn rate y saldo
del presupuesto de latencia. Contrastar con errores, trafico, solicitudes en curso,
recursos de Rails y dependencias. No es necesario que todas las senales empeoren.

Con todas las respuestas exitosas lentas, el burn rate del intervalo es
`1 / 0.05 = 20`; las ventanas largas incorporan tambien el trafico previo. El
ejemplo del Pre-Mortem con 25 % de exitos lentos da burn rate 5 y no supera los
umbrales urgentes actuales. No prometer un tiempo fijo de disparo o resolucion.

Consultar el nombre `injector` en el archivo de estado y sus logs:

```bash
sudo cat /srv/chatwoot/gameday/runtime/latency.json
sudo docker logs --since 5m --tail 50 <inyector-registrado>
```

Los logs son JSON y contienen operacion normalizada, demora configurada, estado
HTTP y duracion. No registran tokens, query strings ni cuerpos. Los eventos del
controlador quedan en `/srv/chatwoot/gameday/runtime/latency-events.jsonl`.

Este ejercicio simula una dependencia lenta en el recorrido. No demuestra
saturacion de Rails: el Pre-Mortem y los 5 Porques deben distinguir esa causa
de una sobrecarga real por exceso de demanda.

## Recuperacion manual

Despues de observar y diagnosticar la degradacion:

```bash
sudo python3 /srv/chatwoot/gameday/v1/latency.py recover
```

El script comprueba que sigue siendo el mismo despliegue y que nadie modifico la
ruta. Desactiva la demora, lo que tambien libera solicitudes que ya estaban
esperando, restaura exactamente la configuracion original y recarga Nginx. Luego
comprueba HTTP 200 y muestra las duraciones inicial y recuperada. No declara que
un unico resultado pruebe estabilidad o recuperacion del SLO historico.

Si no hay workers anteriores drenando, detiene y elimina solo el contenedor del
inyector. Si Nginx conserva conexiones anteriores, lo deja ejecutandose con demora
cero y emite `cleanup_deferred`; asi evita cortar conexiones durante el cierre.
La carpeta privada del ejercicio se conserva como evidencia.

En ese caso, despues de confirmar que `docker top grupo7-router -eo pid,args`
ya no muestra `worker process is shutting down`, limpiar el inyector registrado:

```bash
sudo docker stop <inyector-registrado>
sudo docker rm <inyector-registrado>
```

No hay recuperacion automatica ni temporizador. Un error o la perdida de SSH
requiere reconectarse y ejecutar `recover` con la misma copia de los scripts.
Si falla la comprobacion de recuperacion, revisar los logs y repetir `recover`
tras corregir la causa. No sobrescribir una ruta cambiada por otro despliegue.

Mantener trafico comparable durante al menos cinco minutos, verificar latencia
nominal y acceso funcional, y revisar por separado alertas y notificaciones
`resolved`. El presupuesto consumido permanece. El ensayo real de enrutamiento,
tiempos y alertas en la VM sigue siendo necesario antes de presentar.
