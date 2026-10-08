# Builds the Acme CRM reference app for a container host such as Cloud Run (see deployment.md).
# Two stages: Node builds the Vue panel (client/) into dist/, then a slim Python image runs the
# Sanic server (server/), which serves dist/ under /assets.

# --- Stage 1: build the panel -------------------------------------------------------------------
FROM node:24-slim AS panel
WORKDIR /app

# pnpm comes from Corepack, at the version client/package.json pins.
RUN corepack enable

# Install dependencies first so this layer is cached until the manifests or vendor/ change. The SDK
# is installed from its tarball in client/vendor/, so that folder must be here before `pnpm install`.
COPY client/package.json client/pnpm-lock.yaml client/pnpm-workspace.yaml ./
COPY client/vendor ./vendor
RUN pnpm install --frozen-lockfile

# Type-check and build; this writes dist/ with the hashed assets and Vite's manifest.
COPY client/ .
RUN pnpm build

# --- Stage 2: the server ------------------------------------------------------------------------
FROM python:3.14-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# The server's requirements are all public packages.
COPY server/requirements.txt ./
RUN pip install -r requirements.txt

COPY server/acme_crm ./acme_crm
COPY --from=panel /app/dist ./dist

# Listen on every interface, as a container host requires. Cloud Run overrides PORT; elsewhere 8080
# is the default. The built panel is at /app/dist here, not at the ../client/dist the server looks
# for when run from server/. Secrets and URLs (DIALPAD_CLIENT_SECRET, APP_SECRET, DIALPAD_ORIGIN,
# BASE_URL) are not baked in: pass them as environment variables when you run the container.
ENV HOST=0.0.0.0 \
    PORT=8080 \
    DIST_DIR=dist
EXPOSE 8080

# Nothing here needs root.
RUN useradd --no-create-home --uid 10001 app
USER app

CMD ["python", "-m", "acme_crm"]
