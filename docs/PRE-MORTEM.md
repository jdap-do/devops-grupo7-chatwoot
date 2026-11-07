# Informe Pre-Mortem — Chatwoot

Grupo 7 — Fundamentos de DevOps y SRE, Entrega 4.

Este análisis presenta escenarios hipotéticos de falla y sus medidas de respuesta. Las estimaciones de impacto no equivalen a resultados experimentales.

## 1. Identificación y modelado de al menos dos (2) escenarios críticos de falla potencial en la plataforma.

Para la plataforma Chatwoot se identifican dos posibles escenarios que comprometen el recorrido de atención al cliente: la indisponibilidad del servicio Rails y la degradación de la latencia de las consultas. A continuación se describen los dos escenarios planteados en una situación hipotética de falla de la plataforma:

### Escenario 1. Indisponibilidad del servicio Rails activo

El contenedor Rails que recibe el tráfico deja de responder. Nginx no puede completar las solicitudes y devuelve errores, lo que impide consultar conversaciones, mensajes y contactos. PostgreSQL y Redis pueden continuar disponibles, pero la atención queda interrumpida hasta recuperar el servicio. El despliegue valida cada versión candidata y conserva la anterior. Sin embargo, una falla posterior del Rails activo puede causar indisponibilidad, porque no existe una conmutación automática hacia la otra versión.

**Propagación:** falla del Rails activo → solicitudes sin respuesta válida → errores en las consultas → interrupción de la atención.

El impacto es crítico para las operaciones dependientes de Rails. Esta falla no implica por sí sola pérdida de datos persistentes.

### Escenario 2. Degradación de latencia en las consultas

Una dependencia del recorrido de atención responde lentamente y aumenta el tiempo de las consultas de conversaciones, mensajes y contactos. Las solicitudes pueden completarse correctamente, pero una proporción supera los 500 ms establecidos como umbral de latencia. Esto retrasa la atención y consume el presupuesto de error de latencia. Si la demora provoca timeouts, también puede afectar la disponibilidad.

**Propagación:** demora en una dependencia → aumento del tiempo de las consultas → respuestas superiores a 500 ms → degradación de la atención.

Para el ensayo se introduce una demora adicional controlada en las consultas reales. Esta inyección reproduce el efecto de una dependencia lenta; no demuestra saturación de Rails ni de la base de datos.

El impacto es alto para la consulta de conversaciones, mensajes y contactos, y puede evolucionar hacia indisponibilidad si se agotan los recursos o se superan los tiempos de espera.

## 2. Análisis de causas raíz hipotéticas aplicando la técnica de los 5 Porqués.

### Escenario 1. Indisponibilidad del servicio Rails activo

1. ¿Por qué se interrumpe la atención? Porque las solicitudes a la aplicación no reciben una respuesta válida.
2. ¿Por qué no reciben una respuesta válida? Porque el proceso Rails que recibe el tráfico ha dejado de responder.
3. ¿Por qué la falla de ese proceso interrumpe el servicio? Porque el tráfico se dirige a un único destino activo.
4. ¿Por qué no se utiliza otra versión disponible? Porque el proxy no conmuta automáticamente ante una falla del destino activo.
5. ¿Por qué la recuperación depende de una intervención? Porque el laboratorio incorpora validación y reversión de despliegues, pero no un mecanismo general de recuperación automática ante fallas durante la operación.

**Causa raíz hipotética:** dependencia de un único destino activo, sin conmutación automática ante una falla durante la operación.

### Escenario 2. Degradación de latencia en las consultas

1. ¿Por qué se retrasa la consulta de información? Porque una proporción de las respuestas supera los 500 ms.
2. ¿Por qué las respuestas superan ese tiempo? Porque una dependencia del recorrido tarda más de lo esperado.
3. ¿Por qué esa demora afecta la respuesta al usuario? Porque la consulta necesita esperar el resultado de esa dependencia.
4. ¿Por qué no se evita superar el umbral del SLO? Porque los tiempos de espera y el manejo de la degradación no garantizan una respuesta útil dentro de los 500 ms.
5. ¿Por qué esa limitación no se identificó previamente? Porque las comprobaciones funcionales no bastan para evaluar el comportamiento ante dependencias lentas y requieren ensayos específicos.

**Causa raíz hipotética:** manejo insuficiente de la demora de una dependencia dentro del recorrido de consulta.

## 3. Estimación del impacto sobre los SLIs/SLOs y el ritmo de quema del Error Budget.

Los objetivos definidos son una disponibilidad mínima del 99 % y al menos un 95 % de respuestas exitosas en un tiempo igual o inferior a 500 ms, sobre una ventana móvil de 30 días. Los presupuestos de error correspondientes son del 1 % para disponibilidad y del 5 % para latencia.

### Escenario 1. Indisponibilidad de Rails

Si todas las solicitudes elegibles fallan durante el incidente, la disponibilidad del intervalo cae al 0 %. El ritmo de consumo del presupuesto de disponibilidad sería de 100 veces el permitido: 100 % / 1 % = 100. Si no existen respuestas exitosas, el indicador de latencia de esas respuestas queda sin población evaluable.

`Burn rate = proporción de fallos / presupuesto permitido = 1 / 0,01 = 100`.

### Escenario 2. Degradación de latencia

Si el 25 % de las respuestas exitosas supera los 500 ms, el cumplimiento de latencia sería del 75 % y el ritmo de consumo sería de 5 veces el permitido: 25 % / 5 % = 5.

Si todas las respuestas exitosas superan el umbral, el ritmo sería de 20 veces. La disponibilidad puede mantenerse mientras las solicitudes finalicen correctamente; si aparecen errores o timeouts, también se consume su presupuesto.

Estos valores son estimaciones para los intervalos afectados. El resultado observado depende de la duración del incidente, el volumen de solicitudes y el tráfico previo incluido en cada ventana. Los indicadores de 30 días se consideran provisionales mientras el historial esté incompleto.

`Burn rate = proporción de éxitos lentos / presupuesto permitido = 0,25 / 0,05 = 5`.

## 4. Plan de contingencia, controles preventivos y procedimientos de mitigación asociados al Runbook.

### Escenario 1: indisponibilidad de Rails

**Plan de contingencia.** Suspender los cambios ajenos a la recuperación y restablecer el contenedor de Rails afectado. Si la falla está relacionada con una actualización y no permite recuperar el servicio, retornar a la versión funcional anterior.

**Controles preventivos.** Validar la configuración, comprobar una operación autenticada antes de poner la nueva versión en servicio y probar el procedimiento de reversión.

**Procedimientos de mitigación asociados al runbook.** Aplicar el [runbook de indisponibilidad de Rails de la Entrega 3](../observability/runbooks/http-unavailable.md): revisar el estado y los logs del contenedor y, si se confirma que está detenido, iniciar el mismo contenedor. Si una configuración incompatible impide su arranque, recuperar la versión anterior; esta variante deberá incorporarse y probarse en el runbook.

Verificar una consulta autenticada con respuesta HTTP 200 y contenido esperado, comprobar el acceso a conversaciones y observar estabilidad durante al menos cinco minutos con tráfico nominal. La resolución de la alerta puede tardar por el historial de sus ventanas.

### Escenario 2: degradación de latencia

**Plan de contingencia.** Contener la carga no esencial para priorizar las consultas de atención y disponer de una reversión si la degradación está relacionada con un cambio reciente.

**Controles preventivos.** Realizar pruebas de capacidad y ajustar la concurrencia y los tiempos de espera según los resultados, evitando acumular más trabajo del que puede atenderse oportunamente.

**Procedimientos de mitigación asociados al runbook.** Revisar latencia, tráfico, errores, recursos y dependencias para identificar el origen. Según el diagnóstico, reducir carga no esencial o revertir el cambio responsable. En una inyección controlada, retirar la demora. Comprobar que las consultas recuperan su latencia nominal bajo una carga comparable y observar estabilidad durante al menos cinco minutos.

El procedimiento de inyección, diagnóstico y recuperación de latencia está implementado y documentado en [delivery4/gameday/LATENCY.md](../delivery4/gameday/LATENCY.md). Su validación en la VM y las evidencias de ejecución quedan pendientes de confirmación.

En ambos escenarios se registrarán las acciones y sus resultados. Si se agota algún presupuesto de error, se congelarán los cambios no críticos y se priorizará la recuperación.
