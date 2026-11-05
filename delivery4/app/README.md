# Primer arranque de Chatwoot en GCP

Adaptación del Compose de Entrega 1: los mismos componentes, imagen propia y
datos separados del laboratorio local. Terraform crea el anfitrión; Compose
administra los contenedores en él. `terraform/` y sus recursos locales no cambian.

La imagen Chatwoot y los digests PostgreSQL/Redis proceden de la configuración
Terraform de Entrega 2. No se utiliza `latest` ni se compila en la VM.

## Arranque en la VM

Copiar estos archivos al disco de datos y ejecutar:

```bash
sudo bash /srv/chatwoot/repo/delivery4/app/start.sh
```

El script comprueba el montaje y la raíz Docker antes de actuar; genera claves
nuevas solo si no existe `/srv/chatwoot/config/app.env`. Ese archivo pertenece a
root y tiene permisos 0600. Nunca mostrarlo con cat ni enviarlo a GitHub. No se
recrean contraseñas al repetir el arranque sobre una base existente.

Se descargan imágenes, se esperan dependencias saludables, se prepara la base y
se inician Rails y Sidekiq. Si falla la preparación, no continúa el script. El
HTTP 200 final solo prueba la respuesta de la página inicial; falta registrar
cuenta y comprobar una conversación/lectura autenticada.

Rails se publica solo en localhost:3000; PostgreSQL y Redis no tienen puertos del
host. El registro inicial está habilitado para crear la cuenta en este acceso
privado: deshabilitarlo antes de habilitar una entrada pública. URL y HTTPS
definitivos se configuran en una fase posterior; localhost no es el enlace de
entrega final.

Los volúmenes Docker residen en el disco de datos por la configuración del
anfitrión. `unless-stopped` permite restaurar contenedores al arrancar Docker
tras apagar la VM, salvo que hayan sido detenidos manualmente. Nunca usar
`down -v` para ahorrar ni para reiniciar. La preparación manual es temporal:
el futuro pipeline debe reutilizar el procedimiento y registrar cada versión.

Este arranque recrea una sola instancia al actualizar: no demuestra CD ni
actualización sin pérdida de disponibilidad. Ambas capacidades siguen pendientes.
