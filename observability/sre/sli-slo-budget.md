# Marco SRE de Chatwoot: SLIs, SLOs y presupuesto de error

Fecha de revisión: 2 de noviembre de 2026. Grupo 7.

Este documento define los indicadores, objetivos y política de Error Budget de la integración de Chatwoot. La guía metodológica es Google SRE. El laboratorio tiene pocos usuarios simultáneos e historial parcial; los resultados disponibles no acreditan 30 días de cumplimiento.

## 1. Autoridad y decisiones de diseño

Se adoptan indicadores basados en eventos buenos sobre eventos elegibles [G1]. Para disponibilidad se excluyen únicamente redirecciones y errores confirmados del cliente; para latencia se distinguen respuestas exitosas y fallidas [G3]. Las fuentes se aplican al alcance declarado y no se presentan sus ejemplos como reglas universales.

Se fijan como compromisos del laboratorio disponibilidad de al menos 99 % y al menos 95 % de respuestas exitosas completadas en 500 milisegundos o menos, sobre 30 días móviles. Son decisiones del equipo para este entorno, no umbrales universales de Google ni capacidades garantizadas por la prueba de laboratorio. Se conserva el percentil 95 como representación de latencia y se usa el conteo directo por umbral para el presupuesto.

## 2. Recorrido de usuario y población

El recorrido de usuario acordado es «un agente consulta la información necesaria para atender una conversación». Su cobertura HTTP comprende estas operaciones de lectura autenticada, verificadas en `config/routes.rb`: `GET /api/v1/accounts/{account_id}/conversations`, `GET /api/v1/accounts/{account_id}/conversations/search`, `GET /api/v1/accounts/{account_id}/conversations/{conversation_id}/messages` y `GET /api/v1/accounts/{account_id}/contacts`. Los identificadores se resuelven con datos de laboratorio; no se añaden a las etiquetas. Se admite la query string de paginación o búsqueda sin usarla como etiqueta.

El gateway clasificará el método y la ruta antes de contactar Rails; así, una conexión fallida para una operación cubierta sigue produciendo un evento medible. El contador y el histograma registrarán exactamente las mismas solicitudes completadas de este alcance, cada una una sola vez, incluidos sus códigos `2xx`, `3xx`, `4xx` y `5xx`. Se excluyen otras rutas, recursos estáticos, healthchecks, tráfico directo a Rails, WebSocket y tareas asíncronas. Las métricas describen este recorrido, no todas las funcionalidades de Chatwoot.

Para disponibilidad se exige la etiqueta `availability_result`, con valores `good`, `bad` y `excluded`, asignada de forma coherente al contador y a todas las series del histograma. `good` identifica respuestas exitosas 2xx. `bad` identifica 5xx, 429 por saturación que rechaza tráfico legítimo, otros 4xx atribuibles al servicio y 4xx cuya responsabilidad exclusiva del cliente no se haya confirmado. `excluded` identifica redirecciones y únicamente errores 4xx confirmados como responsabilidad del cliente.

La atribución debe proceder de la aplicación o de un contrato de validación verificable, no solo del código HTTP ni de una cabecera arbitraria enviada por el cliente. Por ejemplo, un 401 por token incorrecto confirmado puede excluirse; un 401 por una configuración defectuosa del servicio cuenta como fallo. Un 429 de cuota exclusivamente imputable a un cliente puede excluirse si se confirma su causa, mientras que el de saturación y el de causa desconocida cuentan como fallos. La instrumentación es responsable de clasificar; PromQL no puede recuperar esa causa desde `status_class="4xx"`.

Los eventos elegibles de disponibilidad son `good` y `bad`, los buenos son `good` y los malos son `bad`. Los excluidos permanecen visibles como diagnóstico y no mejoran el indicador. Los casos de referencia para integrar el clasificador están en `observability/contracts/fixtures/availability-classification.yml`. El alcance de las operaciones no cambia.

Para latencia, la población es únicamente la de respuestas exitosas `2xx`: buenas si su duración es menor o igual a 0.5 segundos, malas si la supera. Los eventos `bad`, incluidos los 4xx atribuibles al servicio, tienen distribución de latencia separada y consumen presupuesto de disponibilidad. No se incluyen errores rápidos para mejorar artificialmente el p95 de respuestas exitosas [G3]. La instrumentación base conserva la misma población para contador e histograma, pero cada SLI aplica sus propios filtros documentados.

Las series son `unal_chatwoot_http_requests_total` y el histograma clásico `unal_chatwoot_http_request_duration_seconds`, con etiquetas `project="devops-grupo7"`, `environment="lab"`, `method`, `status_class` y `availability_result`. Los buckets son `0.05`, `0.1`, `0.25`, `0.5`, `1`, `2.5`, `5`, `10` y `+Inf`, en segundos. El gauge `unal_chatwoot_http_in_flight_requests` aporta concurrencia del recorrido. Las combinaciones se inicializan en cero; falta de series no significa cero errores.

El gateway aplica un deadline total upstream de 5 segundos. Ese límite de protección no es una meta de rendimiento. La configuración estática de SQL y de los middlewares tampoco permite deducir el tiempo normal ni el peor caso integral de una petición.

## 3. Disponibilidad: concepto, fórmula y consulta

Para `W = (t - 30 días, t]`, se define `N_A(W)` como eventos clasificados good o bad; `G_A(W)` como eventos good; `M_A(W)` como eventos bad. Los códigos excluidos no aumentan el numerador ni el denominador.

```text
N_A = N_good + N_bad
SLI_disponibilidad = N_good / (N_good + N_bad) = 1 - M_A / N_A
SLO_disponibilidad: SLI_disponibilidad >= 0.99
```

```promql
(
  sum by (project, environment) (increase(unal_chatwoot_http_requests_total{project="devops-grupo7",environment="lab",availability_result="good"}[30d]))
  /
  sum by (project, environment) (increase(unal_chatwoot_http_requests_total{project="devops-grupo7",environment="lab",availability_result=~"good|bad"}[30d]))
)
and on (project, environment)
(sum by (project, environment) (increase(unal_chatwoot_http_requests_total{project="devops-grupo7",environment="lab",availability_result=~"good|bad"}[30d])) > 0)
```

El resultado es una razón entre cero y uno; su porcentaje multiplica por 100. Los errores 502/504 permanecen en el denominador como intentos fallidos. Si no hay eventos good o bad, no existe disponibilidad evaluable. Si el gateway deja de medir, la consulta histórica no prueba disponibilidad durante ese intervalo.

### Justificación del objetivo

El 99 % expresa una tolerancia agregada máxima del 1 % de errores del servidor en el recorrido del agente. Sobre 10 000 eventos elegibles permite 100 fallas. Se propone para el laboratorio académico de uso limitado y conserva el compromiso inicial del equipo; no se deriva matemáticamente de disponer de un solo servidor ni constituye una promesa comercial.

La lectura de conversaciones y mensajes es necesaria para atender al cliente. Las solicitudes inválidas y redirecciones no deben mejorar su tasa de atención exitosa. La capacidad de cumplir la meta se contrastará con tráfico autenticado y fallas controladas. El margen no se incrementará retrospectivamente para ocultar incumplimientos. Se revisará si el impacto observado exige mayor confiabilidad.

## 4. Latencia: concepto, fórmula y consultas

La latencia mide la duración desde recepción hasta finalización en el gateway. El p95 es el umbral dentro del cual termina aproximadamente el 95 % de las respuestas exitosas; no es promedio ni máximo absoluto. Se define `N_L(W)` como total de respuestas 2xx y `F(W)` como aquellas cuya duración es menor o igual a 0.5 segundos.

```text
SLI_percentilar = p95(duraciones de respuestas 2xx)
SLO_percentilar: p95 <= 0.5 segundos
Proporcion_buena_latencia = F / N_L
Objetivo de eventos: F / N_L >= 0.95
Eventos malos de latencia: M_L = N_L - F
```

La consulta percentilar en segundos es:

```promql
histogram_quantile(0.95,
  sum by (project, environment, le) (increase(unal_chatwoot_http_request_duration_seconds_bucket{project="devops-grupo7",environment="lab",status_class="2xx",availability_result="good"}[30d]))
)
```

El cumplimiento directo del umbral se calcula mediante:

```promql
(
  sum by (project, environment) (increase(unal_chatwoot_http_request_duration_seconds_bucket{project="devops-grupo7",environment="lab",status_class="2xx",availability_result="good",le="0.5"}[30d]))
  /
  sum by (project, environment) (increase(unal_chatwoot_http_request_duration_seconds_count{project="devops-grupo7",environment="lab",status_class="2xx",availability_result="good"}[30d]))
)
and on (project, environment)
(sum by (project, environment) (increase(unal_chatwoot_http_request_duration_seconds_count{project="devops-grupo7",environment="lab",status_class="2xx",availability_result="good"}[30d])) > 0)
```

El percentil desde histograma se estima por interpolación; para el presupuesto se usa el bucket exacto de 0.5 segundos [P1]. Los errores rápidos se muestran con una distribución separada de eventos bad y no mejoran el p95 exitoso. Si no existen respuestas exitosas, latencia se muestra no evaluable; disponibilidad sigue reflejando las fallas cuando existan eventos bad.

### Justificación del objetivo y validación

Se asignan 500 milisegundos al componente HTTP para favorecer lecturas interactivas oportunas en un laboratorio con pocos usuarios. Es una exigencia elegida para el servicio, no una cifra derivada de timeouts o una capacidad ya medida. El p95 admite hasta 5 % de respuestas exitosas más lentas; p99 y máximo acompañan el diagnóstico de esa cola. La experiencia completa del navegador queda fuera de este SLI.

Google orienta las metas hacia necesidades de usuarios y su revisión con evidencia [G1, G2]. La coincidencia con el ejemplo de 500 ms de [G2] no valida automáticamente ese tiempo para Chatwoot. El equipo debe comprobarlo bajo datos y concurrencia representativos y analizar mejoras antes de relajar un compromiso incumplido.

Se propone separar 5 minutos de calentamiento y medir tres intervalos de 15 minutos con mezcla documentada de las cuatro lecturas, inicialmente a una solicitud por segundo. La carga debe poder mantener solicitudes simultáneas si aparecen esperas. Se registrarán hardware, recursos, volumen de datos, mezcla, concurrencia, muestras, errores, p50, p95, p99 y máximo; se conservarán también ejecuciones incumplidas. Estos intervalos no certifican 30 días. El calentamiento que pase por el gateway sigue dentro del SLI global.

## 5. Presupuestos independientes

Para cada objetivo `S`, con su propia población `N` y eventos malos `M`:

```text
b = 1 - S
B = b * N                          # presupuesto permitido en eventos
q = M / N                          # fraccion mala
C = q / b                          # fraccion del presupuesto consumida
R = 100 * (1 - C)                  # saldo restante porcentual
```

Para disponibilidad: `S = 0.99`, `b = 0.01`, `N = N_A`, `M = M_A`. Para latencia: `S = 0.95`, `b = 0.05`, `N = N_L`, `M = M_L`. Los denominadores son distintos; no se compensan los dos presupuestos ni se convierten en minutos de caída. Los saldos se actualizan al evaluar las muestras; con recolección y evaluación previstas cada 15 segundos no constituyen observación instantánea continua.

Saldo de disponibilidad, en porcentaje:

```promql
(100 * (1 - (
  sum by (project, environment) (increase(unal_chatwoot_http_requests_total{project="devops-grupo7",environment="lab",availability_result="bad"}[30d]))
  /
  sum by (project, environment) (increase(unal_chatwoot_http_requests_total{project="devops-grupo7",environment="lab",availability_result=~"good|bad"}[30d]))
) / 0.01))
and on (project, environment)
(sum by (project, environment) (increase(unal_chatwoot_http_requests_total{project="devops-grupo7",environment="lab",availability_result=~"good|bad"}[30d])) > 0)
```

Saldo de latencia, en porcentaje:

```promql
(100 * (1 - (1 - (
  sum by (project, environment) (increase(unal_chatwoot_http_request_duration_seconds_bucket{project="devops-grupo7",environment="lab",status_class="2xx",availability_result="good",le="0.5"}[30d]))
  /
  sum by (project, environment) (increase(unal_chatwoot_http_request_duration_seconds_count{project="devops-grupo7",environment="lab",status_class="2xx",availability_result="good"}[30d]))
)) / 0.05))
and on (project, environment)
(sum by (project, environment) (increase(unal_chatwoot_http_request_duration_seconds_count{project="devops-grupo7",environment="lab",status_class="2xx",availability_result="good"}[30d])) > 0)
```

Sobre 10 000 eventos elegibles de disponibilidad, con 40 errores queda 60 % del presupuesto; con 100 queda cero; con 120 queda -20 %. En este ejemplo ya se excluyeron redirecciones y errores confirmados del cliente; los 4xx del servicio permanecen en el total.

Sobre 10 000 respuestas exitosas evaluables para latencia, con 200 superiores a 0.5 segundos queda 60 %; con 500 queda cero; con 600 queda -20 %. Estos datos son ilustrativos y no son resultados del proyecto.

Como comprobación de exclusiones: 900 respuestas good, 90 respuestas 4xx confirmadas como errores del cliente y 10 respuestas bad producen una disponibilidad de `900 / 910 = 98.9011 %`, no 99 %. Si 855 de las 900 respuestas exitosas cumplen 0.5 segundos, el cumplimiento de latencia es 95 % y su saldo es cero. Los diez errores rápidos no mejoran esa proporción. Si se obtienen 990 respuestas good y 10 respuestas 429 por saturación, la disponibilidad es 99 % y su presupuesto se agota: esas diez respuestas son elegibles y fallidas.

## 6. Calidad de datos, ventana y bajo tráfico

La ventana móvil conserva el efecto de incidentes recientes. La retención propuesta de 35 días no acredita 30 días de cobertura; tampoco lo hace escribir `[30d]`. Se verifican muestras esperadas de `up`, sus fallos y huecos, además de las series obligatorias. Un target sano sin las métricas requeridas sigue siendo una pérdida de observabilidad.

Sin 30 días completos se presentan indicadores y saldos provisionales como «historial parcial», con fechas y limitaciones. Sin eventos elegibles se indica «sin tráfico evaluable». Sin 2xx se indica «sin respuestas exitosas para evaluar latencia». Una muestra ausente nunca se sustituye por un éxito. Las consultas numéricas anteriores no implementan por sí solas la certificación de cobertura.

Se aplica `increase` por serie antes de agregar, contemplando resets de contadores; su extrapolación puede dar cantidades fraccionarias. Si se pierde el almacenamiento se declara nueva cobertura parcial, sin borrar la evidencia documentada del incidente. La falta de telemetría suspende cambios no críticos como medida del laboratorio hasta restaurar la medición y revisar el impacto.

El tráfico sintético ayuda a evaluar el laboratorio con pocos usuarios, pero puede ocultar problemas si no representa las operaciones reales. La campaña identificará su origen y alcance; si coexiste con usuarios reales se separarán las poblaciones antes de atribuir resultados a esos usuarios. No se inventan mínimos de tráfico que descarten fallas significativas [G4].

## 7. Política de presupuesto y respuesta

La política coordina desarrollo y operaciones, sin carácter punitivo [G5]. El equipo asigna responsables de evaluación e instrumentación y revisa los saldos antes de cambios y después de incidentes, documentando acciones en issues o PRs.

Con ambos presupuestos positivos y sin incidente activo se permiten cambios revisados. Ante alerta inmediata de consumo se pausan cambios no relacionados y se aplica el runbook. Si alguno de los presupuestos se agota o excede, se congelan cambios no críticos y se priorizan mitigación, restauración, seguridad y confiabilidad. Las excepciones deben registrar motivo, responsable y verificación. Tratar saldo cero como ausencia de margen es una decisión conservadora explícita del laboratorio.

Se reanudan cambios ordinarios cuando ambos saldos sean positivos sobre períodos evaluables, la medición sea válida, el servicio supere la verificación funcional y no existan alertas inmediatas activas. La decisión conjunta queda documentada. No se exige recuperar un 25 % de reserva como si fuera una recomendación de Google. En campaña parcial, las decisiones se identifican como provisionales.

La recuperación de Rails no devuelve automáticamente presupuesto: el saldo depende de eventos nuevos y eventos que salen de la ventana. No se borran métricas ni se cambian metas retrospectivamente para mostrar cumplimiento.

Todo incidente se registra. Si consume más del 20 % del presupuesto de cualquiera de los SLO, o lo agota, se redacta un postmortem sin atribución de culpa con cronología, impacto y acciones con responsables [G5, G7]. El consumo se estima respecto al presupuesto evaluable al inicio y se documentan cambios de volumen y cobertura parcial. La caída controlada se identifica como causa inducida y su tráfico no se elimina retrospectivamente.

## 8. Burn rate y circuito de alertas

```text
burn_rate(w) = fraccion_mala(w) / (1 - SLO)
```

Un factor de 1 corresponde a la tasa de errores permitida; no significa que el presupuesto ya esté agotado. Cada cálculo usa la población de su SLO.

Se adopta el esquema multiventana y multiburn rate de [G4] como punto de partida para 30 días. Para cada SLO, una alerta de atención inmediata usa `(burn_1h > 14.4 AND burn_5m > 14.4) OR (burn_6h > 6 AND burn_30m > 6)`. Una alerta de seguimiento usa `burn_3d > 1 AND burn_6h > 1`. Se conservan los nombres `ChatwootAvailabilityBudgetBurn` y `ChatwootLatencyBudgetBurn` para atención inmediata; se añaden `ChatwootAvailabilityBudgetBurnSlow` y `ChatwootLatencyBudgetBurnSlow` para seguimiento. Cada par exige denominadores positivos en sus dos ventanas y mantiene las mismas poblaciones del SLO correspondiente.

Las alertas de burn rate no tendrán un `for: 2m` adicional: las ventanas representan persistencia y consumo. Las alertas técnicas de pérdida de telemetría pueden conservar su persistencia local de 2 minutos; no sustituyen alertas SLO. Los factores se aplican a `0.01` para disponibilidad y `0.05` para latencia, no al `0.001` del ejemplo de un SLO del 99.9 %. Por ejemplo, 14.4 equivale a 14.4 % de fallas de disponibilidad o 72 % de respuestas exitosas lentas. Las cifras se comprobarán con fixtures; el 72 % explica por qué también se exige seguimiento de consumo lento.

Se documentarán precisión, detección, recuperación y sensibilidad al bajo tráfico. La referencia de 2 %, 5 % y 10 % de consumo corresponde a la relación entre ventanas de alerta y 30 días bajo volumen comparable; no es una garantía del consumo real cuando el tráfico varía o el historial es parcial. No se exigirá un mínimo arbitrario de eventos que oculte fallas. En el laboratorio se generará tráfico representativo controlado y se declarará su naturaleza sintética.

Prometheus se conecta con Alertmanager y un receptor webhook local con registro persistente de entrega. Se configuran agrupación, severidades y supresión de la notificación de seguimiento cuando ya exista la inmediata del mismo SLO. La validación comprende notificaciones de activación y resolución; ver una regla activa no basta.

El runbook declara impacto, coordinación y responsable técnico, registra acciones, diagnostica, mitiga, comprueba recuperación y documenta seguimiento [G6]. Su aplicación se adapta al equipo real de dos integrantes.

## 9. Validación e integración

La integración utiliza la clasificación `availability_result`. La instrumentación se verificó para las cuatro lecturas autenticadas, la coherencia de contadores e histogramas, las respuestas 502/504, el deadline total, las exclusiones y el bucket 0.5. Las reglas y paneles aplican el mismo alcance y las poblaciones de cada SLO.

Los escenarios sintéticos comprueban cumplimiento, errores rápidos, éxito lento, exclusiones confirmadas, 429 por saturación, 4xx sin atribución confirmada, cero tráfico, ausencia de 2xx, pérdida de métricas, resets, límites y recuperación. Las pruebas de reglas cubren los tres pares de ventanas y la ausencia de `for` en burn rate. Se verificaron las reglas con promtool y las consultas del dashboard a través de Grafana. Estas pruebas aisladas se distinguen del incidente ejecutado sobre Chatwoot real.

La simulación sobre Chatwoot se ejecutó con diez minutos nominales previos y una detención programada de Rails de 180 segundos, manteniendo el generador de tráfico activo. El procedimiento solicitó el arranque del mismo contenedor en su bloque de recuperación; se conservaron PostgreSQL, Redis, volúmenes y estado Terraform. Se verificaron la recuperación funcional, la activación de las alertas de disponibilidad y la entrega del aviso de resolución de la alerta urgente. El comportamiento observado corresponde al historial parcial y al volumen real de solicitudes completadas durante la prueba; no garantiza el mismo tiempo de activación con otro historial o carga.

El informe de entrega conserva las capturas y la cronología del incidente. Las evidencias aisladas con datos sintéticos no sustituyen esa validación de integración ni acreditan 30 días completos de cobertura.

## 10. Referencias

- [G1] Google SRE, Implementing SLOs: https://sre.google/workbook/implementing-slos/
- [G2] Google Cloud, Setting SLOs: a step-by-step guide: https://cloud.google.com/blog/products/management-tools/practical-guide-to-setting-slos
- [G3] Google SRE, Monitoring Distributed Systems: https://sre.google/sre-book/monitoring-distributed-systems/
- [G4] Google SRE, Alerting on SLOs: https://sre.google/workbook/alerting-on-slos/
- [G5] Google SRE, Example Error Budget Policy: https://sre.google/workbook/error-budget-policy/
- [G6] Google SRE, Managing Incidents: https://sre.google/sre-book/managing-incidents/
- [G7] Google SRE, Postmortem Culture: https://sre.google/sre-book/postmortem-culture/
- [P1] Prometheus, histogramas: https://prometheus.io/docs/practices/histograms/
- [P2] Prometheus, pruebas de reglas: https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/

Las reglas están en `observability/prometheus/rules/slo-recording.yml`; las pruebas en `observability/prometheus/tests/slo.test.yml`; su ejecución y las series resultantes se describen en `observability/validation/README.md`. La cobertura de la ventana se expresa mediante `unal_chatwoot:slo_history_coverage:ratio30d` y `unal_chatwoot:slo_window_complete:bool30d`, basadas en las evaluaciones válidas de la instrumentación.
