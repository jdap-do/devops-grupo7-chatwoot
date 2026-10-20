# Bootstrap de estado HCP Terraform

Esta configuración independiente administra workspaces en una organización
existente. No crea una cuenta, contrata planes ni despliega Chatwoot. Se utiliza
el provider oficial `hashicorp/tfe` 0.71.0, con lockfile propio.

El estado del bootstrap es local y se conserva fuera de Git. Un único operador
debe custodiarlo y repetir las operaciones desde el mismo estado. El backend de
Chatwoot se configura después; no puede ser requisito para crear los workspaces
que necesita. Este directorio no utiliza `terraform/backend.tf` del nivel superior.

## Entradas y salidas

| Entrada | Tipo | Uso |
| --- | --- | --- |
| `organization` | string | Organización existente del grupo |
| `workspaces` | map(object) | Nombre de workspace y asociación con propietario, equipo, contexto y configuración |
| `terraform_version` | string | Versión propuesta, por defecto 1.16.6; acordar con José |

Cada objeto de `workspaces` contiene `owner`, `host_name`, `docker_context` y
`configuration`. Esta última acepta `root` o `persistence-example`. La salida
`workspaces` contiene IDs, URLs, asociaciones y modo de ejecución, sin tokens.

Por cada entrada se declaran un `tfe_workspace` y un `tfe_workspace_settings`.
El segundo fija `execution_mode = "local"`, deshabilita el acceso global al estado
desde otros workspaces y deja vacía la lista de consumidores. La asignación de
usuarios al equipo/organización sigue siendo requisito de acceso: esta opción de
estado compartido no sustituye los permisos de usuarios de HCP.

Los workspaces tienen `prevent_destroy = true` y `force_delete = false` para
evitar que un cambio accidental del bootstrap borre el contenedor del estado.
Esta protección no impide que Terraform destruya recursos Docker si se ordena
un destroy de la configuración de aplicación.

## Uso en PowerShell

Desde la raíz del worktree:

```powershell
./terraform/scripts/state-auth.ps1
Copy-Item terraform/bootstrap/terraform.tfvars.example terraform/bootstrap/terraform.tfvars
# Editar el archivo local: organización, equipo y contexto reales. No contiene tokens.
terraform -chdir=terraform/bootstrap init -backend=false -lockfile=readonly
terraform -chdir=terraform/bootstrap validate
terraform -chdir=terraform/bootstrap plan
terraform -chdir=terraform/bootstrap apply
terraform -chdir=terraform/bootstrap plan -detailed-exitcode
```

El último plan debe terminar sin cambios y con código 0. No usar el ejemplo con
`REPLACE_*` sin sustituirlos. Para consultar el nombre del equipo y su contexto:

```powershell
[Environment]::MachineName
docker context show
```

En la preparación de David ya se generó un `terraform.tfvars` local ignorado con
su equipo, la organización `team7-devops-2026-2-org` y únicamente su workspace de
prueba `grupo7-e2-david-persistence`. **No sobrescribirlo con el ejemplo** si se
va a continuar esa preparación. El workspace de José se añadirá al mismo mapa
cuando confirme su equipo y contexto. No retirar del mapa un workspace ya creado.

El token se obtiene de `TFE_TOKEN` en el proceso; no se declara como variable
Terraform ni se envía en `-var`, tfvars, outputs o argumentos de comandos.

Si ya existe un workspace administrado fuera de este estado, revisar primero su
propietario y estado. Recuperar el estado del bootstrap que lo administra o
importar el recurso siguiendo la documentación de la versión fijada del provider
antes de aplicar cambios. Un workspace con estado o propietario ajeno no se
adopta para esta entrega. No borrar workspaces para resolver errores de nombre o
pérdida del estado del bootstrap.

## CI y validación

GitHub Actions inicializa el provider y ejecuta `validate`, TFLint y revisión HCL
sin token HCP. CI no ejecuta plan/apply del bootstrap ni crea workspaces en la
organización. El lockfile de este directorio pertenece a David y es independiente
del lockfile del root que mantiene José.

El procedimiento de conexión y migración está en
[estado-credenciales.md](../../docs/entrega2/estado-credenciales.md).
