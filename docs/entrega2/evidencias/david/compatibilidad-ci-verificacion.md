# Compatibilidad de versiones y ampliación de CI

Fecha: 19 de octubre de 2026, Colombia.
Rama: `david/terraform-datos-gobernanza`.
Base de José incorporada mediante fast-forward: `4ea19e8e4b`.
Los archivos de José no se modificaron; los cambios de David siguen locales.

## Proveedor Docker

Persistence y su ejemplo ahora requieren Terraform `>= 1.16.6, < 2.0.0` y
`kreuzwerker/docker = 4.6.0`, coincidiendo con root, network y compute.
Se regeneró el lockfile del ejemplo con checksums de Windows AMD64 y Linux AMD64.

| Comprobación | Resultado |
| --- | --- |
| Init del ejemplo con upgrade | Provider 4.6.0 instalado |
| Validate del ejemplo | Código 0 |
| Plan sobre estado HCP existente | Sin cambios, código 0; sin apply |
| Plan aislado sin estado previo | 8 creaciones; políticas: 13 comprobaciones correctas |
| Formato Terraform recursivo | Código 0 |

No se recrearon contenedores ni volúmenes para esta actualización. El estado
HCP corresponde al ejemplo de David, no a un despliegue completo de Chatwoot.
Las pruebas anteriores de aprovisionamiento y conservación de datos con 3.6.2
son históricas; no se presentan como un apply realizado con 4.6.0.

## CI ampliado

El workflow ahora recorre todo `terraform/` con TFLint, inicializa y valida root
sin backend y ejecuta `check-plan.ps1 -Configuration root`. Este último copia
código y lockfile a un directorio temporal; excluye backend, estado y archivos
locales. Usa entradas efímeras y solo permite acciones de creación, sin apply.
Exige los tres módulos del contrato y aplica las políticas al plan completo.

| Comprobación local | Resultado |
| --- | --- |
| Root init con backend deshabilitado y lockfile readonly | Código 0 |
| Root validate | Código 0 |
| TFLint recursivo de todo Terraform | Código 0 |
| actionlint del workflow actualizado | Código 0 |
| Suites Rego | 16 de plan y 4 de fuente aprobadas |
| Revisión del HCL actual | 156 comprobaciones aprobadas |
| Fixtures inseguros | Rechazados con código y diagnóstico esperados |
| Script de políticas tras los rechazos esperados | Código 0 explícito para el runner pwsh |
| Plan del root actual | Rechazado: faltan módulos persistence y compute |

El último resultado es un bloqueo de integración real: el root publicado por
José solo declara la red. El nuevo paso de CI fallará hasta que José conecte
los módulos y el plan completo supere las políticas. No se añadió una omisión
del control ni se declararon exitosas políticas sobre recursos aún no llamados.

Esta evidencia es local. Sigue pendiente publicar los cambios y obtener un run
real de GitHub Actions sobre el código integrado. Las pruebas no usaron el
estado de José ni publicaron planes, estados o credenciales como artefactos.
