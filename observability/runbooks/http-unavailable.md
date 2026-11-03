# Runbook operativo: indisponibilidad de Rails en Chatwoot

El incidente seleccionado consiste en la indisponibilidad temporal del componente Rails de Chatwoot, encargado de procesar las peticiones de la aplicación. Durante esta interrupción, el gateway permanece accesible, pero las solicitudes dirigidas a Rails pueden recibir respuestas HTTP 502 o 504, impidiendo consultar conversaciones y mensajes. Esta situación afecta la disponibilidad del servicio y consume su presupuesto de error, por lo que este runbook establece los pasos para diagnosticar la falla, recuperar el componente y verificar el restablecimiento del servicio.

## Alcance y activación

El procedimiento atiende la interrupción de Rails en el despliegue existente administrado mediante Terraform y Docker. La alerta asociada es `ChatwootAvailabilityBudgetBurn`, con severidad `page`. Una interrupción funcional comprobada permite iniciar la respuesta antes de que se active la alerta.

La alerta identifica impacto sobre la disponibilidad; no demuestra por sí sola que Rails esté detenido. La recuperación mediante `docker start` se aplica después de confirmar esa condición. Si la causa es otra, se conserva el diagnóstico y se coordina una intervención específica.

## 1. Reconocimiento y coordinación

Registrar la hora de detección con zona horaria, la alerta recibida, las operaciones afectadas y la revisión del despliegue. Asignar un responsable de coordinación para mantener el registro y comunicar el estado al equipo, y un responsable técnico para diagnosticar y recuperar el servicio. Una misma persona puede asumir ambos roles dejando constancia.

Suspender los cambios ajenos a la recuperación. Mantener una cronología de síntomas, hipótesis, comandos ejecutados, resultados y decisiones. Coordinar las intervenciones para evitar modificaciones simultáneas sobre el mismo componente.

## 2. Preparación del diagnóstico

Usar una terminal PowerShell con acceso al Docker del despliegue afectado y una credencial autorizada para consultar una operación cubierta por el SLI. Completar los parámetros con los valores del entorno real:

```powershell
$RailsContainer = '<contenedor de Rails>'
$GatewayContainer = '<contenedor del gateway>'
$ReadUrl = '<URL de una operación autenticada de lectura a través del gateway>'
$PrometheusUrl = '<URL local de Prometheus>'
$GrafanaUrl = '<URL local de Grafana>'
$AlertmanagerUrl = '<URL local de Alertmanager>'
$Headers = @{ api_access_token = $env:CHATWOOT_API_TOKEN }
```

La credencial se obtiene de la configuración local autorizada; no se incorpora al repositorio, al informe ni a las capturas. La operación debe consultar conversaciones, mensajes, contactos o búsquedas incluidas en el contrato, con cuenta, permisos y parámetros válidos. La página inicial y las rutas de salud no sustituyen esta comprobación.

Confirmar el contexto y los contenedores antes de intervenir:

```powershell
docker context show
docker ps -a --filter "name=$RailsContainer"
docker ps -a --filter "name=$GatewayContainer"
```

Verificar que los nombres correspondan al despliegue afectado. No se reconstruye la plataforma ni se eliminan contenedores, volúmenes o recursos Terraform durante este procedimiento.

## 3. Evaluación inicial del impacto

Consultar el dashboard `chatwoot-sre-unal` en `$GrafanaUrl` y las páginas de alertas de Prometheus (`$PrometheusUrl/alerts`) y Alertmanager. Revisar tráfico, errores, burn rate de disponibilidad, presupuesto restante y calidad de la telemetría.

Realizar una petición a la operación seleccionada y registrar la hora y el resultado:

```powershell
Get-Date -Format o
Invoke-WebRequest -Uri $ReadUrl -Headers $Headers -TimeoutSec 15 -UseBasicParsing
```

En PowerShell, una respuesta HTTP de error puede presentarse como una excepción; conservar su código y mensaje. Las respuestas 502 o 504 son compatibles con una falla del servicio de origen, pero no establecen su causa. Un rechazo por autenticación inválida exige corregir la credencial antes de usar esa petición como prueba del servicio.

Si faltan métricas, revisar también `ChatwootTelemetryMissing` y los targets de Prometheus. La ausencia de información no acredita cumplimiento ni recuperación. No esperar una alerta de latencia para actuar: este SLI evalúa únicamente respuestas exitosas.

## 4. Diagnóstico del componente afectado

Comprobar el estado exacto del contenedor y consultar los registros recientes:

```powershell
docker inspect --format '{{json .State}}' $RailsContainer
docker logs --since 15m --tail 100 $RailsContainer
docker logs --since 15m --tail 100 $GatewayContainer
```

Determinar si Rails está detenido, reiniciándose o presenta errores de arranque o conexión con sus dependencias. Conservar los registros relevantes antes de intervenir. Si el proceso continúa en ejecución, revisar también sus recursos:

```powershell
docker stats --no-stream $RailsContainer
```

Si Rails funciona pero el gateway sigue devolviendo errores, contrastar sus registros y configuración de conectividad. Si aparecen fallas de PostgreSQL o Redis, coordinar el diagnóstico de la dependencia correspondiente; este runbook no prescribe reiniciarla ni modificar sus datos.

## 5. Mitigación y recuperación

Cuando se confirme que el contenedor Rails existente está detenido y que su inicio corresponde a la recuperación del incidente, ejecutarlo nuevamente:

```powershell
docker start $RailsContainer
docker inspect --format '{{json .State}}' $RailsContainer
docker logs --since 5m --tail 100 $RailsContainer
```

Comprobar que el proceso permanezca en ejecución y que sus registros indiquen un arranque correcto. Un comando de inicio exitoso no demuestra por sí solo que Chatwoot esté disponible.

Si el contenedor vuelve a detenerse o las peticiones continúan fallando, mantener abierto el incidente, registrar el error y coordinar la corrección de la causa identificada. Evitar repetir inicios o reinicios sin evaluar sus resultados. No ejecutar `terraform destroy`, eliminar volúmenes ni modificar PostgreSQL o Redis como parte de esta mitigación.

Durante la simulación acordada, coordinar la recuperación con quien ejecuta el script de interrupción para evitar intervenciones contradictorias. Si el script termina abruptamente sin restaurar Rails, comprobar el estado y aplicar este mismo inicio manual.

## 6. Verificación del restablecimiento

Repetir la petición autenticada:

```powershell
Get-Date -Format o
$Response = Invoke-WebRequest -Uri $ReadUrl -Headers $Headers -TimeoutSec 15 -UseBasicParsing
$Response.StatusCode
```

Confirmar HTTP 200 y contenido válido para la operación consultada. Verificar además desde Chatwoot la consulta de conversaciones o mensajes. Mantener tráfico nominal durante al menos cinco minutos de observación, registrando que las nuevas peticiones funcionan y la telemetría permanece disponible.

Comprobar en Grafana la disminución de errores y del burn rate, la resolución de la alerta urgente en Prometheus y la recepción de su notificación `resolved` en el receptor de Alertmanager. La resolución puede tardar por el historial conservado en las ventanas; un HTTP 200 aislado no acredita recuperación sostenida. Si los errores reaparecen, continuar el diagnóstico.

## 7. Cierre y seguimiento

Cerrar el incidente cuando la comprobación funcional sea satisfactoria, el servicio se mantenga estable durante la observación, la telemetría sea válida y la alerta urgente se haya resuelto con notificación de cierre recibida. Si no hubo alerta por tratarse de una interrupción breve, dejar constancia y aplicar los restantes criterios.

Registrar inicio y fin, impacto, causa identificada o hipótesis pendientes, acciones realizadas, verificaciones, evidencias y responsables del seguimiento. Los avisos de consumo sostenido pueden continuar activos por el historial y deben mantenerse en seguimiento.

El restablecimiento de Rails no recupera automáticamente el presupuesto consumido. No se borran métricas ni se modifican los objetivos retrospectivamente. La reanudación de cambios ordinarios sigue la [política de Error Budget](../sre/sli-slo-budget.md): ambos saldos positivos sobre períodos evaluables, medición válida, comprobación funcional y ausencia de alertas inmediatas activas.

Si el incidente consume más del 20 % del presupuesto de cualquiera de los SLO, o lo agota, realizar un postmortem sin atribución de culpa con cronología, causas, impacto y acciones de mejora con responsables. Estimar el consumo respecto al presupuesto evaluable al inicio, identificando cobertura parcial y cambios de volumen.

## Comprobación en la simulación integrada

El escenario acordado detiene únicamente Rails, mantiene tráfico autenticado de una petición por segundo y limita la interrupción inducida a doce minutos. Exige previamente al menos sesenta minutos de tráfico nominal y cero alertas activas. Su ejecución corresponde a `observability/scripts/simulate-rails-outage.ps1`, cuya existencia y comportamiento se comprobarán en la integración.

Conservar los tiempos de detección, diagnóstico, recuperación y entrega de notificaciones, así como el commit y los parámetros del entorno. Este documento define el procedimiento; su creación no acredita la ejecución de una caída de Chatwoot real. El entorno sintético de `observability/validation/` valida reglas y notificaciones, pero no prueba estos comandos sobre el despliegue integrado.

## Referencias

- [Google SRE: Managing Incidents](https://sre.google/sre-book/managing-incidents/).
- [Contrato de SLIs, SLOs y política de Error Budget](../sre/sli-slo-budget.md).
- [Reglas de alerta implementadas](../prometheus/rules/slo-alerts.yml).
