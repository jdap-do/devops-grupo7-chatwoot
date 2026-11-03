# Dashboard de Chatwoot

El archivo `chatwoot-sre.json` es el dashboard importable de la entrega. Usa el modelo JSON Classic, UID `chatwoot-sre-unal` y datasource Prometheus con UID `prometheus-unal`. Sus variables son `project` y `environment`, con valores iniciales `devops-grupo7` y `lab`.

## Contenido

Los primeros paneles muestran calidad de telemetría, cobertura de la ventana, disponibilidad, proporción de respuestas exitosas dentro de 500 ms, presupuestos restantes, p95 e información de concurrencia. Los objetivos son 99 % para disponibilidad y 95 % para latencia sobre 30 días móviles. La cobertura parcial se señala explícitamente; los valores de esa ventana son provisionales.

Las señales HTTP incluyen latencia exitosa y fallida separadas, tráfico, proporción de fallos, evolución del presupuesto y burn rate. Los 4xx atribuibles al servicio se distinguen de los errores confirmados del cliente mediante `availability_result`. Los primeros consumen presupuesto y los excluidos no lo mejoran.

Las dependencias muestran último resultado y p95 de sondeos, fallas de sondeo, transacciones PostgreSQL y comandos Redis. Estos sondeos no miden todas las consultas SQL ni todos los comandos reales. Los rollbacks se identifican como rollbacks. El panel de conexiones compara conexiones de Chatwoot con el máximo global del servidor, sin atribuirle capacidad exclusiva de la base.

Los paneles de recursos muestran memoria de trabajo, fracción respecto al límite y configuración de límites. Si existe consumo observado sin límite interpretable se muestra «SIN LÍMITE» y no se fabrica un porcentaje. Si no existen métricas se conserva ausencia de datos. La concurrencia HTTP no se interpreta como porcentaje de capacidad.

## Integración

Se importa el JSON en Grafana o se monta en el directorio de dashboards del proveedor de archivos. La instancia debe tener el datasource `prometheus-unal`, las recording rules del contrato v3 y las métricas de dependencias y recursos acordadas. El JSON no contiene contraseñas, direcciones del equipo ni rutas personales.

El datasource y el proveedor del entorno integrado pertenecen a su configuración de despliegue. Los archivos bajo `observability/validation/grafana/provisioning/` son exclusivamente para las pruebas aisladas y no deben sustituir automáticamente ese despliegue.

Los cocientes usan la unidad de Grafana «percent (0.0–1.0)»; las duraciones provienen de segundos y Grafana adapta su presentación. Los saldos negativos se conservan sin un mínimo de cero. Las consultas de los indicadores actuales son instantáneas para no reutilizar un valor histórico exitoso cuando desaparezcan los datos. Las gráficas no conectan huecos ni reemplazan datos ausentes por cero.

La línea de referencia y los colores facilitan la interpretación. La notificación de incidentes se configura por separado mediante reglas de alerta y Alertmanager.

## Verificación

El entorno reproducible y los escenarios de prueba se describen en `observability/validation/README.md`. El dashboard se valida con Grafana 13.2.5 y Prometheus 3.13.5. Las capturas de ese entorno se identifican como sintéticas y no sustituyen las evidencias de Chatwoot real.
