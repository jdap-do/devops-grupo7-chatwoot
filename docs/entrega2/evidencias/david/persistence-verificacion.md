# Verificación aislada de persistencia

Fecha: 18 de octubre de 2026, Colombia.
Rama: `david/terraform-datos-gobernanza`.
Base: `f98d5c1fe1`; ejecución con los cambios locales del módulo, aún sin commit.

Entorno: Windows, Docker Desktop con motor Linux 28.4.0, Terraform 1.16.6,
provider `kreuzwerker/docker` 3.6.2.

Configuración: `terraform/modules/persistence/examples/standalone`.
Prefijo exclusivo: `grupo7-david-persistence-test`.
Estado: local del ejemplo, excluido de Git. No se usó un workspace HCP.

## Resultados observados

| Comprobación | Resultado |
| --- | --- |
| Init, validate y formato | Correctos |
| Plan inicial | 8 recursos propuestos; solo creaciones |
| Aprovisionamiento completo | Red, 3 volúmenes, 2 imágenes y 2 contenedores |
| PostgreSQL y Redis | Ambos `healthy` |
| PostgreSQL con pgvector | `CREATE EXTENSION vector` ejecutado y extensión consultada |
| Autenticación PostgreSQL | Consulta autenticada correcta; conexión por interfaz de red sin contraseña o con contraseña incorrecta rechazada |
| Autenticación Redis | `PONG` autenticado; `NOAUTH` sin contraseña y `WRONGPASS` con contraseña incorrecta |
| Exposición | Ningún puerto publicado al anfitrión; ambos contenedores sin modo privilegiado |
| Plan de reemplazo | Exactamente 2 contenedores: 2 creaciones y 2 destrucciones; ningún volumen modificado |
| Volúmenes tras reemplazo | Los 3 conservaron nombre y fecha de creación |
| Datos PostgreSQL | Marcador `7` conservado en `entrega2_persistence_probe` |
| Datos Redis | Marcador `7` conservado en `entrega2:persistence:probe` |
| Plan posterior | `No changes. Your infrastructure matches the configuration.` y código 0 |

El primer apply creó los seis recursos de red, volúmenes e imágenes, pero el
provider falló al procesar `cpus`. Tras expresar la misma restricción con
`cpu_period`/`cpu_quota`, se crearon los contenedores. No se hizo destroy completo.
También se declaró `memory_swap` explícitamente para corregir diferencias
recurrentes con el valor asignado por Docker, y se ajustó el healthcheck PostgreSQL
para que exigiera contraseña fuera de loopback. La verificación final corresponde
a la configuración corregida.

## Identidad de los contenedores reemplazados

| Servicio | Antes | Después |
| --- | --- | --- |
| PostgreSQL | `94f5051b624f` | `b32fb8149d7c` |
| Redis | `445dfc0efd93` | `961a40ebb246` |

El extracto de salida real está en [persistence-resultado.txt](persistence-resultado.txt).
Se conservaron únicamente líneas de comprobación y resultado; no se adjuntaron
estados, planes binarios, JSON de planes, contraseñas ni inspecciones completas.

## Repetición y límites

Seguir el [README del módulo](../../../../terraform/modules/persistence/README.md).
La verificación guardó las contraseñas aleatorias como SecureStrings cifradas con
DPAPI en `credentials.local`, dentro del ejemplo y excluido de Git. Reutilizar ese
archivo desde el mismo usuario/equipo para volver a suministrar `TF_VAR_*` sin
mostrar los valores. No generar nuevas contraseñas para el volumen PostgreSQL
existente. El estado local contiene información sensible aunque ese archivo de
credenciales esté cifrado.

Los contenedores y los volúmenes de prueba permanecen disponibles. No se verificó
contenido del volumen de adjuntos: solo que el recurso no se reemplazó. Quedan
pendientes la integración con Rails/Sidekiq, preparación de la base Chatwoot,
prueba de conversación/adjunto al reemplazar compute, backend HCP y CI. Estos
resultados no se presentan como evidencia del despliegue final integrado.
