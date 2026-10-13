# Grupo 7 — Entrega 1

Base: Chatwoot v4.18.0, commit `9f920b549c14491a4e587687a3eed5d21c6ccc7d`.

## Explicación del Dockerfile

El `Dockerfile` de la raíz empaqueta Chatwoot desde el código fuente mediante
una construcción por etapas. Utiliza Ruby 3.4.11 y Node 24.13.0 sobre Debian
Bookworm, permitiendo que Bundler seleccione gems Linux precompiladas, como
gRPC y Nokogiri, cuando están disponibles en el lockfile.

| Etapa | Responsabilidad |
| --- | --- |
| `node` | Proporciona Node y npm para construir el frontend. |
| `base` | Instala Ruby, Bundler y las bibliotecas de ejecución compartidas. |
| `pre-builder` | Instala dependencias, incorpora el código y compila JavaScript y CSS. |
| `runtime` | Recibe las gems instaladas y la aplicación preparada para ejecutarla. |

La etapa base instala certificados, zonas horarias, cliente y bibliotecas de
PostgreSQL y herramientas de procesamiento de imágenes: ImageMagick y libvips.
La configuración predeterminada utiliza producción y excluye las gems de
desarrollo y pruebas. `BUNDLE_PATH=/gems` determina dónde se instalan las gems;
`VIPS_BLOCK_UNTRUSTED=1` restringe los cargadores de imágenes de libvips.

Las herramientas de compilación se instalan en el builder antes de copiar los
manifiestos. Primero se incorporan `Gemfile` y `Gemfile.lock`, y después
`package.json` y `pnpm-lock.yaml`. Esto permite reutilizar las instalaciones
cuando cambia el código pero las dependencias permanecen iguales.
Bundler utiliza dos trabajadores; pnpm 10.2.0 instala con `--frozen-lockfile`.

BuildKit conserva las descargas de Bundler en `/gems/ruby/3.4.0/cache` y las
de pnpm en `/pnpm/store`. Las gems instaladas permanecen fuera del mount de
descargas y se copian a la imagen final. `npm_config_store_dir` fija la misma
ruta para la instalación inicial y las tareas Rails que ejecutan pnpm otra vez.
`.dockerignore` excluye credenciales, Git, documentación y cachés locales del
contexto de construcción.

Después de copiar el código, se normalizan los scripts a finales de línea
Linux, se prepara el directorio de logs y se ejecuta `assets:precompile`.
El heap de Node se limita a 4096 MiB durante la compilación. La clave usada
para generar recursos es temporal; la clave real se suministra al arrancar.
En producción se eliminan `node_modules`, las pruebas de la raíz y la caché
temporal después de generar los recursos.

El argumento obligatorio `SOURCE_REVISION` se escribe en `/app/.git_sha`
después de compilar los recursos. Identifica el código sin incluir `.git`
y permite actualizar la revisión sin recompilar los recursos por ese motivo.
También se retiran fuentes C, objetos de compilación y el binario Java de
concurrent-ruby, que corresponde a JRuby y no se utiliza bajo Ruby MRI.

La imagen final de producción conserva las bibliotecas, Node, las gems y los
recursos de Chatwoot. Los compiladores, cabeceras, git, npm y pnpm quedan en el
builder. Una construcción explícita en modo desarrollo habilita herramientas
adicionales. `EXPOSE 3000` documenta el puerto interno; Compose proporciona el
comando de Rails o Sidekiq y decide qué puerto publicar en el host.

## Explicación de Docker Compose

El archivo actual es `compose.entrega.yml`. Su función es definir el sistema
completo para ejecutarlo localmente con un único comando. El nombre de proyecto
`devops-grupo7` separa sus contenedores, red y volúmenes de otras instalaciones.

| Servicio | Función |
| --- | --- |
| `postgres` | Ejecuta PostgreSQL 16 con pgvector y la base `chatwoot_production`. |
| `redis` | Proporciona caché y soporte para las colas, con contraseña y persistencia AOF. |
| `prepare` | Ejecuta `bundle exec rails db:chatwoot_prepare` y termina al completar la preparación. |
| `rails` | Ejecuta el servidor web de Chatwoot en el puerto interno 3000. |
| `sidekiq` | Procesa tareas en segundo plano con la configuración `config/sidekiq.yml`. |

La sección `x-app` y el ancla `&app` comparten la imagen local
`devops-grupo7/chatwoot:4.18.0`, su construcción, el archivo `.env`, las variables
de producción y el almacenamiento entre `prepare`, `rails` y `sidekiq`.
El bloque `build` utiliza el Dockerfile de la raíz y exige `SOURCE_REVISION`.
La etiqueta local de Compose es distinta de las etiquetas publicadas en GHCR.

PostgreSQL y Redis tienen comprobaciones de disponibilidad cada cinco segundos,
con un máximo de veinte intentos y un timeout de cinco segundos por intento.
`prepare` espera que ambos servicios estén saludables. Rails y Sidekiq esperan
que `prepare` termine correctamente, mediante `service_completed_successfully`.
Así, la preparación de la base forma parte del arranque automático.

Los servicios permanentes utilizan `restart: unless-stopped`; `prepare` usa
`restart: "no"` para que una preparación fallida no se reintente automáticamente.
Rails publica `127.0.0.1:3001:3000`, permitiendo acceder en
<http://localhost:3001>. PostgreSQL y Redis permanecen en la red interna.

| Volumen | Datos conservados |
| --- | --- |
| `postgres_data` | Base de datos, almacenada en `/var/lib/postgresql/data`. |
| `redis_data` | Archivos de persistencia de Redis, almacenados en `/data`. |
| `storage_data` | Archivos y adjuntos de Chatwoot, almacenados en `/app/storage`. |

Los volúmenes sobreviven a la recreación de los contenedores y a un `down`
normal. `down -v` elimina estos datos y no se utiliza para un reinicio normal.

## Configuración y arranque

Configurar `.env` una vez a partir de `.env.entrega.example`, conservándolo fuera
de Git. Si ya existe, revisar y adaptar sus valores antes de utilizar la entrega.
Reemplazar las claves de ejemplo de `SECRET_KEY_BASE`, `POSTGRES_PASSWORD` y
`REDIS_PASSWORD` por valores aleatorios propios. Indicar en `SOURCE_REVISION`
la revisión del código que se construirá; `git rev-parse HEAD` permite consultar
el commit actual. Mantener las conexiones a los servicios `postgres` y `redis`
y el acceso local en el puerto 3001 según la plantilla.

Con el entorno preparado, construir la imagen y levantar todos los servicios
mediante un único comando:

```powershell
docker compose -f compose.entrega.yml up -d --build
```

`--build` construye la imagen desde el Dockerfile y `-d` mantiene los servicios
en segundo plano. No es necesario ejecutar `docker build` ni preparar la base
por separado. Como comprobación opcional, `docker compose -f compose.entrega.yml
config --quiet` valida el manifiesto sin arrancar contenedores.

Para cumplir literalmente el nombre `docker-compose.yml` solicitado por el
enunciado, queda pendiente renombrar `compose.entrega.yml` y actualizar sus
referencias. Con ese nombre, el arranque sería `docker compose up -d --build`.

## Estado

La primera imagen propia se construyó y arrancó localmente el 10 de octubre
de 2026. La preparación terminó con código 0, PostgreSQL y Redis quedaron
saludables, Rails respondió HTTP 200 y Sidekiq se conectó a Redis.
La versión optimizada se verificó nuevamente el 11 de octubre; los resultados,
las medidas de caché y los hallazgos de seguridad pendientes se registran en
[docs/PIPELINE_GRUPO7.md](docs/PIPELINE_GRUPO7.md).
Falta completar la evidencia de una conversación sobre la imagen propia y
comprobar su publicación y descarga desde el registro.

## Pipeline del grupo

La configuracion del pipeline y sus pendientes se explican en
[docs/PIPELINE_GRUPO7.md](docs/PIPELINE_GRUPO7.md). Valida PR y pushes en
`develop` y `main`; la publicacion en GHCR ocurre solo mediante un push a `main`
que supere construccion y escaneo. La
[ejecución del PR con las correcciones](https://github.com/jdap-do/devops-grupo7-chatwoot/actions/runs/38199279690)
terminó correctamente; la publicación se omitió por tratarse de un Pull Request.

## Licencia

Conservar LICENSE y los avisos originales. El contenido de enterprise/ tiene licencia distinta del código MIT; no afirmar que todo el repositorio está bajo MIT.
