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
   siguen visibles, incluidas las de paquetes Alpine sin versiones fijadas.
2. yamllint revisa `compose.entrega.yml`, el workflow y su archivo de reglas.
3. Compose valida con `.env.entrega.example`, sin utilizar credenciales locales.
4. Buildx construye una imagen Linux amd64 desde el codigo del commit de la
   ejecucion. `SOURCE_REVISION` registra ese commit en `/app/.git_sha`.
5. Trivy genera un informe JSON completo, incluidos hallazgos sin correccion.
   El informe se conserva como artefacto del workflow.
6. Un segundo control bloquea las vulnerabilidades CRITICAL con correccion
   disponible. Esta politica no significa ausencia de otras vulnerabilidades;
   revisar tambien el informe completo para la entrega.

El Dockerfile limita gRPC a dos procesos e instala gems con dos trabajadores,
tras la compilacion local que necesito reducir el paralelismo. Este cambio
reduce el consumo simultaneo de recursos, pero puede alargar la construccion.
La imagen de produccion modificada debe construirse y verificarse en CI.

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

## Estado y pendientes

Los borradores de la carpeta padre se integraron y adaptaron localmente el
11 de octubre de 2026. La configuracion dispone de validaciones locales de
Dockerfile, YAML, workflow y Compose. Esto no prueba que la imagen modificada
se construya, que el escaneo pase o que la publicacion funcione en GitHub.

Falta registrar la primera ejecucion real del workflow, resolver sus fallos,
repetir la conversacion visitante/agente con la imagen propia, publicar desde
`main`, comprobar la descarga del paquete y completar las evidencias del PDF.

El `.env` existente en el equipo de David pertenece a la ejecucion anterior de
desarrollo. No se sustituyo ni se incorporo a Git. Antes de arrancar la entrega,
adaptar su configuracion a `.env.entrega.example` con claves locales propias,
la base `chatwoot_production` y el acceso en `http://localhost:3001`.
