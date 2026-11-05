# Conexión de GitHub Actions con GCP

Estado: identidad preparada en Terraform; sin permisos aplicados ni despliegue
desde Actions demostrado. El arranque manual comprobado no equivale a CD.

Actualización: el usuario aplicó el plan de identidad en Cloud Shell y obtuvo
`11 added, 0 changed, 0 destroyed`. La identidad y sus permisos ya existen;
la autenticación desde Actions y el despliegue todavía no se han comprobado.

Variables de repositorio previstas (identificadores públicos, no secretos):

| Variable | Valor |
| --- | --- |
| `GCP_PROJECT_ID` | `project-45d258e3-00bf-4e6f-bbe` |
| `GCP_ZONE` | `us-central1-a` |
| `GCP_INSTANCE` | `grupo7-chatwoot` |
| `GCP_SERVICE_ACCOUNT` | `grupo7-github-deploy@project-45d258e3-00bf-4e6f-bbe.iam.gserviceaccount.com` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/1039954516938/locations/global/workloadIdentityPools/grupo7-github/providers/github-main` |

La configuración de estas variables en GitHub está pendiente de confirmación.

Actualización: captura del usuario confirma los cinco nombres en Repository
variables de Actions, con proyecto, instancia y zona coincidentes. Los dos
identificadores largos aparecen truncados en la UI; su valor completo se
comprobará mediante autenticación, sin asumirlo a partir de la captura.

## Primera ejecución: conexión sin despliegue

Se prepara `.github/workflows/grupo7-gcp-connection.yml`, manual y restringido a
main. Comprueba las variables, obtiene credenciales temporales, consulta que la
VM está encendida y conecta por IAP/OS Login para consultar el marcador de
preparación y los contenedores. La clave SSH creada por el runner expira a los
diez minutos. No copia la clave personal del usuario ni imprime configuración
de contenedores o secretos. No enciende la VM ni reinicia servicios.

El workflow debe revisarse y llegar a main antes de poder ejecutarlo desde
Actions con esa rama. Su éxito solo acredita el acceso requerido para CD; no
acredita actualización, reversión o continuidad. Ejecución real pendiente.

## Secuencia acordada

1. Crear la identidad de Actions mediante Terraform y revisar sus permisos.
2. Configurar variables del repositorio y publicar cambios revisados.
3. Comprobar autenticación y acceso a la VM desde una ejecución confiable.
4. Conectar la imagen publicada por CI con actualización y comprobación funcional.
5. Ensayar reversión y continuidad antes de declarar cumplimiento de Entrega 4.

Los incidentes siguen aplazados por indicación del usuario mientras coordina
con David. Estos pasos no ejecutan fallas ni cambian los objetivos SRE.

## Identidad y permisos

`infra/gcp/github.tf` se habilita con `enable_github_deploy = true` en las
entradas del workspace de infraestructura GCP. Mantener ese valor en el tfvars
local tras aplicar, pues devolverlo a false propondría retirar la identidad.

La federación OIDC de GitHub permite obtener credenciales temporales sin crear
claves JSON de cuenta de servicio ni guardar la clave SSH personal de José en
GitHub. Las condiciones admiten exclusivamente el ID de repositorio 1413754542,
el propietario 209687802 y `refs/heads/main`. Los IDs se comprobaron mediante la
API pública de GitHub. Un PR o una rama de trabajo no satisfacen esa condición.

Se crean pool/proveedor de federación y cuenta `grupo7-github-deploy`. Su alcance
es OS Admin Login en la VM `grupo7-chatwoot`, túnel IAP de esa VM en puerto 22 y
un rol de consulta con compute.projects.get, compute.instances.get y
compute.instances.list. No se otorgan Owner, Editor ni Instance Admin global.

OS Admin Login implica sudo en esa VM: la identidad puede controlar los
contenedores y acceder a la configuración privada del laboratorio. Por eso se
limita a main y requiere proteger las revisiones de código que llegan a ella.
Los permisos no facultan a crear máquinas, cambiar IAM o encender la VM por API.
Una ejecución del pipeline debe informar que el laboratorio está detenido en
lugar de encenderlo automáticamente, respetando el acuerdo de ahorro.

La VM no tiene cuenta de servicio adjunta; no se agrega una para autenticar
Actions. La cuenta de despliegue existe como identidad externa de operación.
Las APIs IAM, IAM Credentials y STS se habilitan con esta fase. El estado sigue
en HCP y no se mueve al repositorio.

## Revisión en Cloud Shell

Copiar `github.tf` a `infra/gcp/` del clon sin reemplazar main.tf, tfvars,
credenciales o estado. Confirmar y conservar en terraform.tfvars:

```hcl
enable_github_deploy = true
```

Después de exportar la organización y el workspace GCP ya confirmados:

```bash
terraform -chdir=infra/gcp validate
terraform -chdir=infra/gcp plan -out=github-identity.tfplan
```

Revisar que el plan no sustituya ni retire VM, disco o recursos de aplicación.
El bloque solo añade identidad, permisos y servicios. No ejecutar el apply de
un plan que contenga cambios imprevistos. Tras aplicar, registrar las salidas
`github_workload_identity_provider` y `github_service_account`: son
identificadores, no claves. La configuración de Actions se completará después;
todavía no se afirma que un push actualice el entorno.

## Fuentes técnicas

- https://github.com/google-github-actions/auth
- https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines
- https://docs.cloud.google.com/compute/docs/oslogin/set-up-oslogin

## Validación y pendientes

Validación estática contra el proveedor Google 7.0.0; plan y aplicación reales
pendientes en Cloud Shell. También siguen pendientes autenticación desde
Actions, publicación revisada del código, prueba del despliegue, continuidad,
reversión y acceso compartido de David con identidad propia.
