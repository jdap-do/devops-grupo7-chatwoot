# Adaptado de docker/Dockerfile de Chatwoot v4.18.0.
# Construye la aplicacion desde el codigo fuente; no utiliza una imagen Chatwoot precompilada.
# Etapas de construccion: Node aporta el ejecutable y Ruby instala las gems
# y compila los recursos que se copiaran a la imagen final.
FROM node:24.13.0-alpine AS node
FROM ruby:3.4.4-alpine3.21 AS pre-builder

ARG NODE_VERSION="24.13.0"
ARG PNPM_VERSION="10.2.0"
ENV NODE_VERSION=${NODE_VERSION}
ENV PNPM_VERSION=${PNPM_VERSION}

# La configuracion predeterminada es de produccion. Estos argumentos permiten
# ajustar la construccion sin incorporar las credenciales del entorno local.
ARG BUNDLE_WITHOUT="development:test"
ENV BUNDLE_WITHOUT=${BUNDLE_WITHOUT}
ENV BUNDLER_VERSION=2.5.16
ENV GRPC_RUBY_BUILD_PROCS=2

ARG RAILS_SERVE_STATIC_FILES=true
ENV RAILS_SERVE_STATIC_FILES=${RAILS_SERVE_STATIC_FILES}

ARG RAILS_ENV=production
ENV RAILS_ENV=${RAILS_ENV}

# Limitar el heap de Node a 4096 MiB durante la compilacion.
ARG NODE_OPTIONS="--max-old-space-size=4096 --openssl-legacy-provider"
ENV NODE_OPTIONS=${NODE_OPTIONS}

ENV BUNDLE_PATH="/gems"

RUN apk update && apk add --no-cache \
  openssl \
  tar \
  build-base \
  tzdata \
  postgresql-dev \
  postgresql-client \
  git \
  curl \
  xz \
  && mkdir -p /var/app \
  && gem install bundler -v "$BUNDLER_VERSION"

COPY --from=node /usr/local/bin/node /usr/local/bin/
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
  && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN npm install -g pnpm@${PNPM_VERSION}

RUN echo 'export PNPM_HOME="/root/.local/share/pnpm"' >> /root/.shrc \
  && echo 'export PATH="$PNPM_HOME:$PATH"' >> /root/.shrc \
  && export PNPM_HOME="/root/.local/share/pnpm" \
  && export PATH="$PNPM_HOME:$PATH" \
  && pnpm --version

# pnpm necesita esta ruta durante la instalacion y compilacion del frontend.
ENV PNPM_HOME="/root/.local/share/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

WORKDIR /app

# Copiar primero los manifiestos para reutilizar esta capa si solo cambia el codigo.
COPY Gemfile Gemfile.lock ./

# Alpine utiliza musl. Algunas gems, como gRPC, requieren compilacion nativa.
# Las herramientas y cabeceras siguientes mantienen el comportamiento del Dockerfile oficial.
# https://github.com/googleapis/google-cloud-ruby/issues/13306
# xz se conserva por la compilacion de libxml utilizada por Nokogiri.
# https://github.com/chatwoot/chatwoot/issues/4045
RUN apk update && apk add --no-cache build-base musl ruby-full ruby-dev gcc make musl-dev openssl openssl-dev g++ linux-headers xz vips
RUN bundle config set --local force_ruby_platform true

# Excluir dependencias de desarrollo y pruebas en la construccion de produccion.
RUN if [ "$RAILS_ENV" = "production" ]; then \
  bundle config set without 'development test'; bundle install -j 2 -r 3; \
  else bundle install -j 2 -r 3; \
  fi

# Respetar las versiones resueltas en el lockfile; fallar si no coincide con package.json.
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . /app
# Normalizar scripts a finales de linea Linux cuando el contexto proviene de Windows.
RUN find docker bin -type f -exec sed -i 's/\r$//' {} +

# Mantener el directorio de registros si la aplicacion no envia los logs a stdout.
# https://github.com/chatwoot/chatwoot/issues/701
RUN mkdir -p /app/log

# Compilar JavaScript y CSS para servirlos sin un servidor de desarrollo.
# SECRET_KEY_BASE es un valor temporal de compilacion; la clave real se proporciona al arrancar.
# Los tests, node_modules y la cache no se necesitan despues de generar los recursos.
RUN if [ "$RAILS_ENV" = "production" ]; then \
  SECRET_KEY_BASE=precompile_placeholder RAILS_LOG_TO_STDOUT=enabled bundle exec rake assets:precompile \
  && rm -rf spec node_modules tmp/cache; \
  fi

# Registrar la revision indicada por quien construye la imagen.
# El argumento es obligatorio y evita depender de .git dentro del contexto.
ARG SOURCE_REVISION
RUN test -n "$SOURCE_REVISION" && printf "%s\n" "$SOURCE_REVISION" > /app/.git_sha

# Limpiar paquetes descargados y archivos de compilacion antes de copiar las gems.
# Esta limpieza reduce lo transferido a la etapa final; no elimina todas las herramientas heredadas.
RUN rm -rf /gems/ruby/3.4.0/cache/*.gem \
  && find /gems/ruby/3.4.0/gems/ \( -name "*.c" -o -name "*.o" \) -delete \
  && rm -rf .git \
  && rm .gitignore

# Imagen de ejecucion: recibe las dependencias instaladas y la aplicacion compilada.
# No instala de nuevo las dependencias del proyecto ni recompila el frontend.
FROM ruby:3.4.4-alpine3.21

ARG NODE_VERSION="24.13.0"
ARG PNPM_VERSION="10.2.0"
ENV NODE_VERSION=${NODE_VERSION}
ENV PNPM_VERSION=${PNPM_VERSION}

ARG BUNDLE_WITHOUT="development:test"
ENV BUNDLE_WITHOUT=${BUNDLE_WITHOUT}
ENV BUNDLER_VERSION=2.5.16

ARG EXECJS_RUNTIME="Disabled"
ENV EXECJS_RUNTIME=${EXECJS_RUNTIME}

ARG RAILS_SERVE_STATIC_FILES=true
ENV RAILS_SERVE_STATIC_FILES=${RAILS_SERVE_STATIC_FILES}

ARG BUNDLE_FORCE_RUBY_PLATFORM=1
ENV BUNDLE_FORCE_RUBY_PLATFORM=${BUNDLE_FORCE_RUBY_PLATFORM}

ARG RAILS_ENV=production
ENV RAILS_ENV=${RAILS_ENV}
ENV BUNDLE_PATH="/gems"

# Conservar los paquetes de ejecucion del oficial, incluido build-base por compatibilidad.
# Su retirada requiere una verificacion adicional y queda fuera de este cambio de comentarios.
RUN apk update && apk add --no-cache \
  build-base \
  openssl \
  tzdata \
  postgresql-client \
  imagemagick \
  git \
  vips \
  && gem install bundler -v "$BUNDLER_VERSION"

# Restringir libvips a los cargadores de imagen que considera confiables.
ENV VIPS_BLOCK_UNTRUSTED=1

COPY --from=node /usr/local/bin/node /usr/local/bin/
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules

RUN if [ "$RAILS_ENV" != "production" ]; then \
  apk add --no-cache curl \
  && ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
  && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
  && npm install -g pnpm@${PNPM_VERSION} \
  && pnpm --version; \
  fi

COPY --from=pre-builder /gems/ /gems/
COPY --from=pre-builder /app /app

# Conservar el identificador de revision en la imagen de ejecucion.
COPY --from=pre-builder /app/.git_sha /app/.git_sha

WORKDIR /app

# Documentar el puerto interno. Compose decide si se publica y con que puerto del host.
# Rails y Sidekiq usan la misma imagen; Compose proporciona el comando de cada servicio.
EXPOSE 3000
