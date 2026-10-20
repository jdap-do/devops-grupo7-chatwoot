# Contrato de modulos - Entrega 2

Fecha: 19 de octubre de 2026. Base: entrega 1 integrada en main.
Estado: interfaz propuesta para desarrollar por separado; no es evidencia de despliegue.

## Responsabilidades

- Jose: modulos network y compute; archivos Terraform de la raiz salvo backend.tf; integracion y pruebas finales.
- David: modulo persistence, backend.tf, HCP Terraform, credenciales, politicas, workflow Terraform y exclusiones Git.
- Cada responsable modifica sus rutas. Los cambios de interfaz se comunican antes de modificar al consumidor.

## 1. Red: network (Jose)

Entrada: project_prefix (string), prefijo para separar el laboratorio de instalaciones anteriores.
Salida: network_name (string), nombre de la red que reciben compute y persistence.

Crear una red bridge Docker; permitir que Docker asigne una subred libre. No declarar recursos de nube que no existan realmente.

## 2. Datos: persistence (David)

Entradas:
- project_prefix (string).
- network_name (string).
- postgres_password (string, sensitive, sin valor predeterminado).
- redis_password (string, sensitive, sin valor predeterminado).

Salidas:
| Nombre | Tipo | Significado |
| --- | --- | --- |
| postgres_host | string | Nombre DNS interno de PostgreSQL |
| postgres_port | number | Puerto interno, 5432 |
| postgres_database | string | Base chatwoot_production |
| postgres_username | string | Usuario postgres |
| redis_host | string | Nombre DNS interno de Redis |
| redis_port | number | Puerto interno, 6379 |
| storage_volume_name | string | Volumen nombrado de adjuntos |

David crea PostgreSQL con pgvector, Redis y los volumenes de datos y adjuntos. No publica puertos de PostgreSQL ni Redis al anfitrion. Los nombres de host no deben ser localhost ni IPs fijas.

Configurar comprobaciones de salud y espera hasta disponibilidad real. Jose conecta compute despues de persistence mediante dependencia explicita entre modulos. El mecanismo del proveedor se debe validar: una salida llamada ready no demuestra salud.

Los volumenes pertenecen a persistence. Recrear Rails o Sidekiq no debe eliminarlos. No exponer contrasenas mediante outputs.

## 3. Aplicacion: compute (Jose)

Entradas: project_prefix, network_name, chatwoot_image (strings), app_port (number), secret_key_base, postgres_password y redis_password (strings sensibles, sin valores predeterminados), ademas de las siete salidas de persistence.

Root proporciona las mismas credenciales externas a compute y persistence; no se leen de outputs del modulo de datos.

Compute gestiona preparacion de base, Rails y Sidekiq. Los tres usan la imagen publicada de la entrega 1. Solo Rails publica puerto y lo hace en 127.0.0.1. El volumen storage_volume_name se monta en /app/storage.

La preparacion debe terminar correctamente antes de iniciar Rails y Sidekiq, sin causar cambios perpetuos al repetir plan. Este comportamiento se comprobara durante la implementacion.

Salida: app_url (string), direccion local del panel.

Imagen de referencia:

```text
ghcr.io/jdap-do/devops-grupo7-chatwoot@sha256:a07e19d2e177ca98acd3b00460e8366bc24bbc0268b0dcceb6566ed4516005e9
```

Prefijo propuesto en el equipo de Jose: devops-grupo7-e2-jose.
Puerto propuesto: 3010; verificar disponibilidad antes de aplicar.

## 4. Estado y configuracion externa

David prepara HCP Terraform Free con ejecucion Local. Un workspace se asocia a un solo Docker Desktop. Si David despliega en su computador, utiliza su propio workspace.

No versionar estados, planes, archivos con secretos ni tokens. sensitive oculta determinadas salidas, pero no impide que el proveedor almacene secretos en el estado; proteger su acceso.

El proveedor Docker se configura en root; los modulos declaran el mismo origen del proveedor. No fijar rutas o endpoints personales en codigo compartido. Las versiones se fijaran al preparar versions.tf y el lockfile, antes de que David inicialice sus modulos.

## 5. Trabajo independiente y documentacion

Jose desarrolla y valida network/compute contra esta interfaz. David desarrolla persistence y estado/CI en sus rutas. La prueba real del sistema completo se realiza al integrar ambas partes; ejemplos o mocks no se presentan como evidencia final.

Se conserva el documento de David y sus cuatro apartados:
1. Diseno de la Infraestructura: Jose.
2. Organizacion del Codigo: Jose explica estructura/modulos; David explica estado y credenciales.
3. Validacion y Gobernanza: David explica herramientas y CI; Jose aporta plan limpio y despliegue.
4. Enlaces del Proyecto: Jose.

Este contrato apoya el apartado 2 del informe. No es necesario pegarlo completo en el PDF: alli se resumiran las entradas, salidas y responsabilidades reales cuando se implementen.
