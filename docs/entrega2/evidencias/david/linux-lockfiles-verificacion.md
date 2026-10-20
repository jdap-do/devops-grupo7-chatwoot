# Corrección de huellas para Linux

Fecha: 19 de octubre de 2026, Colombia.

## Fallo confirmado

El [run de Terraform sobre 0ad45635b0](https://github.com/jdap-do/devops-grupo7-chatwoot/actions/runs/39345562652/job/118377177938)
falló en el paso de validación del root. Init terminó con una advertencia de
lockfile sin actualizar; a continuación validate rechazó el paquete Docker
4.6.0 de `.terraform/providers` por no coincidir con las huellas registradas.
No fue un error de autenticación de HCP.

Se reprodujo el mismo fallo ejecutando init con `-lockfile=readonly` y validate
en Linux, desde una copia limpia del código. La huella `h1` de Windows del root
no permitía validar el paquete Linux descomprimido, aunque el lockfile incluía
huellas `zh` de los archivos de distribución.

## Cambio realizado

Se ejecutó `terraform providers lock -platform=windows_amd64 -platform=linux_amd64`
contra los registros oficiales para root y bootstrap. Se añadió una huella `h1`
Linux a cada lockfile, conservando las huellas Windows y las versiones Docker
4.6.0 y tfe 0.71.0. El ejemplo de persistencia ya tenía ambas plataformas y no
necesitó cambios. No se editaron huellas manualmente ni se desactivó su validación.

## Verificación posterior

Se usó un contenedor Linux limpio con Terraform 1.16.6, imagen fijada por digest:

```text
hashicorp/terraform:1.16.6@sha256:bfffc1ded5fbf0a17beaaf22eb4793980abdb19d0761ff6a3a0efb2ab4d9b316
```

Solo se copiaron código `.tf` y lockfiles al directorio de verificación. No se
copiaron estados, tfvars privados, credenciales, overrides locales ni cachés.

| Configuración | init sin backend, readonly | validate | Lockfile después de ejecutar |
| --- | --- | --- | --- |
| Root | Código 0 | Código 0 | SHA256 sin cambios |
| Bootstrap | Código 0 | Código 0 | SHA256 sin cambios |
| Ejemplo de persistencia | Código 0 | Código 0 | SHA256 sin cambios |

No se ejecutó apply ni se requirieron credenciales HCP. Esta prueba demuestra la
corrección de compatibilidad de los lockfiles en Linux; no demuestra que el root
ya conecte compute y persistence. Ese bloqueo de integración sigue descrito en
[compatibilidad-ci-verificacion.md](compatibilidad-ci-verificacion.md).
