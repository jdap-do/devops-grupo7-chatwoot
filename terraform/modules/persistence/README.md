# Persistencia de Chatwoot — entrega 2, grupo 7

Responsable: David. Este módulo administra PostgreSQL con pgvector, Redis con AOF
y tres volúmenes Docker nombrados. Consume una red existente; no administra Rails,
Sidekiq, la preparación de la base ni el backend de estado del despliegue final.

## Estado de la implementación

- Interfaz compatible con `docs/entrega2/contrato-modulos.md`, publicado por José.
- Verificado el 18 de octubre de 2026 con Terraform 1.16.6 y provider Docker 3.6.2:
  inicialización del ejemplo, `terraform validate` y `terraform fmt -check`.
- Verificado en Docker Engine 28.4.0: aprovisionamiento, salud, autenticación,
  pgvector, ausencia de puertos publicados, reemplazo de ambos contenedores sin
  reemplazar volúmenes y conservación de marcadores PostgreSQL/Redis. El plan
  posterior terminó sin cambios, con código 0.
- Pendiente: integración con compute y prueba de conversación/adjunto de Chatwoot.
- Actualizado el 19 de octubre de 2026 a Docker provider 4.6.0, como root y
  compute de José (base `4ea19e8e4b`). Init, validate y plan contra el estado HCP
  existente: sin cambios, código 0; no se ejecutó apply para actualizarlo.
- Las imágenes están fijadas por digest de índice multiarquitectura, consultado
  con `docker buildx imagetools inspect` el 18 de octubre de 2026. Esa consulta no
  necesita el motor Docker y no prueba el arranque. Pendiente: prueba funcional
  integrada con el cómputo de José.

## Recursos y ciclo de vida

| Recurso | Nombre | Uso |
| --- | --- | --- |
| Contenedor PostgreSQL | `<prefijo>-postgres` | PostgreSQL 16 con pgvector; puerto interno 5432 |
| Contenedor Redis | `<prefijo>-redis` | Redis 7.4 autenticado y AOF; puerto interno 6379 |
| Volumen PostgreSQL | `<prefijo>-postgres-data` | Montado en `/var/lib/postgresql/data` |
| Volumen Redis | `<prefijo>-redis-data` | Montado en `/data` |
| Volumen adjuntos | `<prefijo>-storage-data` | Compute lo monta en `/app/storage` para Rails y Sidekiq |

Terraform también administra las dos referencias de imagen con `docker_image`.
Los contenedores usan nombres DNS propios en la red recibida, sin IPs fijas ni
puertos publicados al anfitrión. No usan modo privilegiado ni el socket Docker.

Los límites iniciales de laboratorio son PostgreSQL: 512 MB/1 CPU; Redis:
256 MB/0.5 CPU. Deben contrastarse con mediciones del conjunto antes del informe.
No son requisitos oficiales de Chatwoot ni una configuración de alta disponibilidad.

Se usa un período de CPU de 100000 microsegundos y cuotas de 100000/50000,
respectivamente. Durante la validación inicial el parámetro `cpus` provocó un
fallo interno del provider 3.6.2. Se conservan los parámetros CFS equivalentes
al actualizar a 4.6.0 para evitar cambios innecesarios en los recursos. `memory_swap`
se declara como el doble de `memory` (memoria más swap), coincidiendo con el valor
asignado por este Docker y evitando diferencias permanentes en el plan.

Los volúmenes son recursos independientes de los contenedores. Reemplazar solo
Rails, Sidekiq o un contenedor de datos no debe reemplazar los volúmenes. Cambiar el
prefijo selecciona recursos nuevos y no migra los datos. Un `terraform destroy`
completo incluye los volúmenes y puede borrar los datos: esta separación no es un
backup ni protege contra una destrucción explícita.

## Entradas

| Entrada | Tipo | Obligatoria | Descripción |
| --- | --- | --- | --- |
| `project_prefix` | string | Sí | De 1 a 48 caracteres: inicial minúscula, números y guiones |
| `network_name` | string | Sí | Red Docker existente, compartida con compute |
| `postgres_password` | string, sensible | Sí | Contraseña externa no vacía |
| `redis_password` | string, sensible | Sí | Contraseña externa no vacía, distinta a la de PostgreSQL |
| `postgres_image` | string | No | PostgreSQL 16 con pgvector, fijado por el digest listado abajo |
| `redis_image` | string | No | Redis 7.4 Alpine, fijado por el digest listado abajo |

Referencias predeterminadas:

```text
pgvector/pgvector:pg16@sha256:7b822b0aac60967beb1ea5e576b8602c94c300a157d187f385ae3e0da199b90a
redis:7.4-alpine@sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499
```

Al actualizar las imágenes, conservar referencias por digest y volver a probarlas.

El módulo y el ejemplo requieren Terraform `>= 1.16.6, < 2.0.0` y provider
`kreuzwerker/docker = 4.6.0`, alineados con root, network y compute.
El lockfile del ejemplo incluye las plataformas Windows AMD64 y Linux AMD64.
José conserva la propiedad de las versiones y del lockfile del root final.

## Salidas

| Salida | Tipo | Valor |
| --- | --- | --- |
| `postgres_host` | string | Nombre del contenedor PostgreSQL |
| `postgres_port` | number | 5432 |
| `postgres_database` | string | `chatwoot_production` |
| `postgres_username` | string | `postgres` |
| `redis_host` | string | Nombre del contenedor Redis |
| `redis_port` | number | 6379 |
| `storage_volume_name` | string | Nombre del volumen de adjuntos |

No hay salidas de contraseñas ni URLs que las incluyan. Root entrega las mismas
entradas sensibles a persistence y compute. El usuario PostgreSQL es el usuario
inicial de la imagen para este laboratorio; no se presenta como un diseño de
mínimos privilegios para producción pública.

## Salud y preparación de la aplicación

PostgreSQL ejecuta una consulta `SELECT 1` autenticada por TCP contra la base
inicial usando `$HOSTNAME`, para pasar por la interfaz de red del contenedor.
No se usa loopback, que permite conexiones locales de confianza en esta imagen.
No se considera suficiente que exista el contenedor. Redis debe responder
exactamente `PONG` a una consulta autenticada. Ambos usan comprobaciones cada 5 s,
timeout de 5 s, 20 reintentos y `wait = true` con un límite de espera de 180 s.

El provider espera salud al crear los contenedores. Los hosts devueltos dependen
de esos recursos. José debe hacer que la preparación de Chatwoot dependa del
módulo completo (por ejemplo `depends_on = [module.persistence]` en el recurso o
módulo de preparación). Esto no constituye monitoreo continuo: la comprobación de
salud y la espera deben verificarse en el despliegue real.

La imagen PostgreSQL crea `chatwoot_production` en un volumen vacío. Este módulo no
ejecuta migraciones ni crea el esquema de Chatwoot. José implementa la tarea
`db:chatwoot_prepare` y su orden respecto a Rails y Sidekiq.

## Ejemplo aislado en PowerShell

Desde el worktree de David:

```powershell
Set-Location terraform/modules/persistence/examples/standalone
docker version
$env:DOCKER_HOST = docker context inspect --format '{{.Endpoints.docker.Host}}'
if (Test-Path -LiteralPath credentials.local) {
  $credentials = Import-Clixml -LiteralPath credentials.local
  $env:TF_VAR_postgres_password = [System.Net.NetworkCredential]::new('', $credentials.postgres).Password
  $env:TF_VAR_redis_password = [System.Net.NetworkCredential]::new('', $credentials.redis).Password
} else {
  $env:TF_VAR_postgres_password = [System.Net.NetworkCredential]::new('', (Read-Host 'Contraseña PostgreSQL de laboratorio' -AsSecureString)).Password
  $env:TF_VAR_redis_password = [System.Net.NetworkCredential]::new('', (Read-Host 'Contraseña Redis de laboratorio' -AsSecureString)).Password
}
terraform init -backend=false
terraform validate
terraform plan
terraform apply
```

Introducir dos contraseñas de laboratorio fuertes y distintas, conservándolas en
un gestor local para repetir la prueba. Los prompts evitan escribirlas en el
historial. Terraform las recibe como texto en el proceso; no se garantiza que no
aparezcan en el estado o sean accesibles mediante Docker.

La verificación realizada generó dos contraseñas aleatorias y guardó sus
SecureStrings mediante `Export-Clixml` en `credentials.local`, excluido de Git por
`*.local`. En Windows están cifradas con DPAPI para el usuario/equipo actuales.
El bloque anterior permite reutilizarlas sin mostrarlas. Ese archivo no es un
respaldo portable ni elimina los secretos del estado Terraform. Conservarlo
mientras se use el laboratorio; no cambiar las contraseñas al repetir la prueba.

Se necesita el motor Linux de Docker Desktop activo, conectividad a los registros
y permiso para descargar las imágenes. `DOCKER_HOST` apunta al endpoint del
contexto seleccionado; el provider no depende de que interprete el contexto de la
CLI. Si se ejecuta desde WSL/Linux, configurar ese endpoint para ese entorno.

El ejemplo crea una red interna propia y usa el prefijo
`grupo7-david-persistence-test`. No consume recursos de Compose de entrega 1.
Su estado es **local y exclusivo de la prueba**; no usa HCP ni el workspace final.
Un despliegue nuevo propone 8 recursos: red, 3 volúmenes, 2 imágenes y 2
contenedores. Verificar el plan antes de aceptarlo.

## Comprobaciones manuales pendientes

Los siguientes comandos asumen el prefijo predeterminado del ejemplo. Si cambia,
adaptar los nombres. No ejecutar sobre un entorno que contenga datos ajenos.

1. Consultar los estados y puertos. Se esperan ambos servicios `healthy` y ninguna
   publicación de puertos al anfitrión:

   ```powershell
   docker ps --filter name=grupo7-david-persistence-test --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
   docker port grupo7-david-persistence-test-postgres
   docker port grupo7-david-persistence-test-redis
   ```

2. Comprobar PostgreSQL con contraseña y crear un marcador en el volumen de prueba:

   ```powershell
   'export PGPASSWORD="$POSTGRES_PASSWORD"; psql -w -h "$HOSTNAME" -U postgres -d chatwoot_production -v ON_ERROR_STOP=1 -c "SELECT 1"' | docker exec -i grupo7-david-persistence-test-postgres sh
   docker exec grupo7-david-persistence-test-postgres psql -U postgres -d chatwoot_production -v ON_ERROR_STOP=1 -c 'CREATE TABLE IF NOT EXISTS entrega2_persistence_probe (id integer PRIMARY KEY); INSERT INTO entrega2_persistence_probe VALUES (7) ON CONFLICT DO NOTHING;'
   ```

3. Comprobar Redis: sin autenticación debe responder `NOAUTH`; autenticado debe
   permitir escribir el marcador y forzar el guardado antes de la sustitución:

   ```powershell
   docker exec grupo7-david-persistence-test-redis redis-cli ping
   'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli SET entrega2:persistence:probe 7' | docker exec -i grupo7-david-persistence-test-redis sh
   'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli SAVE' | docker exec -i grupo7-david-persistence-test-redis sh
   ```

4. Reemplazar únicamente los contenedores mediante Terraform. El plan debe
   conservar los tres volúmenes; cancelar si propone destruirlos:

   ```powershell
   terraform apply '-replace=module.persistence.docker_container.postgres' '-replace=module.persistence.docker_container.redis'
   docker exec grupo7-david-persistence-test-postgres psql -U postgres -d chatwoot_production -v ON_ERROR_STOP=1 -c 'SELECT id FROM entrega2_persistence_probe;'
   'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli GET entrega2:persistence:probe' | docker exec -i grupo7-david-persistence-test-redis sh
   terraform plan -detailed-exitcode
   $LASTEXITCODE
   ```

   Se esperan ambos marcadores con valor `7` y un plan sin cambios con código 0.
   Código 1 es un error y código 2 indica diferencias. Estas comprobaciones no
   sustituyen la prueba integrada de conversación y adjunto al reemplazar compute.

5. Al terminar la sesión, retirar las variables del proceso sin borrar el estado:

   ```powershell
   Remove-Item Env:TF_VAR_postgres_password, Env:TF_VAR_redis_password
   Remove-Item Env:DOCKER_HOST
   ```

   Volver a proporcionar las mismas contraseñas antes de un plan/apply posterior.
   No usar `destroy` como prueba de persistencia. La limpieza deliberada del
   laboratorio es una operación separada que elimina sus datos.

## Credenciales y cambios posteriores

`.gitignore` excluye `.terraform/`, estados, tfvars, planes con extensiones
`.tfplan`/`.tfplan.json` y configuración local de credenciales. Usar esas extensiones
si se guardan planes; no exportar JSON con otros nombres a rutas versionadas.
Los lockfiles sí se versionan. No publicar estados ni planes como evidencias.

`sensitive = true` oculta las entradas en algunas salidas de Terraform; los valores
pueden quedar en el estado y en la configuración inspeccionable de los
contenedores. El estado local del ejemplo requiere acceso restringido. El backend
HCP y su procedimiento se entregarán por separado.

**PostgreSQL solo usa `POSTGRES_PASSWORD` para inicializar un volumen vacío.**
Cambiar la variable con datos existentes no rota la contraseña almacenada. El
healthcheck fallará si deja de coincidir, evitando presentar el servicio como
saludable. Una rotación requiere actualizar coordinadamente la contraseña en la
base, las variables externas y los clientes; nunca borrar el volumen para rotarla.

Redis aplica su contraseña al iniciar y vuelve a cargar AOF desde su volumen.
Coordinar sus cambios de credenciales con los procesos de la aplicación.

## Entrega a José

- Revisar los nombres/tipos de este contrato y confirmar versiones/digests.
- Crear la red y pasar `network_name` desde su módulo, no como nombre manual fijo.
- Compartir las entradas sensibles entre persistence y compute desde root.
- Montar `storage_volume_name` en `/app/storage` y usar `ACTIVE_STORAGE_SERVICE=local`.
- Configurar las variables PostgreSQL y Redis de Chatwoot a partir de las salidas.
- Esperar este módulo antes de preparar la base y arrancar los procesos.
- Verificar salud, plan limpio y conservación de conversaciones/adjuntos en el
  entorno final. David no ha modificado root, network, compute ni su lockfile.

Referencias: [provider Docker 4.6.0, contenedores](https://github.com/kreuzwerker/terraform-provider-docker/blob/v4.6.0/docs/resources/container.md),
[imagen PostgreSQL e inicialización](https://hub.docker.com/_/postgres),
[persistencia Redis](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/).
