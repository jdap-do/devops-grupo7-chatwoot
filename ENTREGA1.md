# Grupo 7 — Entrega 1

Base: Chatwoot v4.18.0, commit `9f920b549c14491a4e587687a3eed5d21c6ccc7d`.

## Construcción local

```powershell
docker build --build-arg SOURCE_REVISION=9f920b549c14491a4e587687a3eed5d21c6ccc7d -t devops-grupo7/chatwoot:4.18.0 -f Dockerfile .
```

El Dockerfile deriva del oficial de v4.18.0. Mantiene compilación por etapas, instala solo las gems de producción y limpia recursos de construcción. Fija Node 24.13.0 y pnpm 10.2.0; pnpm respeta su lockfile. SOURCE_REVISION identifica el código sin incluir .git. Los scripts se normalizan a finales de línea Linux al construir desde Windows.

## Configuración y arranque

Crear `.env` a partir de `.env.entrega.example` y reemplazar las tres claves de ejemplo por valores aleatorios. No publicar `.env`.

```powershell
docker compose -f compose.entrega.yml config --quiet
docker compose -f compose.entrega.yml up -d --build
```

Compose espera los controles de disponibilidad de PostgreSQL y Redis. El servicio temporal `prepare` prepara la base; Rails y Sidekiq arrancan solo después de su terminación exitosa. Acceso: http://localhost:3001. El puerto y el nombre de proyecto separan esta instalación de la prueba anterior en 3000. Los volúmenes pertenecen a `devops-grupo7`.

## Estado

Imagen propia construida y arrancada localmente el 10 de octubre de 2026. La preparación inicial terminó con código 0; PostgreSQL y Redis saludables; Rails respondió HTTP 200 en localhost:3001 y Sidekiq se conectó a Redis. La prueba se realizó desde volúmenes nuevos con docker compose -f compose.entrega.yml up -d --no-build. Falta probar una conversación sobre esta imagen y completar el pipeline, escaneo y publicación.

## Licencia

Conservar LICENSE y los avisos originales. El contenido de enterprise/ tiene licencia distinta del código MIT; no afirmar que todo el repositorio está bajo MIT.
