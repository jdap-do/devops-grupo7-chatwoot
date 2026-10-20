# Verificación local de la integración CI

Fecha: 18 de octubre de 2026, Colombia.
Rama: `david/terraform-datos-gobernanza`, cambios locales aún sin commit.

Workflow preparado: `.github/workflows/grupo7-terraform.yml`.
No se ha publicado la rama ni ejecutado este workflow en GitHub. Este archivo
registra comprobaciones locales, no evidencia de un run remoto.

| Comprobación | Resultado local |
| --- | --- |
| `terraform fmt -check -recursive terraform` | Código 0 |
| TFLint 0.58.1 con `.tflint.hcl` | Código 0, sin hallazgos |
| actionlint 1.7.7 sobre el workflow nuevo | Código 0, sin hallazgos |
| Suites Conftest | 20 pruebas correctas; ver evidencia de seguridad |
| `check-plan.ps1` | Código 0 |
| Init aislado | Provider Docker 3.6.2 instalado según lockfile de solo lectura |
| Validate aislado | Configuración válida |
| Plan desde estado vacío | 8 creaciones, 0 cambios y 0 destrucciones |
| Políticas sobre ese plan inicial | 13 comprobaciones correctas, código 0 |
| Limpieza | Directorio temporal eliminado al terminar |

Salida final observada:

```text
Plan: 8 to add, 0 to change, 0 to destroy.
13 tests, 13 passed, 0 warnings, 0 failures, 0 exceptions
PASS: isolated empty-state plan (8 creations) accepted; no apply or personal state used.
```

El primer ensayo del plan inicial bloqueó `ipc_mode` porque su valor era
desconocido antes de crear los contenedores. Se declaró `private` explícitamente
en PostgreSQL y Redis y el siguiente plan pasó, conservando la regla que rechaza
atributos de seguridad desconocidos.

El ensayo utilizó el motor Docker local solo para la operación de plan. No leyó
el estado del despliegue, no hizo apply y no utilizó las contraseñas persistentes
del laboratorio. Las contraseñas efímeras no se muestran en esta evidencia.

En GitHub, el mismo paso utilizará el Docker del runner Ubuntu 24.04. La
verificación local se ejecutó desde Windows; falta comprobar y enlazar la
ejecución alojada, incluyendo la instalación de herramientas en ese runner.
No se han probado todavía root, network o compute de José.
