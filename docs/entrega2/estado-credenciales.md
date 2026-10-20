# Estado remoto y credenciales — aporte de David

## Diseño y separación de responsabilidades

La configuración compartida `terraform/backend.tf` usa un bloque `cloud` con
hostname `app.terraform.io`. La organización y el workspace se suministran en
`TF_CLOUD_ORGANIZATION` y `TF_WORKSPACE`. No hay tokens, contraseñas ni nombres de
equipo personales en ese archivo. José conserva versions/providers y el resto
del root; no debe añadir un segundo bloque `backend` o `cloud`.

El bootstrap separado `terraform/bootstrap` crea los workspaces y sus ajustes con
el provider oficial `hashicorp/tfe`. La aplicación utiliza el provider Docker en
el equipo local. HCP almacena el estado; no hospeda Rails, Sidekiq, PostgreSQL,
Redis ni sus volúmenes. GitHub Actions valida una copia temporal independiente.

La organización indicada por David es `team7-devops-2026-2-org`. Se requiere una
cuenta con acceso a ella y permisos para crear/administrar los workspaces. Usar
cuentas individuales para José y David; no compartir tokens por chat. Confirmar
en la cuenta que la organización está en el plan Free acordado; el código no
activa facturación, pruebas pagas, políticas premium ni infraestructura de nube.

| Workspace propuesto | Equipo autorizado | Configuración |
| --- | --- | --- |
| `grupo7-e2-jose` | Equipo de José, por confirmar | Root de despliegue completo |
| `grupo7-e2-david-persistence` | Equipo de David, declarado en tfvars local | Ejemplo aislado de persistencia |

Un workspace representa **una configuración y un Docker anfitrión**. No migrar
el estado del ejemplo al workspace del root: sus direcciones de recursos son
distintas. Si David necesita probar el despliegue completo en su equipo, crear
un tercer workspace, por ejemplo `grupo7-e2-david`, con `configuration = "root"`.

El bootstrap guarda la asociación (proyecto, propietario, equipo, contexto y
configuración) como JSON en la descripción del workspace. Usa
`tfe_workspace_settings` para establecer ejecución Local y restringir los
consumidores del estado. No configura una conexión VCS ni aplica desde HCP.
El locking evita operaciones concurrentes sobre el mismo estado, pero no puede
corregir que un operador apunte al Docker equivocado.

## Autenticación sin secretos en el código

Obtener un token de usuario desde la configuración personal de HCP Terraform.
No usar un token de organización como sustituto del token de usuario de la CLI.
El token debe tener los permisos de la cuenta necesarios para estos workspaces.
Desde Windows PowerShell 5.1 o PowerShell posterior, en el worktree de David:

```powershell
./terraform/scripts/state-auth.ps1
```

El prompt oculta el token. El script lo carga en `TF_TOKEN_app_terraform_io` para
Terraform CLI y en `TFE_TOKEN` para el provider del bootstrap. No lo escribe en
el historial ni lo muestra. El secreto está en texto accesible en el entorno del
proceso durante su uso; no es un almacén cifrado en memoria.

El script rechaza espacios y caracteres de control antes de guardar el token.
Si el pegado en el prompt oculto introduce caracteres de control, repetirlo con
clic derecho o `Shift+Insert`, copiando únicamente el valor del token.
Comprueba además la autenticación de usuario contra la API antes de guardar una
copia cifrada. Un error 401 requiere revisar o regenerar el token en
`https://app.terraform.io/app/settings/tokens`; el mensaje de guardado solo aparece
después de que esa comprobación termine correctamente.

La autenticación de usuario no confirma acceso a una organización. Si la consulta
de la organización devuelve 404, comprobar su nombre exacto, la membresía de la
cuenta autenticada y cualquier invitación pendiente. No regenerar un token que
ya autentica correctamente para intentar resolver una membresía ausente. Crear
workspaces y migrar el estado requiere primero acceso a la organización.

En Windows se puede guardar explícitamente una copia cifrada para ese usuario y
equipo:

```powershell
./terraform/scripts/state-auth.ps1 -SaveForCurrentUser
```

El archivo `terraform/.hcp-token.local` usa SecureString/CLIXML con DPAPI y está
excluido por `*.local`. No es portable a otra cuenta o computador. No enviarlo a
José ni incluirlo en capturas o artefactos. Para cargarlo en otra sesión del
mismo usuario/equipo sin mostrarlo:

```powershell
$savedToken = Import-Clixml -LiteralPath terraform/.hcp-token.local
$env:TF_TOKEN_app_terraform_io = [System.Net.NetworkCredential]::new('', $savedToken).Password
$env:TFE_TOKEN = $env:TF_TOKEN_app_terraform_io
```

No es necesario guardar esa copia. Como alternativa nativa, `terraform login`
administra credenciales de la CLI, pero `state-init.ps1` requiere explícitamente
la variable de proceso para comprobar el workspace vía API. El provider tfe usa
su variable `TFE_TOKEN`; no asumir que lee automáticamente la sesión de la CLI.

## Aprovisionamiento del backend

1. Confirmar organización, acceso, nombres de los equipos y contextos Docker.
2. Completar `terraform/bootstrap/terraform.tfvars`, ignorado, usando el ejemplo
   versionado. No contiene el token. David ya tiene una configuración local de
   su workspace; conservarla al continuar. Agregar José cuando confirme sus datos.
3. Ejecutar init, validate, plan y apply según el README del bootstrap. Revisar
   que solo se crean los workspaces y ajustes acordados. Cada workspace necesita
   ambos recursos; no conectar la aplicación a uno con ajustes pendientes.
4. Obtener un segundo plan sin cambios. Conservar el estado local del bootstrap
   y una copia protegida: es necesario para administrarlo idempotentemente.

El estado de este bootstrap es local para resolver el arranque inicial sin una
dependencia circular. No contiene los datos de Chatwoot y no sustituye el estado
remoto de la aplicación. Un solo operador lo custodia; otro operador no debe
reaplicar la configuración con un estado vacío. La creación/configuración de
workspaces se realiza por Terraform, sin clicks manuales en las consolas.

## Conectar un despliegue nuevo

Una vez integrado el root de José y creado su workspace Local, José carga su
propio token y ejecuta desde su computador:

```powershell
./terraform/scripts/state-init.ps1 -Organization team7-devops-2026-2-org -Workspace grupo7-e2-jose
```

El script consulta el workspace existente, exige modo Local, comprueba la
asociación de equipo y configuración y obtiene el endpoint del contexto Docker
declarado. Solo entonces selecciona las variables de conexión y ejecuta init.
No crea workspaces implícitos ni hace apply. Si encuentra recursos en el estado
local default, se detiene para que se siga el procedimiento de migración de
abajo antes de seleccionar el workspace remoto.

Después cargar las variables de aplicación por el mecanismo externo acordado
con José: `TF_VAR_postgres_password`, `TF_VAR_redis_password` y
`TF_VAR_secret_key_base`, más los parámetros no sensibles que declare root. No
copiar esas declaraciones a su `variables.tf` desde esta documentación sin que
José las integre. En modo Local las variables de workspace HCP **no se inyectan**
en la ejecución local.

Mantener seleccionados el workspace, el Docker y las mismas credenciales durante
plan/apply. Ejecutar las políticas sobre el plan que vaya a aplicarse. No usar
el workspace de José desde el Docker de David ni desde GitHub Actions.

## Migrar el ejemplo de persistencia existente de David

Esta operación requiere el workspace `grupo7-e2-david-persistence` aprovisionado
y asociado al equipo/contexto de David. No mueve los datos de los volúmenes:
traslada el estado que registra esos recursos.

Antes de migrar, mantener un solo operador, cargar las contraseñas existentes del
ejemplo desde `credentials.local` y comprobar que su plan local no tiene cambios.
No generar nuevas contraseñas para un volumen PostgreSQL ya inicializado.
Guardar una copia local del estado en una ubicación protegida:

```powershell
Copy-Item terraform/modules/persistence/examples/standalone/terraform.tfstate terraform/modules/persistence/examples/standalone/pre-hcp.tfstate
```

La copia está ignorada por `*.tfstate`. No imprimir ni subir su contenido. Si ya
existe una copia con ese nombre, conservarla y elegir un nuevo nombre antes de
sobrescribirla. A continuación:

```powershell
@'
terraform {
  cloud {
    hostname = "app.terraform.io"
    organization = "team7-devops-2026-2-org"
    workspaces {
      name = "grupo7-e2-david-persistence"
    }
  }
}
'@ | Set-Content -LiteralPath terraform/modules/persistence/examples/standalone/state-backend.local.tf -Encoding utf8
Remove-Item Env:TF_WORKSPACE -ErrorAction SilentlyContinue
terraform -chdir=terraform/modules/persistence/examples/standalone init
```

Declarar el nombre explícitamente en ese archivo local permite mantener como
origen el workspace local `default`. No usar `state-init.ps1` para esta primera
migración: asignar `TF_WORKSPACE` al nombre remoto antes de init puede seleccionar
un workspace local vacío con ese nombre y dejar sin copiar el estado default.
Comprobar que no haya otro workspace local seleccionado antes de comenzar.

`state-backend.local.tf` está ignorado y mantiene el ejemplo compartido compatible
con CI local. El script de plan de CI excluye expresamente ese archivo al copiar
el ejemplo. No ejecutar CI contra el estado remoto de David.

Leer el diálogo de init: el origen debe ser el estado local de este ejemplo y el
destino su workspace vacío, nunca el de José. Si aparece un estado remoto previo
inesperado o un error, cancelar y revisar; no usar `-force-copy`, `state push` ni
`state rm` para silenciarlo. La integración `cloud` migra mediante `terraform init`,
no requiere añadir `-migrate-state`.

Después ejecutar desde el directorio del ejemplo:

```powershell
terraform workspace show
terraform state list
terraform plan -detailed-exitcode
$LASTEXITCODE
```

Se esperan el workspace correcto, los mismos 8 recursos y plan sin cambios con
código 0. Comprobar en HCP una nueva versión de estado y que el modo sigue siendo
Local, sin mostrar contenidos sensibles. Registrar una evidencia saneada con
workspace, modo, cantidad/direcciones de recursos y código del plan. Comparar
también los identificadores de los recursos contra la copia protegida, sin
publicar el contenido del estado. En la migración verificada HCP asignó un nuevo
linaje y serial; la comprobación de continuidad se hizo sobre los ocho recursos
y su plan sin cambios.

Después de verificar la migración, `state-init.ps1` puede utilizarse para las
sesiones posteriores con ese workspace. El ejemplo de David ya fue migrado;
no repetir estos pasos sobre su estado remoto existente.

Los backups locales siguen siendo sensibles aunque la migración termine. Su
limpieza o retención se decide después de verificar la migración; no borrarlos
antes. No retirar el archivo cloud para volver a usar un estado local viejo,
porque se crearían dos estados que afirman administrar los mismos recursos.

## Seguridad, recuperación y evidencias

- `sensitive = true` oculta valores en algunas salidas; las variables Docker
  pueden conservar contraseñas en el estado y en `docker inspect`.
- Restringir acceso al workspace y proteger el equipo del operador. No publicar
  estados, backups, planes binarios/JSON, tokens ni archivos CLIXML de secretos.
- Ante exposición de un token, revocarlo y generar otro. No basta borrarlo de Git.
  Las contraseñas de aplicación requieren rotación coordinada; cambiar
  `POSTGRES_PASSWORD` no rota una base PostgreSQL ya inicializada.
- El historial HCP es historial de infraestructura, no backup de la base ni de
  adjuntos. Los volúmenes requieren su propia estrategia de respaldo.
- No ejecutar destroy para probar persistencia. Tampoco borrar workspaces con
  estado para resolver un problema de autenticación.

Al finalizar una sesión, retirar las variables de acceso del proceso:

```powershell
Remove-Item Env:TF_TOKEN_app_terraform_io, Env:TFE_TOKEN -ErrorAction SilentlyContinue
Remove-Item Env:TF_VAR_postgres_password, Env:TF_VAR_redis_password, Env:TF_VAR_secret_key_base -ErrorAction SilentlyContinue
Remove-Item Env:TF_CLOUD_ORGANIZATION, Env:TF_WORKSPACE, Env:DOCKER_HOST -ErrorAction SilentlyContinue
```

Para el apartado 2.2 del informe, describir la separación entre código, estado y
datos; autenticación externa; limitaciones de `sensitive`; modo Local y
workspaces por equipo/configuración. Adjuntar solo evidencias de operaciones
realmente ejecutadas. Código válido no equivale a workspace creado o estado
migrado: esas pruebas requieren acceso autenticado a la organización.

Fuentes oficiales: [conexión CLI y migración cloud](https://developer.hashicorp.com/terraform/cli/cloud/settings),
[variables del bloque cloud](https://developer.hashicorp.com/terraform/language/block/terraform),
[modo Local](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/settings#execution-mode),
[provider tfe](https://registry.terraform.io/providers/hashicorp/tfe/0.71.0/docs),
[información sensible](https://developer.hashicorp.com/terraform/language/manage-sensitive-data).
