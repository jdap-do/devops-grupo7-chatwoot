# Validación de recording rules SRE

Fecha: 2 de noviembre de 2026. Rama: `david/entrega3-sre-alertas`.

Se validaron 40 reglas de cálculo y 29 escenarios sintéticos con promtool 3.13.5, revisión `f497435984d1ca1d84cda5ed309387ac2eb1f8f6`, plataforma Windows amd64. El binario se obtuvo de la distribución oficial y el SHA256 del archivo descargado coincidió con el publicado. Los archivos están en el árbol de trabajo; esta evidencia no corresponde todavía a un commit publicado ni a una ejecución de CI.

## Comandos y resultado

```text
promtool check rules observability/prometheus/rules/slo-recording.yml
  SUCCESS: 40 rules found

promtool test rules observability/prometheus/tests/slo.test.yml
  SUCCESS
```

También se ejecutó correctamente `observability/validation/validate-slo.ps1`, que comprueba la versión y finaliza con error si cualquiera de las verificaciones falla.

## Comportamiento comprobado

Los errores confirmados del cliente y las redirecciones no mejoran disponibilidad. Un evento 4xx clasificado como fallo del servicio, incluido el escenario de 429 por saturación, permanece en el denominador y consume presupuesto. Los 4xx sin atribución confirmada al cliente se tratan como fallos. La clasificación se recibe mediante `availability_result`; estas pruebas no deducen ni validan la causa desde el código HTTP.

Se comprobaron presupuestos positivos, agotados y negativos, respuestas exitosas lentas y separación de errores rápidos. El burn rate utiliza el presupuesto propio de cada SLO en las seis ventanas definidas. Se verificaron ausencia de tráfico o respuestas exitosas, targets caídos o ausentes, series faltantes o stale, valores de clasificación inválidos, reinicios de contadores y recuperación reciente con consumo histórico conservado.

Los eventos de otro entorno no alteran los indicadores del laboratorio. Las réplicas se agregan por sus solicitudes y una réplica incompleta invalida la evaluación. Un historial breve no certifica la ventana de 30 días y cero observaciones no produce un percentil satisfactorio.

## Alcance

La comprobación ejecutó el motor de PromQL de promtool con series sintéticas. No se desplegaron Prometheus, Grafana ni Alertmanager, no se modificó Chatwoot y no se provocaron incidentes reales. La instrumentación deberá implementar el contrato v3 y ejecutar los casos de `contracts/fixtures/availability-classification.yml` antes de integrar. Las reglas de alertas y el dashboard se desarrollarán sobre estas series en sus respectivas etapas.
