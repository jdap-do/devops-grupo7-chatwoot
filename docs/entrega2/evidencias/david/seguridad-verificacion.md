# Verificación de políticas de seguridad

Fecha: 18 de octubre de 2026, Colombia.
Rama: `david/terraform-datos-gobernanza`; cambios locales aún sin commit.
Herramienta: Conftest 0.65.0 / OPA 1.11.0, imagen fijada por digest en el README.

| Comprobación | Resultado |
| --- | --- |
| Suite Rego de plan | 16 pruebas correctas |
| Suite Rego de fuente | 4 pruebas correctas |
| Código Terraform actual | 5 archivos, 30 comprobaciones correctas |
| Fixture de plan seguro | Aceptado, código 0 |
| Fixture de plan inseguro | Rechazado con 8 diagnósticos, código 1 |
| Fixture HCL seguro | Aceptado, código 0 |
| Fixture HCL inseguro | Rechazado con 5 diagnósticos, código 1 |
| Plan real del ejemplo | Sin cambios, código 0; aceptado por las políticas |
| Copia del plan real con `privileged=true` | Rechazada por P003, código 1 |

Las tablas de prueba verifican cada caso con `every`, incluyendo todas las
variantes de bind de Rails, tipos de montaje, valores desconocidos y defaults de
credenciales. La entrada incorrecta o vacía no se acepta como plan seguro.

Los datos inseguros son sintéticos. La modificación del plan real existió solo
en memoria: no se cambió el Terraform del módulo ni se ejecutó apply. El plan
binario se guardó únicamente en el directorio local ignorado del ejemplo; su JSON
se pasó por stdin a Conftest. No se adjuntaron planes ni estados.

El [extracto de resultados](seguridad-resultado.txt) conserva únicamente resultados
y códigos de salida del verificador local, sin valores de credenciales.
Para repetir las pruebas sin el despliegue personal:

```powershell
./terraform/policies/check.ps1
```

Este resultado es local. El workflow y TFLint ya están configurados y su
[verificación local](ci-verificacion-local.md) está documentada. Quedan pendientes
la ejecución alojada en GitHub Actions, la validación del root integrado y su
plan real con compute.
