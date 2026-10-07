# Builds the Acme CRM reference app for a container host such as Cloud Run (see deployment.md).
# Two stages: Node builds the Vue frontend into dist/, then a slim Python image runs the Sanic
# backend, which serves dist/ under /assets.

# --- Stage 1: build the frontend ---------------------------------------------------------------
FROM node:24-slim AS frontend
WORKDIR /app

# pnpm comes from Corepack, at the version package.json pins.
RUN corepack enable

# Install dependencies first so this layer is cached until the manifests or vendor/ change. The SDK
# is installed from its tarball in vendor/, so that folder must be here before `pnpm install`.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY vendor ./vendor
RUN pnpm install --frozen-lockfile

# Type-check and build; this writes dist/ with the hashed assets and Vite's manifest.
COPY . .
RUN pnpm build

# --- Stage 2: the backend ----------------------------------------------------------------------
FROM python:3.14-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# The backend's requirements are all public packages.
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY backend ./backend
COPY --from=frontend /app/dist ./dist

# Listen on every interface, as a container host requires. Cloud Run overrides PORT; elsewhere 8080
# is the default. Secrets and URLs (DIALPAD_CLIENT_SECRET, APP_SECRET, DIALPAD_ORIGIN, BASE_URL)
# are not baked in: pass them as environment variables when you run the container.
ENV HOST=0.0.0.0 \
    PORT=8080
EXPOSE 8080

# Nothing here needs root.
RUN useradd --no-create-home --uid 10001 app
USER app

CMD ["python", "-m", "backend"]
