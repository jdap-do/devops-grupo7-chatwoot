# Validación del dashboard de Grafana

Fecha: 2 de noviembre de 2026, 18:19 (UTC−05:00). Rama: `david/entrega3-sre-alertas`.

Se validó `observability/grafana/dashboards/chatwoot-sre.json`, con UID `chatwoot-sre-unal`, 29 paneles y 28 consultas. SHA256 del archivo: `8e20b62e4e7388ee64ea16b279216f1979c7a573e332921165ffb985e3f19d4c`.

Las herramientas utilizadas fueron Grafana 13.2.5, Prometheus 3.13.5 y Microsoft Edge automatizado mediante Playwright 1.56.1. Los servicios pertenecen al proyecto Docker aislado `devops-grupo7-sre-validation`; los tres targets consultan únicamente al generador sintético.

## Comprobaciones realizadas

Se verificó la importación del JSON actual, el UID del datasource, las variables y la correspondencia de títulos y consultas con el archivo versionado. Las 28 consultas se ejecutaron tanto en Prometheus como a través de Grafana. El navegador no registró errores de aplicación ni de las consultas del dashboard.

Se comprobaron historial parcial, respuestas 4xx clasificadas como fallas, p95 exitoso superior a 500 ms y saldos negativos. También se verificó un endpoint HTTP accesible que omite métricas: los SLOs quedaron no evaluables y la tarjeta de telemetría mostró «INCOMPLETA».

Cuando Redis conserva memoria observada sin límite configurado, el dashboard muestra «SIN LÍMITE» y omite su porcentaje de saturación. Cuando desaparecen las métricas de dependencias, sus paneles muestran ausencia de datos en lugar de éxito.

## Capturas sintéticas

- [Generador en modo saludable](dashboard/synthetic-healthy.png).
- [Degradación y presupuestos negativos](dashboard/synthetic-degraded.png).
- [Endpoint accesible sin métricas HTTP](dashboard/synthetic-telemetry-missing.png).
- [Redis sin límite de memoria](dashboard/synthetic-no-memory-limit.png).

El modo healthy describe la generación actual; los indicadores y presupuestos conservan los eventos anteriores de sus ventanas. La recuperación no borra el consumo histórico. Todas las capturas pertenecen a la carpeta «VALIDACIÓN SINTÉTICA · Grupo 7» y no representan el despliegue real de Chatwoot.

El resumen automatizado, versiones, comprobaciones y hash se conservan en [validation-results.json](dashboard/validation-results.json). Los comandos reproducibles se describen en `observability/validation/README.md`.

## Alcance

Los paneles operan sobre métricas sintéticas compatibles con el contrato v3. No se modificaron recursos de Chatwoot ni se ejecutaron fallas sobre su instalación. La integración deberá proporcionar el datasource y las métricas reales antes de capturar las evidencias operativas del informe. Las alertas y notificaciones se implementan en su etapa correspondiente.
