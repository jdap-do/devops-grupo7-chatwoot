# Modulo compute

Responsable: Jose. Usa la imagen publicada de Chatwoot, sin construirla.

## Recursos

- docker_image.chatwoot: imagen por digest; keep_locally conserva la descarga al retirar el recurso.
- docker_container.prepare: ejecuta db:chatwoot_prepare y espera su terminacion; una salida distinta de 0 bloquea a los consumidores.
- docker_container.rails: servidor web; publica el puerto elegido solo en 127.0.0.1.
- docker_container.sidekiq: trabajador de colas, sin puertos publicados.

Rails y Sidekiq dependen de prepare. Los tres reciben configuracion compartida y montan el volumen de adjuntos creado por persistence. Compute no crea ni administra los volumenes de datos.

## Entradas y salida

variables.tf contiene el contrato: prefijo, red, imagen, puerto local, conexiones PostgreSQL/Redis, volumen de adjuntos y tres valores sensibles externos. Ninguna credencial tiene un valor predeterminado.

Salida: app_url, direccion local del panel. sensitive oculta determinados valores en la terminal, pero el proveedor puede conservarlos en el estado; se debe proteger el backend.

## Integracion pendiente

La configuracion principal todavia llama solo a network. Al integrar persistence, Jose conectara sus siete salidas con las entradas correspondientes de compute y pasara las mismas contrasenas externas a ambos modulos. La llamada a compute tendra dependencia explicita respecto a persistence, cuyos servicios deben esperar su salud real.

No ejecutar este modulo como despliegue completo sin la red, base, Redis, volumen y backend correctos. Las declaraciones no sustituyen las pruebas de arranque e idempotencia.

## Validacion para el pipeline de David

Mientras compute no este llamado por el root, terraform validate ejecutado solo en /terraform no lo valida. Inicializar y validar tambien modules/compute y modules/network, o usar una configuracion de comprobacion que los incluya. Utilizar init -backend=false y las versiones fijadas; no necesita secretos reales ni ejecutar apply.

Ejemplo de comprobaciones desde la raiz del repositorio, una vez configuradas las exclusiones de archivos generados:

```text
terraform fmt -check -recursive terraform
terraform -chdir=terraform/modules/compute init -backend=false -input=false
terraform -chdir=terraform/modules/compute validate
```

No versionar las carpetas .terraform, planes o estados generados por comprobaciones. El lockfile de la configuracion principal si se versiona. David define las exclusiones y el workflow en sus rutas.

## Estado comprobado

Formato y terraform validate aprobados localmente con Terraform 1.16.6 y kreuzwerker/docker 4.6.0. Las validaciones se ejecutaron en una copia temporal sin backend ni apply.

Pendientes: plan integrado, preparacion real con salida 0, salud de Rails/Sidekiq, conversacion y segundo plan sin cambios. La espera del contenedor temporal y su estabilidad deben comprobarse con ejecucion real; aun no se afirman como resultados.
