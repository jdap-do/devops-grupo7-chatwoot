# Verificación de estado remoto

Fecha: 19 de octubre de 2026, Colombia.
Rama: `david/terraform-datos-gobernanza`, cambios locales aún sin commit.
Organización indicada: `team7-devops-2026-2-org`.

## Comprobaciones locales realizadas

| Comprobación | Resultado |
| --- | --- |
| Instalación del provider HCP | `hashicorp/tfe` 0.71.0, firmado por HashiCorp |
| Bootstrap Terraform validate | Código 0 |
| Sintaxis del root con bloque cloud | Terraform validate, código 0 |
| Formato Terraform | Código 0 |
| TFLint de módulos y bootstrap | Código 0 |
| actionlint del workflow actualizado | Código 0 |
| Suites Rego | 16 pruebas de plan y 4 de fuente correctas |
| Revisión HCL actual | 10 archivos, 60 comprobaciones correctas |
| Exclusiones Git | Token cifrado, tfvars, estados y override cloud local excluidos |
| Scripts de autenticación y conexión | Sintaxis válida para Windows PowerShell 5.1 |

## Evidencia remota verificada

La API confirmó acceso de `dzambranob` a la organización indicada.
Terraform creó el workspace y sus ajustes: **2 creados, 0 modificados,
0 destruidos**. El segundo plan del bootstrap terminó sin cambios, código 0.

- Workspace: [grupo7-e2-david-persistence](https://app.terraform.io/app/team7-devops-2026-2-org/workspaces/grupo7-e2-david-persistence).
- ID: `ws-aqBXKAeSLYMbDnbF`.
- Ejecución comprobada por API: `local`.
- Equipo: `DZAMBRANOB`; contexto: `desktop-linux`; configuración: `persistence-example`.
- Versión de estado comprobada: `sv-YL5GwFoNJa93Q2cE`.
- Estado remoto: 8 recursos, con las mismas direcciones e identificadores que
  el respaldo local previo a la migración.
- Plan posterior a la migración: sin cambios, código 0.

Antes de migrar se detectaron ausentes los dos contenedores de prueba. Los tres
volúmenes seguían presentes; solo se recrearon los contenedores, conservando los
volúmenes y las credenciales. El plan de restauración pasó las 13 comprobaciones
de políticas. Después se obtuvo un plan local sin cambios y se respaldó el estado.

La primera inicialización con `TF_WORKSPACE` seleccionó un estado vacío y no
migró los recursos. No se ejecutó apply sobre ese estado remoto vacío. Se
repitió init desde el respaldo verificado, con el nombre destino explícito en
el archivo cloud local y sin `TF_WORKSPACE`. Tras confirmar el diálogo de
migración, HCP recibió los ocho recursos. HCP asignó un linaje nuevo y serial 1
frente al serial 23 del origen; se verificó continuidad mediante direcciones,
identificadores y plan sin cambios. El procedimiento y el script se ajustaron
para impedir repetir la selección anticipada sobre un estado local con recursos.

El bootstrap conserva su estado local protegido. Los respaldos, estados y
credenciales están excluidos de Git. No se publican sus contenidos.

La reconexión posterior mediante `state-init.ps1` terminó correctamente. Los
marcadores de prueba con valor `7` seguían presentes en PostgreSQL y Redis.
Después de incorporar el archivo cloud local se repitió `check-plan.ps1`:
validación correcta, plan aislado de 8 creaciones y 13 comprobaciones de
políticas aprobadas, sin apply ni uso del estado personal.

## Pendiente para el despliegue completo

Confirmar equipo y contexto de José para aprovisionar su workspace, integrar su
root y comprobar el despliegue completo con su propio estado. Esta evidencia
demuestra el estado remoto del ejemplo de persistencia de David.

Las instrucciones de operación están en
[estado-credenciales.md](../../estado-credenciales.md).
