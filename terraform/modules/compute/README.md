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

La configuración principal invoca este módulo después de persistence. Las comprobaciones del plan completo se ejecutan con terraform/policies/check-plan.ps1 -Configuration root, usando un estado aislado y sin aplicar recursos. No incluir en Git los directorios `.terraform`, los estados ni los planes generados.

## Estado de integración

El módulo pasó las comprobaciones locales de formato y validación con Terraform 1.16.6 y el proveedor Docker 4.6.0. La configuración principal conecta network, persistence y compute. Las conexiones de datos y el volumen de adjuntos llegan desde las salidas de persistence; las credenciales llegan desde las variables principales. La dependencia explícita de persistence permite esperar sus comprobaciones de salud antes de ejecutar prepare. El arranque real y el segundo plan sin cambios siguen pendientes de la prueba de despliegue.
