# Validación independiente de cálculos SRE

Se implementan las recording rules, sus pruebas sintéticas y la clasificación de referencia del contrato v3. No es necesario ejecutar Chatwoot, disponer de credenciales ni acceder al equipo donde se integrará la infraestructura.

## Herramienta fijada

Las validaciones se ejecutan con **promtool 3.13.5**, incluido en Prometheus 3.13.5 LTS. Se obtiene desde la [distribución oficial](https://prometheus.io/download/). La selección fija la herramienta de prueba; no supone que la pila final ya utilice esa versión. La integración deberá usar la misma versión para reproducir estos resultados.

El ZIP oficial para Windows amd64 tiene SHA256 `846398b50b90e02f69960342190a1d01bf9a335b3aeee69bfd6ead41d3a314c5`. El ejecutable y las descargas se conservan fuera de los archivos versionados. No se modifica la política de ejecución del equipo ni se inicia un servidor con estos comandos.

Desde la raíz del worktree, con `promtool` disponible en PATH:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File observability/validation/validate-slo.ps1
```

Si el ejecutable se encuentra en otro directorio:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File observability/validation/validate-slo.ps1 -PromtoolPath ./tmp/prometheus-tools/promtool.exe
```

La opción de ejecución se limita a ese proceso. También es posible ejecutar directamente:

```text
promtool check rules observability/prometheus/rules/slo-recording.yml
promtool test rules observability/prometheus/tests/slo.test.yml
```

## Clasificación requerida a la instrumentación

Los contadores HTTP y todas las series del histograma conservan `method` y `status_class` y añaden **`availability_result`**. La clasificación se asigna una sola vez en la fuente, antes de incrementar ambos tipos de métrica; las reglas no intentan deducir causas a partir de la familia `4xx`.

`good` identifica una respuesta exitosa 2xx. `bad` identifica una falla del servicio: 5xx, 429 por saturación, otros 4xx atribuibles al servicio o 4xx cuya responsabilidad exclusiva del cliente no pueda demostrarse. `excluded` identifica redirecciones y 4xx confirmados como responsabilidad exclusiva del cliente.

La atribución debe provenir de la aplicación o de un contrato de validación comprobable para la operación. Un código 400, 401, 404 o 429 por sí solo no demuestra esa atribución. Una cuota explícita superada por un cliente abusivo puede excluirse si se confirma esa causa; un rechazo de tráfico legítimo por capacidad insuficiente es un fallo. No se acepta como autoridad una cabecera arbitraria enviada por el cliente. Los casos de referencia están en `contracts/fixtures/availability-classification.yml`.

Las reglas no implementan el clasificador del gateway: este pertenece a la instrumentación. Los escenarios promtool suponen que la clasificación ya fue asignada y prueban su tratamiento matemático. La integración debe ejecutar los casos de referencia contra la instrumentación real, especialmente 429 y dos respuestas del mismo código con causas diferentes.

Cada target del job `chatwoot-http` debe exponer `project`, `environment`, `job`, `instance`, contadores `good` y `bad`, y el histograma exitoso con sus buckets contratados. Las series esperadas se inicializan en cero aunque todavía no existan eventos. Un contrato antiguo sin la nueva etiqueta no tiene compatibilidad silenciosa: los resultados SLO quedan ausentes por calidad de datos insuficiente.

## Resultados disponibles para Grafana y alertas

`unal_chatwoot:slo_sli:ratio` devuelve el cumplimiento entre 0 y 1. `unal_chatwoot:slo_error:ratio` devuelve la fracción mala. `unal_chatwoot:slo_burn_rate:ratio` la divide entre el presupuesto permitido. Estas series incluyen `project`, `environment`, `slo` y `window`; las ventanas son `5m`, `30m`, `1h`, `6h`, `3d` y `30d`.

`unal_chatwoot:slo_budget_remaining:ratio` y `unal_chatwoot:slo_budget_consumed:ratio` corresponden a `window="30d"`. Para presentarlas como porcentaje se multiplican por 100 o se utiliza la unidad de Grafana que interpreta razones entre 0 y 1. El saldo negativo se conserva y no debe recortarse en el panel.

`unal_chatwoot:http_request_duration:p95_seconds` ofrece p95 de `availability_result="good"` y `"bad"` por separado, con ventanas `5m` y `30d`. El resultado está en segundos. `unal_chatwoot:http_requests:rate5m` ofrece solicitudes por segundo separadas por clase y clasificación, incluidos eventos excluidos del SLI.

`unal_chatwoot:http_telemetry_valid:ratio` solo ofrece un resultado 1 cuando todos los targets HTTP están accesibles y contienen las series mínimas requeridas. Una réplica incompleta no queda oculta por otra sana. Los cocientes y percentiles se suprimen si falta esa condición; los denominadores cero también se suprimen. La ausencia no debe convertirse en cero errores ni en cumplimiento del 100 %.

`unal_chatwoot:slo_history_coverage:ratio30d` contabiliza las evaluaciones válidas respecto de las 172 800 esperadas en 30 días a intervalos de 15 segundos. `unal_chatwoot:slo_window_complete:bool30d` indica 1 únicamente al alcanzar esa cobertura. El dashboard debe mostrar «historial parcial» cuando no sea 1. La cobertura comienza cuando se evalúa esta regla; no se infiere de la edad del proceso ni solo del historial de `up`. No se cambian intervalos sin adaptar el cálculo y sus validaciones.

## Alcance de las pruebas

Los escenarios comprueban tráfico sano, exclusión de errores del cliente y redirecciones, fallas 4xx válidas, ausencia de tráfico o éxitos, lentitud, presupuestos positivos/cero/negativos, reinicios, recuperación, pérdida de métricas y aislamiento por entorno. Las réplicas se agregan por sus eventos, sin promediar sus porcentajes. Los histogramas sintéticos permiten verificar que los errores rápidos no mejoran el p95 exitoso.

La comprobación usa el motor real de PromQL de promtool. No acredita instrumentación de Chatwoot, cumplimiento mensual ni reglas de alerta desplegadas. El dashboard consume estas series y se comprueba separadamente con el entorno descrito a continuación.

## Entorno aislado del dashboard

El archivo `observability/validation/compose.yml` inicia Grafana 13.2.5, Prometheus 3.13.5 y un generador sintético. Se utiliza el proyecto Docker `devops-grupo7-sre-validation`, una red propia y volúmenes propios. No se conecta a Chatwoot, PostgreSQL o Redis reales ni utiliza el socket Docker dentro de contenedores.

Desde la raíz del worktree:

```powershell
docker compose -f observability/validation/compose.yml up -d --build
```

Grafana queda disponible en `http://127.0.0.1:13005/d/chatwoot-sre-unal`, Prometheus en `http://127.0.0.1:19090` y el control de escenarios en `http://127.0.0.1:18091/scenario`. Los puertos se pueden cambiar mediante `VALIDATION_GRAFANA_PORT`, `VALIDATION_PROMETHEUS_PORT` y `VALIDATION_METRICS_PORT`. Todos se publican exclusivamente en localhost.

La instancia de validación permite acceso anónimo de lectura y no necesita credenciales reales. El dashboard se importa automáticamente en la carpeta **VALIDACIÓN SINTÉTICA · Grupo 7**, con el datasource de UID `prometheus-unal`. Esa configuración de acceso pertenece exclusivamente a este entorno de prueba.

El proveedor revisa los archivos cada 30 segundos mediante polling para detectar cambios de JSON en montajes de Docker Desktop que no propagan eventos de filesystem. Las modificaciones deben realizarse en el archivo versionado.

El generador utiliza Python 3.13.11 y prometheus-client 0.23.1. Produce diez eventos HTTP ficticios por segundo y un sondeo ficticio por dependencia cada 15 segundos. No ejecuta diez peticiones reales contra Chatwoot ni mide su capacidad. Sus contadores y duraciones se construyen para ejercitar los paneles del contrato v3.

## Escenarios disponibles

`healthy` genera respuestas exitosas con una pequeña fracción de respuestas lentas y rechazos confirmados del cliente. `degraded` añade eventos 4xx bad que representan saturación, errores 5xx, respuestas exitosas lentas y mayor utilización de recursos. `telemetry_missing` mantiene accesible el endpoint HTTP de métricas, pero omite las series obligatorias. `no_memory_limit` conserva memoria observada para Redis y omite su límite. `dependencies_missing` omite las métricas de dependencias manteniendo accesible su endpoint.

Para cambiar de escenario:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:18091/scenario -ContentType application/json -Body '{"scenario":"degraded"}'
```

Para restaurar el generador:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:18091/scenario -ContentType application/json -Body '{"scenario":"healthy"}'
```

Cambiar el escenario no elimina el historial ni reinicia los contadores. El efecto de una degradación permanece en las ventanas y presupuestos hasta que nuevas solicitudes o la salida de eventos de la ventana modifiquen el resultado. La actualización de métricas y reglas puede requerir varios ciclos de 15 segundos.

## Validación en un navegador real

El paquete de Node de esta carpeta es independiente de las dependencias de Chatwoot. Se utiliza Playwright 1.56.1 y Microsoft Edge instalado. Instalar desde **este directorio**, evitando ejecutar npm install con --prefix desde la raíz:

```powershell
Set-Location observability/validation
npm.cmd ci --ignore-scripts --no-audit --no-fund
node validate-dashboard-browser.mjs
Set-Location ../..
```

En Linux u otro entorno con Chromium de Playwright instalado se configura `VALIDATION_BROWSER_CHANNEL=chromium`. Si se cambian puertos, se ajustan `VALIDATION_GRAFANA_URL`, `VALIDATION_PROMETHEUS_URL` y `VALIDATION_METRICS_URL` con las URLs locales correspondientes.

El validador solo acepta URLs de localhost y comprueba que el controlador se identifique como sintético. Verifica importación, UID, variables, datasource, targets aislados y todas las consultas mediante Prometheus y Grafana. Luego abre el dashboard y comprueba degradación, presupuesto negativo, falta de métricas con endpoint sano, límite de memoria ausente y dependencias sin datos. Al terminar restaura el escenario healthy, conservando el consumo histórico.

Las capturas y el resumen JSON se guardan en `observability/evidence/david/dashboard/`. Son evidencia de datos sintéticos en herramientas reales, no de tráfico de usuarios o del despliegue integrado de Chatwoot. El archivo JSON del dashboard se entrega sin credenciales ni direcciones personales para integrarlo posteriormente.

Para detener el entorno y conservar sus volúmenes:

```powershell
docker compose -f observability/validation/compose.yml down
```
