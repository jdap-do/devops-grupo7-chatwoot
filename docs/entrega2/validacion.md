# Validación y gobernanza — aporte de David

## Controles implementados

La infraestructura Docker se analiza con Conftest 0.65.0 y reglas Rego v1 de OPA.
El análisis se separa en código HCL y valores del plan Terraform. El HCL se revisa
para impedir defaults de contraseñas, variables de credenciales sin sensibilidad,
credenciales literales y outputs que las expongan. El plan se revisa para impedir
contenedores privilegiados, namespaces del anfitrión, exposición de puertos de
datos, acceso al socket Docker, almacenamiento efímero para los servicios del
contrato e imágenes sin digest.

La publicación de Rails se limita a `127.0.0.1`, puerto interno 3000/TCP. Los
atributos de seguridad desconocidos bloquean la evaluación: se exige resolverlos
antes del despliegue. El ID aún desconocido de una imagen gestionada por
`docker_image` se admite cuando la configuración muestra esa referencia y el
recurso de imagen tiene digest.

Las reglas incluyen casos permitidos y rechazados, no solo una ejecución exitosa
del código actual. Las pruebas sobre configuraciones inseguras deben fallar con
el diagnóstico y código de salida esperados. Los valores de contraseñas no se
incluyen en los mensajes de rechazo. Los planes y estados sensibles permanecen
excluidos de Git y no se publican como evidencias.

La herramienta se ejecuta en una imagen fijada por digest, montando el código en
solo lectura y sin red durante la evaluación. Su ejecución está documentada en
[terraform/policies/README.md](../../terraform/policies/README.md).

## Evidencia disponible

El 18 de octubre de 2026 se verificaron 20 pruebas Rego, organizadas en 16 de plan
y 4 de fuente, con tablas que exigen que todos sus casos cumplan las aserciones.
Se aceptaron el HCL actual y el plan real del ejemplo de persistencia. Los
fixtures inseguros y una copia del plan real con `privileged=true` fueron
rechazados. No se aplicaron configuraciones inseguras.

[Evidencia saneada](evidencias/david/seguridad-verificacion.md).

## Integración en GitHub Actions

El workflow [grupo7-terraform.yml](../../.github/workflows/grupo7-terraform.yml)
ejecuta formato Terraform, TFLint 0.58.1, pruebas de políticas, revisión del HCL y
aceptación/rechazo de fixtures. Se activa en PRs hacia `develop`/`main`, pushes a
esas ramas que cambien Terraform o el propio workflow, y por ejecución manual.
Usa Ubuntu 24.04, permiso `contents: read` y un límite de 15 minutos. No modifica
el workflow de construcción/publicación de entrega 1.

TFLint aplica el preset Terraform `recommended` y reglas de documentación,
declaración de tipos y nombres `snake_case`. Se ejecuta recursivamente con la
configuración `terraform/.tflint.hcl` sobre todo `terraform/`, incluidos root,
network, compute, persistence, su ejemplo y bootstrap. El workflow inicializa y
valida también el root con `-backend=false` y su lockfile de solo lectura.
No se presenta como un analizador de
seguridad específico del proveedor Docker; esa revisión la realiza Conftest.

Las suites/fixtures comprueban el comportamiento de las reglas. Además, para
revisar los valores del código que cambia en un PR, el workflow ejecuta
`check-plan.ps1`: copia el módulo y ejemplo a un directorio temporal nuevo, genera
credenciales efímeras y ejecuta init/validate/plan contra el Docker del runner.
El plan debe proponer las 8 creaciones del ejemplo y superar las políticas. No
se ejecuta apply, no se usa HCP ni se copia el estado personal. El plan JSON se
transmite por stdin y el directorio temporal se elimina al terminar. No se suben
planes ni estados como artefactos.

Además ejecuta `check-plan.ps1 -Configuration root`, copiando el root real y los
tres módulos a otro directorio temporal, sin `backend.tf` ni `*.local.tf`.
Inyecta contraseñas y clave Rails efímeras; el prefijo de prueba también es único.
Exige que el root conecte network, persistence y compute, que el plan vacío solo
proponga creaciones y que cumpla las políticas. No transforma un root incompleto
en un resultado aprobado ni requiere acceso a HCP.

El workflow también inicializa y valida `terraform/bootstrap`, con su lockfile
propio y sin autenticación HCP. No ejecuta plan ni apply de esa configuración.
El backend de aplicación está en `terraform/backend.tf`; no se copia al plan
aislado de CI. El procedimiento operativo está en
[estado-credenciales.md](estado-credenciales.md).

Se verificaron localmente TFLint, actionlint, las suites y el plan inicial. Estas
comprobaciones **no constituyen una ejecución alojada en GitHub Actions**. Falta
subir los cambios y obtener el run real del PR; su enlace y capturas deberán
incorporarse en el apartado 3.3 del informe. La evidencia local está en
[ci-verificacion-local.md](evidencias/david/ci-verificacion-local.md).

## Integración del conjunto pendiente

La base de José `4ea19e8e4b` ya contiene network y compute. Su root todavía
instancia únicamente network: la nueva comprobación del plan de root falla
explícitamente hasta que José conecte persistence y compute. El proveedor Docker
de persistence y su ejemplo se actualizó a 4.6.0, coincidiendo con esa base.

El módulo compute aún no está integrado en root; sus recursos deben respetar el contrato
de nombres, montajes, publicaciones y entradas externas. El plan real del
conjunto deberá evaluarse con las mismas reglas antes de su apply. La protección
del estado, el backend HCP y las pruebas funcionales de Chatwoot se documentan por
separado; no quedan demostradas por un resultado estático exitoso.
