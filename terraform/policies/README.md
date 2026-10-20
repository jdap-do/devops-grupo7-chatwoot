# Políticas de seguridad Terraform/Docker

Conftest 0.65.0 / OPA 1.11.0, Rego v1. Imagen de herramienta fijada por digest:

```text
openpolicyagent/conftest:v0.65.0@sha256:afa510df6d4562ebe24fb3e457da6f6d6924124140a13b51b950cc6cb1d25525
```

Se usan dos entradas distintas: HCL2 para controles del código fuente y JSON de
`terraform show -json <plan>` para controles de valores resueltos. Deben ejecutarse
ambas. Validar solo fixtures o solo HCL no demuestra que un plan real sea seguro.

## Reglas del plan

| ID | Rechaza |
| --- | --- |
| P001 | Entradas que no sean un plan Terraform JSON formato 1.x |
| P002 | Planes sin contenedores Docker gestionados que permanezcan tras aplicar |
| P003 | Contenedores privilegiados |
| P004 | Namespaces de red, PID o IPC compartidos con el anfitrión |
| P005 | Publicación automática de todos los puertos |
| P006 | Publicaciones distintas a Rails:3000/TCP en `127.0.0.1` |
| P007 | Montajes bind del socket Docker, su directorio de ejecución o la raíz del host |
| P008 | Falta de volumen nombrado para datos o adjuntos |
| P009 | Recursos `docker_image` sin referencia por digest SHA256 |
| P010 | Imagen de contenedor mutable o desconocida sin referencia a `docker_image.*.image_id` |
| P011 | Valores de seguridad desconocidos antes de aplicar |

P006 permite cualquier puerto externo disponible; exige 3000 como puerto interno
de Rails. PostgreSQL y Redis no pueden publicar puertos, ni siquiera en loopback.
Los servicios Rails se reconocen por nombre del recurso `rails` o sufijo `-rails`
del nombre Docker.

P008 reconoce los recursos `postgres`, `redis`, `rails`, `sidekiq`, `prepare` y los
nombres Docker con esos sufijos. Exige respectivamente
`/var/lib/postgresql/data`, `/data` o `/app/storage`. Se aceptan `volumes` con
`volume_name` o `mounts` de tipo `volume` con `source`; no se aceptan volúmenes
anónimos ni bind mounts como almacenamiento de esos servicios. Mantener esta
convención en el contrato con José; si el diseño cambia, adaptar reglas y casos.

P011 recorre `after_unknown` de los atributos de seguridad, incluidos bloques
anidados. No interpreta un dato desconocido como seguro. La excepción de imagen
en P010 permite que Terraform aún no conozca el ID al crearla si la configuración
declara su referencia a un recurso `docker_image`; ese recurso se revisa con P009.
Se recorren módulos anidados e índices `count`/`for_each`. Se evalúan también
recursos `no-op`; los recursos con `after = null` se excluyen. Estas políticas son
para planes de despliegue, no para autorizar un `destroy` completo.

## Reglas del código fuente

| ID | Rechaza |
| --- | --- |
| S001 | Defaults de variables cuyos nombres indican credenciales, incluso defaults vacíos |
| S002 | Variables de credenciales sin `sensitive = true` |
| S003 | Outputs con nombres de credenciales o referencias a variables de credenciales |
| S004 | Credenciales en locals, argumentos de módulos/recursos/providers que no provengan directamente de `var.*` |
| S005 | Credenciales literales o parcialmente literales en listas `env` de contenedores |

Los nombres protegidos contienen `password`, `secret_key_base`, o los segmentos
`token`, `credential`, `credentials`. Las entradas de credenciales se deben
reenviar directamente, por ejemplo `POSTGRES_PASSWORD=${var.postgres_password}`.
No se imprimen valores de credenciales en los diagnósticos.

Esta revisión no es un detector universal de secretos: no resuelve expresiones
HCL arbitrarias ni inspecciona archivos fuera del conjunto Terraform evaluado.
Mantener los nombres acordados y las entradas externas del contrato. Tampoco
analiza vulnerabilidades de imágenes ni sustituye autenticación, backups,
protección del estado o pruebas de ejecución.

## Verificación reproducible sin aprovisionar

Desde la raíz del worktree, con Docker Linux activo y PowerShell:

```powershell
./terraform/policies/check.ps1
```

El script ejecuta las dos suites, revisa los `.tf` actuales excluyendo
`.terraform/`, acepta los fixtures seguros y exige el rechazo de los inseguros
con código 1 y diagnóstico esperado. Cualquier fallo inesperado termina el script
con error. El resumen final debe ser:

```text
PASS: policy suites, current HCL and accepted/rejected fixtures.
```

Los contenedores Conftest tienen el repositorio montado solo para lectura y red
deshabilitada durante el análisis. La primera descarga de la herramienta sí
requiere conectividad al registro. No se requieren credenciales Terraform ni
acceso al estado o al workspace del despliegue. El mismo script se puede invocar
desde un runner con PowerShell y Docker Linux; ya lo invoca
[grupo7-terraform.yml](../../.github/workflows/grupo7-terraform.yml).

El workflow añade formato, TFLint 0.58.1 y la evaluación de planes iniciales del
ejemplo y del root. Para repetirlos con Terraform 1.16.6, Docker Linux y
PowerShell 7.2 o posterior:

```powershell
./terraform/policies/check-plan.ps1
./terraform/policies/check-plan.ps1 -Configuration root
```

`check-plan.ps1` copia solo los `.tf` de los módulos y de la configuración
seleccionada (ejemplo o root), junto con su lockfile,
a un directorio temporal único. Usa contraseñas aleatorias efímeras, backend local
sin estado previo y el Docker del equipo que ejecuta la prueba. Ejecuta init con
lockfile de solo lectura, validate, plan y Conftest. No hace apply. Al terminar,
restaura las variables del proceso y elimina su directorio temporal después de
comprobar que se encuentra dentro de la raíz temporal del sistema. No copia el
estado, credenciales o backend del entorno personal: excluye `backend.tf` y
`*.local.tf` al copiar la configuración. El plan se valida también
cuando los IDs de imágenes aún son desconocidos.

La opción `root` exige llamadas a los tres módulos del contrato (`network`,
`persistence` y `compute`), solo acciones de creación desde estado vacío y las
mismas políticas de seguridad. El root de José en `4ea19e8e4b` solo llama a
network, por lo que ese control debe fallar hasta que José conecte el conjunto.
No se omite la comprobación ni se sustituye el root real por un fixture aprobado.

TFLint usa el ruleset Terraform incluido en su imagen, sin plugins externos:
preset `recommended`, documentación de variables/salidas, tipos y nombres
`snake_case`. Su configuración está en
[terraform/.tflint.hcl](../.tflint.hcl); las reglas de seguridad Docker siguen siendo
responsabilidad de Conftest.

TFLint recorre todo `terraform/`: root, módulos, ejemplo y bootstrap.
El workflow ejecuta también init/validate de root y bootstrap sin backend,
token ni apply. El plan de root usa exclusivamente el directorio temporal
independiente descrito arriba. Docker provider está fijado en 4.6.0 tanto en
root y módulos de José como en persistencia y su ejemplo.

Con Conftest nativo 0.65.0 se pueden ejecutar las mismas políticas directamente:

```text
conftest verify --policy terraform/policies/plan
conftest verify --policy terraform/policies/source
conftest test --parser hcl2 --policy terraform/policies/source <archivos.tf>
conftest test --parser json --policy terraform/policies/plan terraform/policies/fixtures/secure.plan.json
```

`<archivos.tf>` representa la lista de archivos que debe recorrer CI; no ejecutar
ese marcador literalmente. Los fixtures son datos sintéticos reducidos, con un
registro `example.invalid`, hashes de prueba y `NOT_A_REAL_SECRET`. No son planes
desplegables ni se deben aplicar.

## Evaluar el plan real antes del apply

Cargar primero las variables externas y el endpoint Docker según el README del
ejemplo. Desde `terraform/modules/persistence/examples/standalone`:

```powershell
terraform plan '-out=security.tfplan'
if ($LASTEXITCODE -ne 0) { throw 'Falló terraform plan' }
$policyPath = (Resolve-Path '../../../../policies').Path
terraform show -json security.tfplan | docker run --rm --network none -i --mount "type=bind,source=$policyPath,target=/policies,readonly" openpolicyagent/conftest:v0.65.0@sha256:afa510df6d4562ebe24fb3e457da6f6d6924124140a13b51b950cc6cb1d25525 test --parser json --policy /policies/plan -
if ($LASTEXITCODE -ne 0) { throw 'El plan no superó las políticas' }
# Solo después de revisar y aceptar el plan validado:
terraform apply security.tfplan
```

El archivo binario está excluido de Git por `*.tfplan`. El JSON se transmite por
stdin y no se publica como artefacto. Tanto el binario como el JSON pueden
contener secretos aunque los diagnósticos de las políticas no los muestren.
No usar `--trace` ni publicar dumps para el plan real. Si `terraform show` falla,
Conftest debe rechazar la entrada; verificar también ese error al automatizarlo.

En la verificación del 18 de octubre de 2026 se aceptó un plan real sin cambios y
se rechazó una copia en memoria con `privileged = true`. No se aplicó ninguna
variante insegura. La evidencia está en
[seguridad-verificacion.md](../../docs/entrega2/evidencias/david/seguridad-verificacion.md).

Fuentes oficiales: [Conftest, ejecución y pruebas](https://www.conftest.dev/),
[release 0.65.0](https://github.com/open-policy-agent/conftest/releases/tag/v0.65.0),
[formato JSON de Terraform](https://developer.hashicorp.com/terraform/internals/json-format).
