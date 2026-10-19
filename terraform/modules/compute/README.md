# Módulo de cómputo

Ejecuta Chatwoot con la imagen publicada en GHCR. Incluye la preparación de la base de datos, el servidor Rails y el trabajador Sidekiq.

## Recursos

| Recurso | Función |
| --- | --- |
| `chatwoot` | Descarga la imagen indicada por digest. |
| `prepare` | Ejecuta `db:chatwoot_prepare` y comprueba que termine con código 0. |
| `rails` | Publica la aplicación en `127.0.0.1` y en el puerto configurado. |
| `sidekiq` | Procesa las colas sin publicar puertos al anfitrión. |

Rails y Sidekiq dependen de `prepare`. Los tres contenedores montan el volumen de adjuntos proporcionado por `persistence`. La red, PostgreSQL, Redis y los volúmenes se administran fuera de este módulo.

## Configuración

Las entradas se declaran en `variables.tf`: prefijo, red, imagen, puerto, conexiones de datos, volumen de adjuntos y credenciales. Las credenciales se reciben como variables sensibles sin valores predeterminados. Pueden quedar almacenadas en el estado de Terraform, por lo que debe restringirse su acceso.

La salida `app_url` indica la dirección local del panel.

## Validación

Desde la raíz del repositorio:

```bash
terraform fmt -check -recursive terraform
terraform -chdir=terraform/modules/compute init -backend=false -input=false
terraform -chdir=terraform/modules/compute validate
```

Mientras la configuración principal no invoque este módulo, debe validarse por separado. No incluir en Git los directorios `.terraform`, los estados ni los planes generados.

## Estado de integración

El módulo pasó las comprobaciones locales de formato y validación con Terraform 1.16.6 y el proveedor Docker 4.6.0. Está pendiente conectarlo con `persistence` y comprobar el arranque y el segundo plan sin cambios. La configuración principal todavía incluye únicamente el módulo de red.
