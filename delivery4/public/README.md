# Acceso publico HTTPS

Validado en GCP: certificados HTTPS, acceso autenticado a ambas aplicaciones y
conversacion visitante-agente en ambos sentidos. Una prueba posterior completo
60 solicitudes HTTP 200 y todas las comprobaciones de integracion del monitoreo.
Tambien se verifico la recuperacion despues de detener y encender la VM: cambio
la IP externa y ambas aplicaciones volvieron a abrir con los mismos dominios.
Chatwoot devolvio un 502 transitorio mientras arrancaba; no requirio reparacion
manual. Esperar el arranque antes de declarar una falla persistente.

- Chatwoot: https://grupo7-chatwoot-unal.duckdns.org → proxy existente en 3001.
- Grafana: https://grupo7-grafana-unal.duckdns.org → Grafana en 3005.
- Caddy usa red del host Linux; solo 80/443 se abren mediante `public.tf`.
- Certificados y configuracion persisten en `/srv/chatwoot/public/`.
- No se reserva IP estatica. El temporizador actualiza DuckDNS desde los
  metadatos de GCP al arrancar y cada dos minutos.
- Token: `/srv/chatwoot/config/duckdns-token`, propietario root y modo 0600.
  Nunca incluirlo en Git, argumentos de procesos, capturas ni salidas.
- Mantener deshabilitados el registro publico de cuentas y el acceso anonimo
  de Grafana. Ajustar FRONTEND_URL de Chatwoot y ROOT_URL de Grafana antes
  de publicar. Conservar las comprobaciones internas HTTP del despliegue.
- Al apagar la VM las paginas dejan de estar disponibles. Al encenderla puede
  existir demora de actualizacion DNS. Los discos siguen generando cargos;
  DNS y certificados no eliminan los costos de GCP.

La habilitacion del firewall esta desactivada por defecto. No habilitarla hasta
terminar la configuracion y verificar las credenciales.

## Configuracion aplicada

`prepare.py` se ejecuta con sudo dentro de la VM. Copia la configuracion a
`/srv/chatwoot/public`, valida Caddy e instala el servicio y temporizador de DNS.
El token se crea por separado y nunca se empaqueta con el codigo.

En `/srv/chatwoot/config/app.env` se conserva:

```dotenv
FRONTEND_URL=https://grupo7-chatwoot-unal.duckdns.org
ENABLE_ACCOUNT_SIGNUP=false
```

Tambien se deshabilita `ENABLE_ACCOUNT_SIGNUP` en InstallationConfig de Chatwoot.
El cambio de entorno requiere recrear Rails y Sidekiq del slot activo, usando su
archivo Compose original y su archivo de slot. Despues se valida y recarga Nginx
para resolver la direccion actual del contenedor, y se comprueba la API autenticada.
Esta operacion inicial puede interrumpir brevemente la aplicacion.

El archivo `delivery4/monitoring/compose.gcp.yml` configura la URL publica de
Grafana, el origen permitido y cookies seguras. Se aplica junto con
`observability/compose.yml`, conservando el archivo privado `.env.gcp`.

Caddy termina TLS y agrega Secure a las cookies de Chatwoot que salen al navegador.
Las comprobaciones internas del despliegue conservan HTTP; no se activa FORCE_SSL.
PostgreSQL, Redis, Prometheus y los puertos internos no se publican.

Para iniciar el acceso HTTPS preparado:

```bash
sudo docker compose -f /srv/chatwoot/public/compose.yml up -d
```

En Cloud Shell, guardar `enable_public_web = true` en el archivo privado
`infra/gcp/terraform.tfvars`, revisar el plan y aplicar el firewall. Mantener este
valor evita que una ejecucion posterior proponga quitar la regla web.

## Verificacion y operacion

Comprobar ambas URLs desde un equipo externo, sin omitir la validacion TLS.
La pagina `/demo-gcp.html?token=TOKEN_DEL_CANAL` utiliza el identificador publico
del canal web de Chatwoot; permite comprobar envio y respuesta desde el navegador.

El generador `observability/scripts/generate-traffic.py` y el validador
`observability/scripts/validate-integration.py` se ejecutan dentro de la VM.
Los SLIs actuales miden las lecturas autenticadas que atraviesan el gateway de
observabilidad; no representan todas las solicitudes publicas que recibe Caddy.

Al encender, revisar el temporizador `grupo7-duckdns.timer`, la ejecucion de
`grupo7-duckdns.service`, los contenedores y las dos URLs. El nombre DNS permanece
igual aunque cambie la IP. La disponibilidad depende de que la VM este encendida.
Conservar los directorios de certificados al actualizar Caddy.

Al finalizar el proyecto, respaldar evidencias y datos, desactivar CD y revisar
el plan de destruccion de Terraform. Comprobar aparte los recursos creados fuera
de Terraform y eliminar los subdominios cuando dejen de utilizarse.
