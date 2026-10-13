# Pipeline del Grupo 7

## Base y ramas

La entrega utiliza Chatwoot v4.18.0 y el trabajo integrado en el fork
`jdap-do/devops-grupo7-chatwoot`. El flujo del equipo es:

```text
rama de trabajo -> PR a develop -> PR a main
```

El workflow `.github/workflows/grupo7-ci.yml` valida los PR dirigidos a
`develop` y `main`, los pushes a esas dos ramas y las ejecuciones manuales.
Un push a una rama de trabajo no lo activa: abrir el PR hacia `develop`.

## Validacion, construccion y escaneo

1. Hadolint revisa el `Dockerfile` de la raiz y bloquea errores. Las advertencias
   siguen visibles, incluidas las de paquetes Debian sin versiones fijadas.
2. yamllint revisa `docker-compose.yml`, el workflow y su archivo de reglas.
3. Compose valida con `.env.entrega.example`, sin utilizar credenciales locales.
4. Buildx construye una imagen Linux amd64 desde el codigo del commit de la
   ejecucion. `SOURCE_REVISION` registra ese commit en `/app/.git_sha`.
5. Trivy genera un informe JSON completo, incluidos hallazgos sin correccion.
   El informe se conserva como artefacto del workflow.
6. Un segundo control bloquea las vulnerabilidades CRITICAL con correccion
   disponible. Esta politica no significa ausencia de otras vulnerabilidades;
   revisar tambien el informe completo para la entrega.

El Dockerfile de la raiz usa Ruby 3.4.11 y Node 24.13.0 sobre Debian Bookworm.
Bundler elige las gems precompiladas del lockfile cuando estan disponibles,
incluidas gRPC y Nokogiri, sin forzar `force_ruby_platform`. Las otras gems
nativas se instalan con dos trabajadores para limitar el consumo de memoria.
Las herramientas del sistema se instalan antes de copiar los manifiestos.
La etapa final contiene bibliotecas de ejecucion y los recursos compilados;
los compiladores, cabeceras, git, npm y pnpm quedan en el builder de produccion.
El Compose de la entrega sigue proporcionando los comandos de Rails y Sidekiq.
El Dockerfile original bajo `docker/` conserva la receta de desarrollo Alpine,
con Ruby actualizado para que siga siendo compatible con el Gemfile.

## Cache de construccion

El workflow importa y exporta cache de GitHub Actions con el scope `grupo7`.
La exportacion usa `mode=max` para incluir las capas intermedias de instalacion
de gems, dependencias JavaScript y compilacion de recursos.

Ademas, BuildKit monta `/gems/ruby/3.4.0/cache` para los archivos descargados
de Bundler y `/pnpm/store` para pnpm. Las gems instaladas permanecen en `/gems`
y se copian a la imagen final; no se monta ese directorio completo como cache.
Esto permite reutilizar descargas cuando cambia un lockfile y hay que instalar
de nuevo las dependencias.
`npm_config_store_dir` fija la misma ruta para la instalacion inicial y para
el `pnpm install` que ejecuta la tarea de recursos de Chatwoot. El mount se
utiliza en ambos pasos para evitar una reinstalacion por cambio de store.

La cache `type=gha` de capas no conserva esos mounts entre runners. El workflow
usa `actions/cache` y `buildkit-cache-dance` para restaurarlos y extraerlos.
La clave incluye sistema, arquitectura, versiones de Ruby/pnpm y los lockfiles;
una clave anterior compatible sirve para recuperar descargas ya disponibles.

`.dockerignore` excluye la cache local `.pnpm-store/`, `docs/`, los Markdown
de documentacion de la raiz y configuracion de CI/Compose que no necesita la
imagen. Las dependencias se instalan dentro del builder. Los cambios en estos
archivos no alteran el contenido de `COPY . /app`, por lo que pueden reutilizarse
las capas de recursos si el codigo y las dependencias siguen iguales.
Las licencias y el codigo de `enterprise/` permanecen incluidos.

`SOURCE_REVISION` se escribe despues de compilar recursos. Un commit nuevo
actualiza `/app/.git_sha` sin obligar por si solo a recompilar esos recursos.
Los cambios funcionales del Dockerfile siguen invalidando las instrucciones
afectadas; la primera construccion necesita generar la cache.

Para comprobar el resultado, revisar `CACHED`, la importacion y la exportacion
de cache en los logs de Buildx. Una cache almacenada no demuestra que todas
las capas se reutilizaron ni garantiza un tiempo concreto de construccion.

Referencia: [optimizacion de cache de Docker](https://docs.docker.com/build/cache/optimize/).
La persistencia de mounts en CI sigue la
[documentacion de Docker para GitHub Actions](https://docs.docker.com/build/ci/github-actions/cache/#cache-mounts).

## Publicacion

Solo un push a `main` permite autenticarse en GHCR y publicar, despues de pasar
los controles anteriores. Los PR, pushes a `develop` y ejecuciones manuales
validan, construyen y escanean sin publicar.

Se publica la misma imagen local que se escaneo, sin una segunda construccion:

- `ghcr.io/jdap-do/devops-grupo7-chatwoot:sha-<commit>`
- `ghcr.io/jdap-do/devops-grupo7-chatwoot:4.18.0-grupo7`

Se utiliza `GITHUB_TOKEN`, con permiso de escritura de paquetes en el job de
construccion y escaneo. El nombre del registro se obtiene del repositorio de
la ejecucion y se convierte a minusculas. Comprobar permisos y visibilidad del
paquete despues de la primera publicacion; estas rutas no son evidencia de
que ya exista una imagen publicada.

## Workflows heredados

Se conservaron los workflows originales. Todos sus jobs quedan restringidos
a `github.repository == 'chatwoot/chatwoot'`, manteniendo sus otras condiciones.
En el fork sus jobs se omiten; no se ejecutan pruebas o publicaciones del upstream.

| Categoria | Archivos |
| --- | --- |
| Imagenes y construccion | `publish_foss_docker.yml`, `publish_ee_docker.yml`, `publish_codespace_image.yml`, `test_docker_build.yml` |
| Pruebas y revision | `run_foss_spec.yml`, `run_mfa_spec.yml`, `frontend-fe.yml`, `size-limit.yml`, `logging_percentage_check.yml`, `lint_pr.yml` |
| Automatizacion externa | `deploy_check.yml`, `nightly_installer.yml`, `ghsa-linear-sync.yml` |
| Gestion de PR e issues | `auto-assign-pr.yml`, `stale.yml`, `lock.yml` |

Esto evita, entre otros, publicaciones dirigidas a `chatwoot/chatwoot` en
Docker Hub, llamadas a servicios de Linear y comprobaciones de aplicaciones
Heroku que pertenecen al proyecto original. El workflow propio del grupo es
el que realiza la validacion y publicacion de esta entrega.

## Correccion de vulnerabilidades de la imagen

El escaneo del PR #2 detecto CVE-2026-59873 en `tar` incluido en npm,
CVE-2026-42257 en la copia `net-imap 0.5.8` de la base Ruby y
CVE-2026-27820 en la gem predeterminada `zlib 3.2.1`.

La imagen utiliza ahora `ruby:3.4.11-slim-bookworm` como base de ambas etapas.
Ruby 3.4.11 incluye `net-imap 0.5.15` y `zlib 3.2.3`. Las referencias a Ruby
en Gemfile, lockfile, `.ruby-version` y las configuraciones Docker de desarrollo
se actualizaron para mantenerlas compatibles. La copia de `net-imap 0.6.4.1`
de Chatwoot ya estaba corregida. `scout_apm` se actualiza a la serie 5.7,
que corrige su compilacion nativa con GCC 15, tras el fallo comprobado de
la version 5.3.3 durante la prueba previa con Alpine. Las otras gems se mantienen bloqueadas.

La imagen de produccion copia el ejecutable Node, pero no npm ni sus paquetes
globales. npm y pnpm siguen disponibles en el builder; la copia de herramientas
en la etapa final se realiza solo cuando `RAILS_ENV` no es `production`.
El control de vulnerabilidades del workflow permanece habilitado.

La limpieza retira tambien `concurrent_ruby.jar`, incluido por concurrent-ruby
para JRuby. La imagen usa Ruby MRI y el
[cargador de concurrent-ruby](https://github.com/ruby-concurrency/concurrent-ruby/blob/v1.3.8/lib/concurrent-ruby/concurrent/utility/native_extension_loader.rb)
solo requiere ese archivo bajo JRuby. Ademas de retirar un artefacto de otra
plataforma, esto evita descargar la base Java de Trivy para analizarlo.

Fuentes: [aviso de net-imap](https://github.com/ruby/net-imap/security/advisories/GHSA-hm49-wcqc-g2xg),
[aviso de zlib](https://www.ruby-lang.org/en/news/2026/03/05/buffer-overflow-zlib-cve-2026-27820/),
[aviso de tar](https://github.com/advisories/GHSA-23hp-3jrh-7fpw) y
[compatibilidad de Scout con GCC 15](https://github.com/scoutapp/scout_apm_ruby/pull/552).

## Validacion local de la imagen optimizada

El 11 de octubre de 2026 (hora de Bogota) se construyo y verifico la imagen
`devops-grupo7/chatwoot:security-fix` con el codigo local modificado. Su revision
es `ffa40542b336b66a197cbffc1419c1be9ff75a2d-dirty`; no representa un commit limpio.
Docker reporto el identificador
`sha256:18345ef8943ed68fc17610b88065a95879883189bb122a3e64b903a664bdd133`
y un tamano de 452141675 bytes mediante `docker image inspect`.

- Hadolint, actionlint, yamllint y la validacion de Compose pasaron.
- gRPC cargo como `x86_64-linux` y Nokogiri como `x86_64-linux-gnu`.
  Se verificaron tambien PostgreSQL, libvips y concurrent-ruby bajo Ruby MRI.
- La imagen no contiene npm, gcc ni make. El binario exclusivo de JRuby se retiro.
- Una reconstruccion que cambio la limpieza final tardo 313.3 segundos en
  Docker Desktop. Bundler, pnpm y los recursos se reutilizaron como `CACHED`.
  Al repetir la instalacion de pnpm durante el ajuste se reutilizaron 1072
  paquetes sin nuevas descargas. Estas mediciones no garantizan tiempos en CI.
- El Compose existente arranco con un entorno y volumenes temporales separados.
  PostgreSQL y Redis quedaron saludables, `prepare` termino con codigo 0,
  el login y su JavaScript respondieron HTTP 200 y Sidekiq respondio HTTP 200
  en su comprobacion interna de salud.
- Trivy 0.70.0 genero el informe completo y paso con codigo 0 el mismo control
  de CI: `--severity CRITICAL --ignore-unfixed --exit-code 1`. Ninguno de los
  tres CVE originales aparece en el informe final.

El informe completo conserva ocho vulnerabilidades criticas sin una version
corregida disponible en los paquetes de Bookworm. No se agregaron exclusiones
para ellas ni se modifico la politica de CI:

| Paquete | CVE pendientes en Bookworm |
| --- | --- |
| libaom3 | CVE-2023-6879 |
| libglib2.0-0 | CVE-2026-58016 |
| libopenexr-3-1-30 | CVE-2023-5841, CVE-2026-42216, CVE-2026-42217 |
| libsqlite3-0 | CVE-2025-7458 |
| libxml2 | CVE-2026-6653 |
| zlib1g | CVE-2023-45853 |

Tambien permanecen hallazgos de otras severidades. El informe de Trivy y la
disponibilidad de parches deben revisarse de nuevo en cada construccion.

## Estado y pendientes

Los borradores de la carpeta padre se integraron y adaptaron localmente el
11 de octubre de 2026. Las verificaciones locales de la imagen optimizada se
registran arriba. El PR #2 ejecuto el workflow y fallo en el bloqueo de las
tres vulnerabilidades corregibles de la imagen anterior. Las correcciones
deben pasar de nuevo el workflow en GitHub; la validacion local no demuestra
que la persistencia de caches o la publicacion funcionen en ese entorno.

Falta registrar una ejecucion exitosa del workflow con estas correcciones,
repetir la conversacion visitante/agente con la imagen propia, publicar desde
`main`, comprobar la descarga del paquete y completar las evidencias del PDF.

El `.env` existente en el equipo de David pertenece a la ejecucion anterior de
desarrollo. No se sustituyo ni se incorporo a Git. Antes de arrancar la entrega,
adaptar su configuracion a `.env.entrega.example` con claves locales propias,
la base `chatwoot_production` y el acceso en `http://localhost:3001`.
