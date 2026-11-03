# Observabilidad de Chatwoot

Configuraciones de monitoreo de la Entrega 3. La aplicación existente continúa gestionada por Terraform; este Compose añade instrumentación HTTP, sondeos de dependencias, métricas de memoria, Prometheus y Grafana sin sustituir sus recursos.

## Requisitos

- Docker Desktop con contenedores Linux y Docker Compose compatible con `env_file.format: raw`.
- PowerShell y Python 3 en el anfitrión.
- Chatwoot, PostgreSQL y Redis desplegados y conectados a una red Docker existente.
- cgroup v2 para las lecturas de memoria implementadas.

Las variables sin secretos están en `.env.example`. Los nombres predeterminados corresponden al laboratorio `devops-grupo7-e2`; se ajustan a cada entorno. No publicar configuraciones locales, contraseñas ni archivos de `.runtime/`.

## Arranque

Desde `observability/`, con la aplicación existente activa:

```powershell
./scripts/initialize-grafana.ps1
./scripts/initialize-prober.ps1
./scripts/initialize-client.ps1
python scripts/collect-resources.py --once
docker compose --env-file .env.example -f compose.yml config --quiet
docker compose --env-file .env.example -f compose.yml up -d --build
./scripts/start-resources.ps1
```

Si Windows PowerShell bloquea la ejecución de scripts locales, se puede invocar cada archivo en un proceso independiente, sin cambiar la política permanente del sistema. Por ejemplo, desde este mismo directorio:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File ./scripts/initialize-grafana.ps1
```

`initialize-prober.ps1` admite `-PostgresContainer` y `-RedisContainer`. Consulta sus credenciales existentes sin imprimirlas y genera `.env.prober`, excluido de Git. No sobrescribe una configuración existente. El prober utiliza las credenciales del laboratorio y fuerza transacciones de solo lectura en PostgreSQL; no se implementó un rol separado de monitoreo.

El colector de memoria se ejecuta en el anfitrión y guarda muestras locales que el exportador lee sin acceso al socket Docker. Como alternativa al inicio en segundo plano puede ejecutarse `python scripts/collect-resources.py` en una terminal, con `--prefix` si cambia el prefijo del despliegue. No iniciar ambos modos simultáneamente. No se instala arranque automático de Windows; comprobar el colector antes de cada demostración. Su PID y registros están en `.runtime/`.

| Servicio | Dirección local |
| --- | --- |
| Gateway HTTP | http://localhost:3011 |
| Métricas HTTP | http://localhost:9101/metrics |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3005 |
| Alertmanager | http://localhost:9093 |
| Registro de notificaciones | http://localhost:3006/notifications |

Grafana usa el usuario inicial `admin` y la contraseña de `.runtime/grafana-admin-password.txt`. Su base local persiste en `grafana_data`; la contraseña inicial no debe regenerarse para resolver problemas de acceso. Prometheus persiste sus series en `prometheus_data`, con retención de 35 días. No eliminar volúmenes durante reinicios normales.

## Configuraciones y métricas

- `instrumentation/`: gateway HTTP, sondeos `SELECT 1` y `PING`, y exportador de recursos.
- `prometheus/prometheus.yml`: recolección y evaluación cada 15 segundos; jobs `chatwoot-http`, `chatwoot-dependencies` y `chatwoot-resources`.
- `prometheus/rules/`: reglas de cálculo de SLIs, SLOs, presupuestos y alertas.
- `prometheus/tests/`: escenarios de prueba de las reglas.
- `grafana/provisioning/`: datasource Prometheus y carga de dashboards desde archivos.
- `grafana/dashboards/`: dashboard operativo en formato JSON.
- `alertmanager/`: agrupación y entrega de avisos al receptor local.
- `sre/` y `runbooks/`: definiciones de confiabilidad, política de Error Budget y procedimiento de atención del incidente.
- `scripts/`: arranque local, recolección de memoria y validaciones.

El datasource se llama `Prometheus UNAL`, tiene UID `prometheus-unal` y consulta `http://prometheus:9090`. Se incluye el dashboard `chatwoot-sre-unal`, las reglas SRE y el runbook aportados en el PR 9. La instrumentación HTTP se adapta a la clasificación `availability_result` y al alcance de lecturas autenticadas definido en `sre/sli-slo-budget.md`.

La instrumentación expone las familias `unal_chatwoot_http_*`, `unal_dependency_probe_*`, `unal_dependency_probes_total`, `unal_postgres_*`, `unal_redis_commands_processed_total` y `unal_container_memory_*`. El histograma incluye el bucket de un segundo y Prometheus adapta su etiqueta a `le="1"`.

## Validación

Después de la primera recolección:

```powershell
docker compose --env-file .env.example -f compose.yml exec -T prometheus promtool check config /etc/prometheus/prometheus.yml
Get-Content scripts/validate-http.py -Raw | docker compose --env-file .env.example -f compose.yml exec -T http-gateway python -
Get-Content scripts/validate-prometheus.py -Raw | docker compose --env-file .env.example -f compose.yml exec -T http-gateway python -
Get-Content scripts/validate-dependencies.py -Raw | docker compose --env-file .env.example -f compose.yml exec -T dependency-prober python -
Get-Content scripts/validate-resources.py -Raw | docker compose --env-file .env.example -f compose.yml exec -T resource-exporter python -
python scripts/validate-grafana.py
python scripts/validate-integration.py
```

Las validaciones de fallos utilizan procesos aislados y no detienen la aplicación ni sus dependencias. La validación Grafana consulta el puerto predeterminado 3005; si se cambia ese puerto, se ajusta esa URL del script.

## Alcance de la medición

Los SLIs HTTP cubren cuatro lecturas GET a través del gateway: lista de conversaciones, búsqueda de conversaciones, mensajes de una conversación y contactos. Se excluyen recursos estáticos, otras rutas, métodos de escritura, WebSockets y rutas de salud/métricas. La query string no se usa como etiqueta. La clasificación ocurre por método/ruta antes de conectar con Rails, de modo que un fallo 502/504 sigue contabilizado. Las respuestas 2xx son `good`, las redirecciones son `excluded` y los demás fallos son `bad`. En la integración actual todos los 4xx se clasifican conservadoramente como `bad`, porque no se dispone de una prueba independiente de responsabilidad exclusiva del cliente. Ninguna cabecera enviada por el cliente puede forzar una exclusión. Los casos `client_confirmed` de los fixtures se verifican en pruebas unitarias; no se afirma que exista atribución automática completa de 4xx en producción.

La disponibilidad tiene objetivo del 99 % y la latencia exige al menos 95 % de respuestas exitosas en 500 ms o menos, en 30 días móviles, con presupuestos independientes. La duración mide lectura de la respuesta upstream y no renderizado ni entrega de mensajes. Las respuestas se almacenan temporalmente en memoria; el gateway se utiliza para pruebas HTTP del laboratorio, no para descargas grandes o streaming.

Los sondeos de dependencias incluyen conexión y autenticación, con timeout de dos segundos. Los contadores de actividad incluyen operaciones del monitoreo. Los rollbacks PostgreSQL no equivalen automáticamente a errores. `up` indica recolección del exportador; el estado de la dependencia se consulta con `unal_dependency_probe_success` y el de sus estadísticas con `unal_dependency_collection_success`.

La memoria se calcula como working set a partir de cgroup v2. Solo se publica un límite cuando está configurado para el contenedor. Las muestras mayores de 45 segundos se omiten y se informa fallo de recolección. El porcentaje no representa toda la memoria cargada al cgroup ni garantiza ausencia de OOM.

La retención configurada no acredita 30 días de cobertura ni cumplimiento mensual de SLOs.

## Tráfico y preparación del incidente

`initialize-client.ps1` lee el token existente del usuario de laboratorio y los identificadores de cuenta/conversación, sin crear usuarios ni rotar tokens. Se guardan en `.runtime/chatwoot-client.json`, fuera de Git. `python scripts/generate-traffic.py --duration 60` alterna las cuatro lecturas autenticadas con intervalo previsto de un segundo y timeout de siete segundos. No ejecuta escrituras. La raíz pública del panel ya no es tráfico elegible del SLI. Si una solicitud tarda más, disminuye la cadencia real; no se generan ráfagas para compensar retrasos. La duración del cliente no sustituye el histograma del gateway. El resumen local queda en `.runtime/traffic-*.json`, fuera de Git. Se admiten `--url` (base del gateway), `--client-file`, `--duration` (hasta 1800 segundos) y `--interval` (como mínimo un segundo).

`./scripts/simulate-rails-outage.ps1` solo comprueba la preparación por defecto: identifica el contenedor Rails, verifica HTTP 200 y consulta si está integrada la alerta `ChatwootAvailabilityBudgetBurn`. No detiene recursos. La ausencia de esa alerta impide ejecutar el modo de incidente.

El parámetro `-Execute` habilita la intervención, limitada a un máximo de 360 segundos. Se usa únicamente durante la prueba coordinada, con diez minutos nominales previos, generador de tráfico activo, observación de métricas y las reglas ya validadas. El script comprueba que no haya alertas firing y restaura el mismo contenedor en un bloque `finally`. No accede a bases ni volúmenes. Este mecanismo no garantiza recuperación ante cierre forzado del proceso o apagado del anfitrión; en ese caso se verifica el estado y se inicia manualmente el contenedor indicado. El arranque debe acompañarse de verificación HTTP, funcional y de resolución de la alerta.

El modo de intervención no está validado por ejecutar la comprobación previa. La preparación no equivale a evidencia de incidente ni a alerta activada.

## Notificaciones

Prometheus envía alertas a Alertmanager (`http://localhost:9093`), que agrupa y remite eventos firing/resolved al receptor local. El receptor integrado usa `http://localhost:3006/notifications` para consultar el registro persistente en `notifications_data`. Se trata de una demostración local; no se presenta como entrega de correo o mensajería externa. Los componentes bajo `validation/` conservan sus escenarios sintéticos aislados y no sustituyen el tráfico del servicio real.
