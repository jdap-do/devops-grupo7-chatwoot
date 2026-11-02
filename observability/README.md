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
python scripts/collect-resources.py --once
docker compose --env-file .env.example -f compose.yml config --quiet
docker compose --env-file .env.example -f compose.yml up -d --build
./scripts/start-resources.ps1
```

`initialize-prober.ps1` admite `-PostgresContainer` y `-RedisContainer`. Consulta sus credenciales existentes sin imprimirlas y genera `.env.prober`, excluido de Git. No sobrescribe una configuración existente. El prober utiliza las credenciales del laboratorio y fuerza transacciones de solo lectura en PostgreSQL; no se implementó un rol separado de monitoreo.

El colector de memoria se ejecuta en el anfitrión y guarda muestras locales que el exportador lee sin acceso al socket Docker. Como alternativa al inicio en segundo plano puede ejecutarse `python scripts/collect-resources.py` en una terminal, con `--prefix` si cambia el prefijo del despliegue. No iniciar ambos modos simultáneamente. No se instala arranque automático de Windows; comprobar el colector antes de cada demostración. Su PID y registros están en `.runtime/`.

| Servicio | Dirección local |
| --- | --- |
| Gateway HTTP | http://localhost:3011 |
| Métricas HTTP | http://localhost:9101/metrics |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3005 |

Grafana usa el usuario inicial `admin` y la contraseña de `.runtime/grafana-admin-password.txt`. Su base local persiste en `grafana_data`; la contraseña inicial no debe regenerarse para resolver problemas de acceso. Prometheus persiste sus series en `prometheus_data`, con retención de 35 días. No eliminar volúmenes durante reinicios normales.

## Configuraciones y métricas

- `instrumentation/`: gateway HTTP, sondeos `SELECT 1` y `PING`, y exportador de recursos.
- `prometheus/prometheus.yml`: recolección y evaluación cada 15 segundos; jobs `chatwoot-http`, `chatwoot-dependencies` y `chatwoot-resources`.
- `prometheus/rules/`: ubicación de reglas SRE al integrarlas.
- `prometheus/adapters/`: ubicación de adaptaciones adicionales al integrarlas.
- `grafana/provisioning/`: datasource Prometheus y carga de dashboards desde archivos.
- `grafana/dashboards/`: ubicación de los JSON del dashboard al integrarlos.
- `scripts/`: arranque local, recolección de memoria y validaciones.

El datasource se llama `Prometheus UNAL`, tiene UID `prometheus-unal` y consulta `http://prometheus:9090`. Los dashboards deben referenciar ese UID. En esta versión todavía no se incluyen el dashboard final, las reglas SRE ni el runbook; no se presentan como implementados.

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
```

Las validaciones de fallos utilizan procesos aislados y no detienen la aplicación ni sus dependencias. La validación Grafana consulta el puerto predeterminado 3005; si se cambia ese puerto, se ajusta esa URL del script.

## Alcance de la medición

Los SLIs HTTP cubren únicamente tráfico que atraviesa el gateway. Se excluyen WebSockets y rutas internas de salud/métricas. La duración mide lectura de la respuesta upstream y no renderizado ni entrega de mensajes. Las respuestas se almacenan temporalmente en memoria; el gateway se utiliza para pruebas HTTP del laboratorio, no para descargas grandes o streaming.

Los sondeos de dependencias incluyen conexión y autenticación, con timeout de dos segundos. Los contadores de actividad incluyen operaciones del monitoreo. Los rollbacks PostgreSQL no equivalen automáticamente a errores. `up` indica recolección del exportador; el estado de la dependencia se consulta con `unal_dependency_probe_success` y el de sus estadísticas con `unal_dependency_collection_success`.

La memoria se calcula como working set a partir de cgroup v2. Solo se publica un límite cuando está configurado para el contenedor. Las muestras mayores de 45 segundos se omiten y se informa fallo de recolección. El porcentaje no representa toda la memoria cargada al cgroup ni garantiza ausencia de OOM.

La retención configurada no acredita 30 días de cobertura ni cumplimiento mensual de SLOs.
