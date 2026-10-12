# syntax=docker/dockerfile:1
# Empaquetar Chatwoot desde el codigo fuente con binarios compatibles con glibc.
FROM node:24.13.0-bookworm-slim AS node
FROM ruby:3.4.11-slim-bookworm AS base

ARG RAILS_ENV=production
ARG BUNDLE_WITHOUT="development:test"
ARG RAILS_SERVE_STATIC_FILES=true
ARG EXECJS_RUNTIME="Disabled"
ENV RAILS_ENV=${RAILS_ENV} \
    BUNDLE_WITHOUT=${BUNDLE_WITHOUT} \
    RAILS_SERVE_STATIC_FILES=${RAILS_SERVE_STATIC_FILES} \
    EXECJS_RUNTIME=${EXECJS_RUNTIME} \
    BUNDLE_PATH="/gems" \
    BUNDLER_VERSION=2.5.16 \
    VIPS_BLOCK_UNTRUSTED=1

# Bibliotecas y clientes de ejecucion; los compiladores quedan en el builder.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates imagemagick libpq5 libvips42 postgresql-client tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && gem install bundler -v "$BUNDLER_VERSION" --no-document

COPY --from=node /usr/local/bin/node /usr/local/bin/node
WORKDIR /app

FROM base AS pre-builder
ARG PNPM_VERSION="10.2.0"
ARG NODE_OPTIONS="--max-old-space-size=4096 --openssl-legacy-provider"
ENV NODE_OPTIONS=${NODE_OPTIONS} \
    PNPM_HOME="/root/.local/share/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

# Instalar herramientas antes de copiar los manifiestos para conservar esta capa.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git libffi-dev libpq-dev libssl-dev libyaml-dev pkg-config xz-utils \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install -g pnpm@${PNPM_VERSION}

# Bundler puede elegir las gems Linux precompiladas del lockfile (incluido gRPC).
# Montar solo los paquetes descargados; las gems instaladas quedan dentro de /gems.
COPY Gemfile Gemfile.lock ./
RUN --mount=type=cache,target=/gems/ruby/3.4.0/cache,sharing=locked \
    bundle install --jobs 2 --retry 3

COPY package.json pnpm-lock.yaml ./
ENV npm_config_store_dir=/pnpm/store
RUN --mount=type=cache,target=/pnpm/store,sharing=locked \
    pnpm install --frozen-lockfile

COPY . /app
RUN find docker bin -type f -exec sed -i 's/\r$//' {} + \
    && mkdir -p /app/log

# Compilar los recursos con una clave temporal y retirar dependencias del frontend.
RUN --mount=type=cache,target=/pnpm/store,sharing=locked \
    if [ "$RAILS_ENV" = "production" ]; then \
    SECRET_KEY_BASE=precompile_placeholder RAILS_LOG_TO_STDOUT=enabled bundle exec rake assets:precompile \
    && rm -rf spec node_modules tmp/cache; \
    fi

# La revision cambia despues de los recursos para aprovechar su cache.
ARG SOURCE_REVISION
RUN test -n "$SOURCE_REVISION" && printf "%s\n" "$SOURCE_REVISION" > /app/.git_sha
# MRI no utiliza el binario Java de concurrent-ruby, que pertenece a JRuby.
RUN find /gems/ruby/3.4.0/gems/ \( -name "*.c" -o -name "*.o" \) -delete \
    && find /gems/ruby/3.4.0/gems/concurrent-ruby-* -name concurrent_ruby.jar -delete \
    && rm -rf /gems/ruby/3.4.0/cache /app/.git \
    && rm /app/.gitignore

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

COPY --from=pre-builder /gems/ /gems/
COPY --from=pre-builder /app/ /app/

# Compose proporciona el comando de Rails o Sidekiq para la misma imagen.
EXPOSE 3000
