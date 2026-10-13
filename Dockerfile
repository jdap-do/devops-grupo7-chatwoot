# syntax=docker/dockerfile:1
# Empaquetar Chatwoot desde el codigo fuente con binarios compatibles con glibc.
# Etapa node: proporciona Node y npm para construir los recursos del frontend.
FROM node:24.13.0-bookworm-slim AS node
# Etapa base: bibliotecas y configuracion compartidas por el builder y la imagen final.
FROM ruby:3.4.11-slim-bookworm AS base

# Los argumentos se resuelven al construir; el modo predeterminado es produccion.
ARG RAILS_ENV=production
# Excluir las gems de desarrollo y pruebas en la instalacion de produccion.
ARG BUNDLE_WITHOUT="development:test"
# Permitir que Rails sirva los recursos compilados y deshabilitar ExecJS por defecto.
ARG RAILS_SERVE_STATIC_FILES=true
ARG EXECJS_RUNTIME="Disabled"
# Persistir la configuracion, instalar gems en /gems y restringir los cargadores de libvips.
ENV RAILS_ENV=${RAILS_ENV} \
    BUNDLE_WITHOUT=${BUNDLE_WITHOUT} \
    RAILS_SERVE_STATIC_FILES=${RAILS_SERVE_STATIC_FILES} \
    EXECJS_RUNTIME=${EXECJS_RUNTIME} \
    BUNDLE_PATH="/gems" \
    BUNDLER_VERSION=2.5.16 \
    VIPS_BLOCK_UNTRUSTED=1

# Bibliotecas y clientes de ejecucion; los compiladores quedan en el builder.
# Instalar certificados, procesamiento de imagenes, cliente PostgreSQL y zonas horarias.
# Omitir paquetes recomendados y retirar indices APT y documentacion de Bundler para reducir el tamano.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates imagemagick libpq5 libvips42 postgresql-client tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && gem install bundler -v "$BUNDLER_VERSION" --no-document

# Conservar el ejecutable Node sin incorporar aqui npm ni sus paquetes globales.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
# Las instalaciones, recursos y comandos de la aplicacion utilizan /app como directorio de trabajo.
WORKDIR /app

# Etapa pre-builder: instala dependencias y genera los recursos que recibe runtime.
FROM base AS pre-builder
# Fijar pnpm y limitar el heap de Node a 4096 MiB durante la compilacion del frontend.
ARG PNPM_VERSION="10.2.0"
ARG NODE_OPTIONS="--max-old-space-size=4096 --openssl-legacy-provider"
# Agregar el directorio de herramientas de pnpm al PATH de esta etapa.
ENV NODE_OPTIONS=${NODE_OPTIONS} \
    PNPM_HOME="/root/.local/share/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

# Instalar herramientas antes de copiar los manifiestos para conservar esta capa.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git libffi-dev libpq-dev libssl-dev libyaml-dev pkg-config xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Incorporar npm al builder, habilitar sus ejecutables e instalar la version fijada de pnpm.
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install -g pnpm@${PNPM_VERSION}

# Bundler puede elegir las gems Linux precompiladas del lockfile (incluido gRPC).
# Montar solo los paquetes descargados; las gems instaladas quedan dentro de /gems.
# Copiar manifiestos antes del codigo para reutilizar la instalacion si solo cambia la aplicacion.
COPY Gemfile Gemfile.lock ./
# Utilizar dos trabajadores y tres reintentos; sharing=locked protege la cache de escrituras simultaneas.
RUN --mount=type=cache,target=/gems/ruby/3.4.0/cache,sharing=locked \
    bundle install --jobs 2 --retry 3

# Instalar el frontend en otra capa, dependiente de sus propios manifiestos.
COPY package.json pnpm-lock.yaml ./
# Usar el mismo store en esta instalacion y en las tareas Rails que vuelven a ejecutar pnpm install.
ENV npm_config_store_dir=/pnpm/store
# Respetar el lockfile y recuperar paquetes descargados previamente en la cache de BuildKit.
RUN --mount=type=cache,target=/pnpm/store,sharing=locked \
    pnpm install --frozen-lockfile

# Incorporar el codigo permitido por .dockerignore; .env, Git y caches locales quedan fuera del contexto.
COPY . /app
# Normalizar scripts procedentes de Windows y preparar el directorio de logs.
RUN find docker bin -type f -exec sed -i 's/\r$//' {} + \
    && mkdir -p /app/log

# Compilar los recursos con una clave temporal y retirar dependencias del frontend.
# La clave real se proporciona al arrancar mediante .env; la cache de pnpm tambien se monta en este paso.
RUN --mount=type=cache,target=/pnpm/store,sharing=locked \
    if [ "$RAILS_ENV" = "production" ]; then \
    SECRET_KEY_BASE=precompile_placeholder RAILS_LOG_TO_STDOUT=enabled bundle exec rake assets:precompile \
    && rm -rf spec node_modules tmp/cache; \
    fi

# La revision cambia despues de los recursos para aprovechar su cache.
# Exigir un identificador de codigo y registrarlo sin necesitar .git dentro del contexto.
ARG SOURCE_REVISION
RUN test -n "$SOURCE_REVISION" && printf "%s\n" "$SOURCE_REVISION" > /app/.git_sha
# MRI no utiliza el binario Java de concurrent-ruby, que pertenece a JRuby.
# Retirar fuentes C, objetos de compilacion, paquetes descargados y metadatos Git antes de copiar a runtime.
RUN find /gems/ruby/3.4.0/gems/ \( -name "*.c" -o -name "*.o" \) -delete \
    && find /gems/ruby/3.4.0/gems/concurrent-ruby-* -name concurrent_ruby.jar -delete \
    && rm -rf /gems/ruby/3.4.0/cache /app/.git \
    && rm /app/.gitignore

# Etapa runtime: reutiliza la base y recibe solo las gems instaladas y la aplicacion preparada.
FROM base AS runtime
ARG PNPM_VERSION="10.2.0"

# Conservar herramientas para quien construya explicitamente en modo desarrollo.
# En produccion no se copian npm, pnpm, compiladores ni cabeceras.
RUN --mount=type=bind,from=node,source=/usr/local/lib/node_modules,target=/node_modules \
    if [ "$RAILS_ENV" != "production" ]; then \
    apt-get update && apt-get install -y --no-install-recommends \
      build-essential curl git libffi-dev libpq-dev libssl-dev libyaml-dev pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && cp -a /node_modules /usr/local/lib/node_modules \
    && ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install -g pnpm@${PNPM_VERSION}; \
    fi

# Copiar dependencias y codigo compilado sin volver a instalar gems ni construir el frontend.
COPY --from=pre-builder /gems/ /gems/
COPY --from=pre-builder /app/ /app/

# Compose proporciona el comando de Rails o Sidekiq para la misma imagen.
# EXPOSE documenta el puerto interno; su publicacion en el host se configura en Compose.
EXPOSE 3000
