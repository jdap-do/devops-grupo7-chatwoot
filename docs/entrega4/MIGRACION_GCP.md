# Evolución del laboratorio local a Google Cloud

Fecha: 4 de noviembre de 2026. Estado: preparación; no se ha creado ni validado infraestructura GCP durante este trabajo.

## Propósito

Extender la plataforma de Chatwoot a Google Cloud para disponer de un entorno compartido y conectar GitHub Actions con su despliegue. Se conserva el laboratorio local y se reutilizan los componentes y contratos comprobados en las entregas anteriores.

La migración no convierte automáticamente el sistema en altamente disponible. Una única máquina virtual conserva el punto único de falla del anfitrión.

## Acuerdos de operación y ahorro

Acuerdos del usuario, 4 de noviembre de 2026:

- Usar la prueba gratuita de GCP y controlar el consumo de créditos. No convertir la cuenta a pago como parte del despliegue.
- Encender la VM durante desarrollo, ensayos y sustentación; detenerla al terminar cada sesión. Apagar el PC no detiene la VM.
- Preparar el arranque automático de Docker y servicios persistentes; comprobar Chatwoot, Prometheus, Grafana y alertas después de cada encendido.
- Encender con anticipación el sábado 7 de noviembre para verificar el sistema antes de la sesión de clase de 07:00 a 10:00 COL.
- La detención reduce los cargos de CPU/memoria, pero conserva cargos de disco y posibles recursos reservados. Confirmar el inventario y costo antes de crear recursos.
- Conservar datos entre sesiones; detener no equivale a eliminar. No retirar discos o volúmenes como mecanismo de ahorro diario.
- Registrar los apagados como periodos planificados del laboratorio. No convertir ausencia de tráfico o telemetría en cumplimiento de disponibilidad o cobertura SRE.
- Mantener separados los recursos y estados local/GCP. Documentar los cambios para sustentarlos, conservando las entregas anteriores como evidencia histórica.
- Actualizar arquitectura y operación final en el repositorio; explicar la evolución y sus resultados comprobados en las lecciones aprendidas de la Entrega 4.

### Estado confirmado por capturas de Cloud Shell

Proyecto seleccionado: `project-45d258e3-00bf-4e6f-bbe`. La consulta de facturación devolvió `True`; la habilitación de `compute.googleapis.com` terminó correctamente; Terraform 1.17.1 quedó instalado en la sesión de Cloud Shell. Esta instalación del sistema puede requerir repetirse si se reemplaza la sesión efímera.

El usuario realizará los pasos de autenticación y comandos en Cloud Shell. No se solicitan tokens ni claves privadas por el chat. La descarga del repositorio y la selección de revisión todavía no se han confirmado en Cloud Shell. La rama GCP creada localmente tampoco se ha publicado.

## Qué se conserva y qué cambia

Actualización confirmada por capturas: organización HCP `team7-devops-2026-2-org`,
workspace nuevo `grupo7-e4-gcp-infra`, modo Local y cero recursos. El usuario
completó `terraform login` en Cloud Shell. El workspace anterior `grupo7-e2-jose`
conserva sus recursos y no se reutiliza. No se copiaron credenciales al repositorio.

La configuración `infra/gcp/` pasó formato, validación con Google 7.0.0 y revisión
de sintaxis del script de arranque. Aún no se ejecutaron init contra HCP, plan
autenticado ni apply de esta raíz. Se prepara un ZIP de archivos seleccionados
para transferirlos al clon de Cloud Shell, sin incluir cachés, estado ni secretos.

| Elemento | Se conserva | Cambio previsto y motivo |
| --- | --- | --- |
| Aplicación | Código, Dockerfile e imagen propia publicada | Descargar la imagen en la máquina GCP, identificando su digest |
| Arquitectura | Rails, Sidekiq, PostgreSQL y Redis desacoplados | Trasladar su ejecución a un anfitrión Linux remoto |
| Infraestructura local | Configuración Terraform y estado actuales | Agregar configuración GCP aislada; no reutilizar el estado del laboratorio para administrar recursos nuevos |
| Persistencia | Necesidad de conservar base, colas y adjuntos | Crear almacenamiento propio en GCP; decidir y registrar si se usan datos nuevos o una migración explícita |
| CI | Construcción, validación y escaneo existentes | Incorporar autenticación, despliegue, verificación y reversión del entorno GCP |
| Observabilidad | Instrumentación, Prometheus, Grafana y reglas SRE | Ajustar destinos, acceso y persistencia; comprobar nuevamente las señales |
| SLOs | Disponibilidad 99 %, latencia de éxitos 95 % dentro de 500 ms, ventana de 30 días | No modificar objetivos para facilitar la migración; identificar el nuevo historial como parcial |
| Operación | Diagnóstico y recuperación existentes | Adaptar accesos, nombres y procedimientos al anfitrión remoto y reensayarlos |

Cada cambio se justificará por una necesidad del nuevo entorno. No se introducen Kubernetes, bases administradas ni una reescritura de Chatwoot como parte de esta decisión.

## Registro de cambios verificables

| Cambio | Estado | Evidencia |
| --- | --- | --- |
| Copia de trabajo y rama `jose/entrega4-gcp` desde `03617cb` | Realizado localmente | Historial Git y worktree; todavía sin publicación de esta rama |
| Documento de alcance y trazabilidad | Realizado | Este archivo |
| Proyecto GCP y prueba gratuita | Informados por el usuario mediante captura | Pendiente consultar cuenta y proyecto activos al conectar |
| Aprovisionamiento Terraform GCP | Pendiente | Se registrarán plan, recursos y resultado sin secretos |
| Despliegue de aplicación y observabilidad | Pendiente | Se registrarán revisión, digest y pruebas funcionales |
| Actualización automática y continuidad | Pendiente | Se registrarán ejecución Actions, cambio efectivo y sondeo independiente |
| Ensayos de fallas y recuperación | Pendiente | Se registrarán cronologías, señales y runbooks contrastados |

## Evidencia mínima por cambio

### Revisión visual del dashboard en GCP

La vista previa inicial mostró `origin not allowed`: el acceso local por API
había pasado, pero las consultas desde el navegador eran rechazadas por CSRF.
Se incorporó el hostname exacto de la vista previa mediante
`GF_SECURITY_CSRF_TRUSTED_ORIGINS` y se recreó solo Grafana. La captura posterior
muestra consultas sin errores, telemetría válida, historial parcial,
disponibilidad y cumplimiento del umbral de latencia en 100 % sobre el historial
observado, presupuestos restantes en 100 % y p95 estimado de 99,5 ms.

Las capturas adicionales muestran sondeos satisfactorios de PostgreSQL/Redis,
latencia de sondas, transacciones y comandos, proporción de sondas fallidas en
cero, conexiones de PostgreSQL respecto del máximo y memoria absoluta de los
cuatro contenedores. Los tres endpoints de recolección aparecen accesibles.

El panel de memoria relativa muestra Sin datos porque el nuevo Compose no fija
límites individuales; el panel de configuración muestra SIN LÍMITE para los
cuatro componentes. No es ausencia de muestras de memoria ni significa RAM
ilimitada: los procesos comparten los 8 GB del anfitrión. A diferencia del
Terraform local, donde PostgreSQL y Redis sí tenían límites, su paridad de
configuración debe revisarse antes del cierre. No se han aplicado límites nuevos
durante esta revisión ni se infiere ausencia de saturación bajo mayor carga.

Queda validada la visualización nominal observada. Siguen pendientes CD,
accesos finales/compartidos, prueba de apagado y encendido con persistencia y
los incidentes aplazados para coordinación con David. También falta completar
el acceso operativo a logs estructurados; métricas visibles no acreditan por
sí solas ese requisito.

### Validación nominal de observabilidad en GCP

Captura aportada por el usuario: el generador completó 180 solicitudes en 180
segundos, todas HTTP 200, con duración media cliente de 0,056819 segundos
(aproximadamente 56,8 ms). Ejecución entre 2026-11-05 04:03 y 04:06 UTC,
equivalentes al 4 de noviembre de 2026, 23:03–23:06 en Bogotá.

`validate-integration.py` terminó sin error y reportó 40 recording rules y cinco
alertas saludables; telemetría HTTP válida; dos SLI/presupuestos; cuatro series
de memoria; dos dependencias disponibles; dashboard provisionado y sus 28
consultas ejecutables a través de Grafana; receptor sano y Alertmanager
descubierto por Prometheus. Los resultados quedaron en `.runtime/` de la VM.

El promedio cliente no es p95 ni acredita por sí solo el SLO de latencia. Que
las consultas sean ejecutables no implica que todos los paneles tengan datos
en cada condición. Pendiente revisar visualmente el dashboard y sus unidades,
incluidos paneles relativos a límites de memoria ausentes. No se han ensayado
alertas mediante incidentes durante esta fase. El historial sigue siendo parcial.

### Monitoreo e incidentes: alcance actualizado

El usuario pidió avanzar con observabilidad y aplazar los incidentes mientras
coordina con David, quien posiblemente asumirá esa parte. No se ejecutan ni se
incluyen scripts de inyección en el paquete preparado de monitoreo.

Se reutilizan configuraciones de `observability/` con override de red GCP y
parámetros de colector para nombres Compose. Se añade configuración Linux de
credenciales locales y colector systemd. Se preservan dashboard, SLOs y reglas.
Pasaron sintaxis Bash/Python y resolución de Compose, incluido aislamiento del
volumen de muestras del exportador. Quedan pendientes construcción/arranque en
GCP, comprobación de targets y validación real con tráfico nominal autenticado.

### Prueba funcional de conversación en GCP

El usuario completó el onboarding y accedió al panel autenticado con la cuenta
de demostración Admin UNAL. Creó la bandeja Website `Demo GCP - Grupo 7`.
Se sirvió `delivery4/app/demo-gcp.html` desde el directorio público de Rails,
con SDK y base URL derivados del origen del navegador. La página recibe el
identificador público de la bandeja por query; no utiliza un token personal API.

Las capturas aportadas muestran el mensaje del visitante en el panel de la
conversación 1 y la respuesta de Admin UNAL en el widget del visitante. Queda
comprobado el intercambio en ambos sentidos en este entorno. Las capturas no
permiten certificar por sí solas que no hubo recarga ni medir tiempos de entrega.

El acceso utiliza SSH/IAP y la vista previa autenticada de Cloud Shell en 8080,
reenviada a localhost:3000 de la VM. No hay todavía URL pública definitiva ni
CD conectado. Esta prueba funcional tampoco acredita los SLOs HTTP, sus cuatro
lecturas autenticadas a través del gateway, ni treinta días de cumplimiento.
El monitoreo GCP y la prueba de reinicio conservando datos siguen pendientes.

La página demo se copió al contenedor para esta comprobación y se conserva en
`/srv/chatwoot/repo/delivery4/app/` del disco persistente. Una recreación de Rails
requiere volver a instalarla o configurar su montaje en el despliegue definitivo;
no se presenta esa copia manual como entrega continua reproducible.

### Primer arranque de aplicación: redirección inicial

Las imágenes se descargaron, PostgreSQL y Redis se declararon saludables y Rails
y Sidekiq arrancaron. El primer chequeo exigía HTTP 200 directo en `/` y agotó
su espera. El diagnóstico aportado por el usuario muestra HTTP 302 hacia
`/installation/onboarding` y tareas ejecutadas por Sidekiq. Se corrige el chequeo
para exigir HTTP 200 final después de hasta tres redirecciones. No se acepta un
302 aislado como prueba de salud ni se modifica el SLI de la Entrega 3: se trata
solo del chequeo inicial de la interfaz, fuera del recorrido autenticado medido.
La página final, el alta inicial y la operación autenticada siguen pendientes
de comprobación. No hay evidencia que justifique reinicializar o borrar la base.

### Infraestructura creada y preparación comprobada

El segundo apply terminó correctamente: 6 altas y 1 reemplazo del registro IAP
marcado incompleto. La VM `grupo7-chatwoot` quedó creada en `us-central1-a`.
El usuario conectó por SSH mediante IAP y comprobó el marcador `bootstrap-ready`,
la raíz Docker `/srv/chatwoot/docker`, Compose v5.7.0 y el montaje ext4 de
`/dev/sdb` en `/srv/chatwoot`. Esto valida la preparación del anfitrión, no aún
la aplicación, los SLOs ni el pipeline de despliegue.

Se añade `delivery4/app/` como adaptación del Compose de Entrega 1: imágenes
por digest reutilizadas de Entrega 2, credenciales nuevas en el servidor, base
independiente y acceso inicial exclusivo por localhost. Su formato Compose y
sintaxis Bash pasaron validación local. Ejecución y prueba funcional pendientes.
La gestión de contenedores en GCP mediante Compose queda explícita: esta raíz
GCP de Terraform administra el anfitrión, no los contenedores de aplicación.

### Primer apply: requisito de API detectado

El primer plan propuso 8 altas, sin cambios ni eliminaciones. Durante apply se
registraron Compute Engine y OS Login. La habilitación de IAP falló con 403
SERVICE_DISABLED por falta de `cloudresourcemanager.googleapis.com`. La salida
no muestra creación de VM, discos o red. Se incorpora la habilitación de Cloud
Resource Manager al bootstrap y se prescribe regenerar el plan sobre el mismo
estado antes de reintentar. No se declara recuperación hasta comprobar el nuevo
resultado. Este caso aporta una lección de IaC sobre prerrequisitos de servicios
y recuperación de aplicaciones parciales sin perder el estado remoto.

Registrar el problema que resuelve, archivos modificados, funcionamiento anterior y nuevo, procedimiento de verificación y resultado. Los fallos y las limitaciones forman parte del registro. No incluir contraseñas, claves de servicio, tokens, archivos de estado con secretos ni datos personales en capturas o commits.

Para el despliegue, distinguir tres pruebas: infraestructura creada mediante Terraform; aplicación realmente operativa; actualización desde GitHub Actions sin fallos observados por el sondeo durante el intervalo documentado. El éxito de una de ellas no acredita las otras.

## Relación con las entregas académicas

Las entregas 1, 2 y 3 describen la versión construida y comprobada en su momento. Sus PDF no se reescriben para atribuirles un despliegue cloud posterior.

En la Entrega 4, el resumen de plataforma mostrará la arquitectura definitiva, la URL y el repositorio. El Pre-Mortem identificará el nuevo anfitrión y las dependencias pertinentes. Los runbooks reflejarán el acceso remoto y los mecanismos de recuperación realmente probados.

El apartado de lecciones aprendidas explicará la evolución local a GCP, las dificultades de CI/CD, IaC y SRE y cómo se resolvieron. No sustituye las instrucciones reproducibles del repositorio ni debe convertirse en un listado de comandos. Los resultados se redactarán después de comprobarlos, sin presentar los cambios previstos como terminados.

## Preguntas que ambos integrantes deben poder responder

1. ¿Por qué se eligió una VM y qué componentes se reutilizaron?
2. ¿Qué crea Terraform y dónde se guarda su estado?
3. ¿Cómo se autentica Actions y cómo llega el cambio al servidor?
4. ¿Dónde persisten datos y qué pasa si se reinicia o elimina la VM?
5. ¿Cómo se comprueba la versión desplegada y cómo se revierte?
6. ¿Cómo se verifican los SLOs y qué límites tiene el historial disponible?
7. ¿Qué fallas tolera la arquitectura y cuáles siguen siendo puntos únicos de falla?
