# Monitoreo de Entrega 3 en GCP

Estado: preparación y verificaciones locales; ejecución en GCP pendiente.
No se incluyen ni ejecutan escenarios GameDay. Su coordinación con David queda
pendiente por indicación del usuario; no se atribuye su implementación al equipo.

## Qué se reutiliza

`observability/compose.yml`, gateway instrumentado, sondas de dependencias,
exportador de memoria, Prometheus, Grafana, dashboard, recording rules,
alertas, Alertmanager y receptor webhook local. Se mantienen los SLOs y las
etiquetas project/environment. El historial GCP es nuevo y parcial; no mezcla
el almacenamiento de Prometheus del PC.

## Ajustes exclusivos de GCP

- Override de red hacia `devops-grupo7-gcp-network`, con origen Rails de GCP.
- Configuración de PostgreSQL/Redis tomada del archivo local de la VM, sin
  imprimir secretos ni copiarlos al paquete o al repositorio.
- Lectura del token del usuario y conversación ya existentes, como hacía
  `initialize-client.ps1`, adaptada a Python para Linux. Se usa admin@example.com
  de este laboratorio; no es una identidad dedicada de producción.
- Colector de memoria con nuevos argumentos opcionales `--suffix` y
  `--directory`: sus valores por defecto conservan el comportamiento local.
- Servicio systemd para muestrear memoria cada 15 segundos y reiniciar al
  encender la VM. El contenedor exportador solo recibe las muestras, no el
  socket Docker ni las credenciales guardadas en .runtime.

Los contenedores de aplicación GCP no tienen límites individuales de memoria;
no se inventan porcentajes respecto de límites ausentes. Se observan memoria
absoluta y conexiones de PostgreSQL. Los paneles relativos sin límite deben
interpretarse y revisarse, no presentarse como saturación cero.

## Arranque

Tras copiar el paquete y extraerlo en `/srv/chatwoot/repo`:

```bash
sudo bash /srv/chatwoot/repo/delivery4/monitoring/start.sh
```

La configuración de secretos no se sobrescribe si ya existe. La clave Grafana
se guarda en `observability/.runtime/grafana-admin-password.txt` dentro de un
directorio root 0700. No enviarla por el chat. El script construye los pequeños
adaptadores Python en la VM; Chatwoot sigue usando su imagen propia publicada.
La publicación de adaptadores en CI se evaluará al integrar el CD definitivo.

## Validación con tráfico nominal, sin fallas

Ejecutar en la VM:

```bash
sudo python3 /srv/chatwoot/repo/observability/scripts/generate-traffic.py --duration 180
sudo python3 /srv/chatwoot/repo/observability/scripts/validate-integration.py
```

El generador consulta las cuatro lecturas autenticadas cubiertas por el SLI a
través del gateway en localhost:3011. Es carga sintética nominal limitada; no
realiza inyecciones ni acredita capacidad máxima o 30 días de cumplimiento.
La validación comprueba reglas, calidad HTTP, indicadores/presupuestos,
dependencias, memoria, Grafana y receptor. No demuestra entrega de una alerta
real: esa prueba corresponde al ensayo coordinado posterior.

Puertos del servidor enlazados únicamente a localhost: Grafana 3005, Prometheus
9090, Alertmanager 9093 y receptor 3006. El acceso se realizará mediante túneles
IAP. No se exponen directamente al público. El receptor conserva avisos locales,
no envía correos ni mensajes a personas.

Al terminar, detener la VM según el acuerdo de ahorro. El monitoreo también se
detiene: ese intervalo no representa cobertura SRE ni disponibilidad confirmada.

## Pendientes

### Acceso mediante vista previa Cloud Shell

La revisión visual detectó `origin not allowed` pese a que las consultas locales
pasaron. La vista previa utiliza un hostname distinto del Host recibido por
Grafana. Se añade `GRAFANA_PREVIEW_HOST` a `.env.gcp` con el hostname exacto de
la vista previa (sin https, puerto ni ruta), que el override entrega mediante
`GF_SECURITY_CSRF_TRUSTED_ORIGINS`. Grafana 12.4 compara este hostname con el
Origin del navegador. No se desactiva CSRF ni se permiten comodines. Si cambia
la sesión de Cloud Shell, actualizar el hostname y recrear solo Grafana.

Después del ajuste se debe comprobar nuevamente el dashboard desde el navegador;
el resultado local sin Origin no prueba esta ruta de acceso.

Comprobar arranque, targets, carga, reglas, dashboard y acceso visual en GCP;
guardar resultados sin secretos; conectar después el CD. Los runbooks y los dos
incidentes quedan para coordinar con David.
