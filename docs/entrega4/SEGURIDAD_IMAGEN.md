# Mitigacion temporal de Active Storage

El PR 12 compilo correctamente, pero Trivy bloqueo la imagen por
`GHSA-f3w6-w445-fwh9` en `activestorage 7.2.3.1`. El aviso se publico el
4 de noviembre de 2026 y afecta al procesamiento de adjuntos con ImageMagick.
Las versiones corregidas publicadas son 8.0.5.2 y 8.1.4.1. Este cambio conserva
Rails 7.2 y aplica la alternativa de mitigacion documentada por Rails mientras
se planifica una actualizacion compatible de Chatwoot y sus dependencias.

## Cambio y alcance

- `docker/security/imagemagick-policy.xml` agrega las restricciones del aviso:
  scripting MSL, lecturas externas, coders de Ghostscript y otros interpretes,
  delegado `gs` y lectura indirecta `@archivo`.
- El Dockerfile incorpora esas reglas al final de la politica de ImageMagick 6
  de Debian. Conserva los limites de recursos y restricciones del sistema.
- La politica afecta al procesamiento mediante ImageMagick en Rails y Sidekiq.
  PNG y JPEG siguen funcionando; previsualizaciones de PDF/PostScript mediante
  ImageMagick quedan restringidas. Esto no equivale a prohibir todo adjunto PDF.
- No cambia la version instalada de Active Storage ni corrige todos los avisos
  de Rails. El hallazgo sigue presente en el informe completo de Trivy.

## Control en CI

Despues de construir y escanear la imagen, CI verifica sus reglas instaladas y
ejecuta pruebas con ImageMagick en esa misma imagen: conversion PNG/JPEG,
bloqueo de MSL, TEXT, PDF, PS y MPC por politica de seguridad, y bloqueo de
lectura indirecta. Un simple error de formato no cuenta como bloqueo valido.
Las pruebas se ejecutan sin red, con archivos temporales inocuos.

Solo si esas pruebas pasan se evalua el informe JSON completo de Trivy.
`check_critical_vulnerabilities.py` mantiene el bloqueo de vulnerabilidades
criticas con version corregida disponible. Acepta temporalmente un unico
identificador, paquete y version: `GHSA-f3w6-w445-fwh9`, `activestorage`,
`7.2.3.1`. La excepcion vence el **12 de noviembre de 2026 a las 00:00 UTC**;
desde ese momento CI falla hasta revisar o retirar esta decision.

El artefacto `trivy-<sha>` conserva el informe sin supresiones. No se usa una
lista general de avisos ignorados ni se reduce el nivel de bloqueo.

## Validacion y despliegue

Validacion local: se aplicaron las reglas sobre la imagen de Chatwoot existente
(`a07e19d2...`), y pasaron las pruebas de formatos, politica y lectura indirecta.
Tambien se verificaron el alcance y vencimiento de la excepcion y la sintaxis
del workflow. CI debe repetir las pruebas sobre la nueva imagen completa;
la prueba local no sustituye ese resultado.

Este commit **no modifica la VM ni la imagen que ya esta ejecutandose en GCP**.
Publicar y desplegar la nueva imagen, y comprobar el flujo visitante-agente,
son pasos posteriores. Hasta entonces la VM conserva la imagen anterior.
La migracion a Rails soportado y la retirada de esta excepcion quedan pendientes
del equipo antes de su vencimiento.

## Fuentes

- [Aviso y alternativa oficial de Rails](https://github.com/rails/rails/security/advisories/GHSA-f3w6-w445-fwh9).
- [Reglas de la politica publicada en Rails 8.0.5.2](https://github.com/rails/rails/blob/v8.0.5.2/activestorage/lib/active_storage/image_magick/policy.xml).
