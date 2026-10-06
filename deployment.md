# Deploying to Cloud Run

This describes how to run the reference app as a container, and how to put that
container on Google Cloud Run so Dialpad can frame it over HTTPS (for example in
dialpadbeta). Any container host works the same way; only the Cloud Run commands
are specific.

> **A demo, not a production setup.** The OAuth round trip is fake, and access
> tokens and finished OAuth results live in one process's memory. See
> [What to know before relying on it](#what-to-know-before-relying-on-it).

## What is in the image

The `Dockerfile` builds in two stages:

1. **Frontend.** Node 24 with Corepack runs `pnpm install --frozen-lockfile` and
   `pnpm build`, producing `dist/` (the hashed assets and Vite's manifest). The
   SDK installs from its tarball in `vendor/`.
2. **Backend.** A slim Python 3.14 image installs `requirements.txt` (Sanic and
   the toolkit wheel, also from `vendor/`), then copies in `backend/` and the
   built `dist/`. It runs as a non-root user and starts `python -m backend`,
   which serves the page and the API, and the built assets under `/assets`.

The image sets `HOST=0.0.0.0` and `PORT=8080`. It does not contain any secret or
URL: the environment variables below are passed when the container runs.

## Environment variables

See the [Configuration table in the README](README.md#configuration) for all of
them. A container needs these four, none of which is baked into the image:

| Variable                | Value                                                                     |
| ----------------------- | ------------------------------------------------------------------------- |
| `DIALPAD_CLIENT_SECRET` | The OAuth app's client secret (a secret: use Secret Manager on Cloud Run) |
| `APP_SECRET`            | A random secret that signs `state` and the cookie (also a secret)         |
| `DIALPAD_ORIGIN`        | `https://dialpadbeta.com` for beta, `https://dialpad.com` for production  |
| `BASE_URL`              | The public HTTPS URL of the service, without a trailing slash             |

Do not set `LOCAL_MODE`. The listen port comes from `PORT`; the port in
`BASE_URL` is not used when `PORT` is set, which is what a container host does.

If a variable is missing or malformed the container exits at once with a message
such as `DIALPAD_CLIENT_SECRET is required` or
`DIALPAD_ORIGIN must be a bare origin ...`, rather than failing on the first
request.

## Build and try the image locally

```sh
docker build -t acme-crm-demo .

docker run --rm -p 8080:8080 \
  -e DIALPAD_CLIENT_SECRET=... \
  -e APP_SECRET=... \
  -e DIALPAD_ORIGIN=https://dialpadbeta.com \
  -e BASE_URL=http://localhost:8080 \
  acme-crm-demo

curl http://localhost:8080/healthz   # ok
```

`BASE_URL` is only used to build the authorize and callback URLs, so locally it
can be the address you reach the container at. `http://localhost:8080/` with a
real Dialpad `idtoken` renders the panel page; a browser opening it directly
shows "Open this panel from Dialpad", because the SDK needs Dialpad to frame it.

Cloud Run runs on x86-64. On an Apple-silicon Mac, `docker build` makes an arm64
image; build with `--platform linux/amd64` to test what Cloud Run will run, or
let Cloud Build do the build (below).

## Deploy

None of the `gcloud` commands in this section were run while writing this
document; check them against the current Cloud Run documentation. Replace
`PROJECT`, `REGION` and the names to suit.

### 1. Enable the services and create a repository

```sh
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com secretmanager.googleapis.com

gcloud artifacts repositories create acme-crm \
  --repository-format=docker --location=REGION
```

### 2. Build and push the image

Cloud Build builds for the right architecture, from the repository root:

```sh
gcloud builds submit \
  --tag REGION-docker.pkg.dev/PROJECT/acme-crm/acme-crm-demo:latest .
```

`vendor/` is tracked in git, so it is uploaded with the source; the image needs
it.

### 3. Store the secrets

```sh
printf '%s' "$DIALPAD_CLIENT_SECRET" | gcloud secrets create dialpad-client-secret --data-file=-
openssl rand -hex 32 | tr -d '\n' | gcloud secrets create acme-app-secret --data-file=-
```

Grant the service's runtime service account the `Secret Manager Secret Accessor`
role on both.

### 4. Deploy

```sh
gcloud run deploy acme-crm-demo \
  --image REGION-docker.pkg.dev/PROJECT/acme-crm/acme-crm-demo:latest \
  --region REGION \
  --allow-unauthenticated \
  --port 8080 \
  --min-instances 1 --max-instances 1 \
  --set-env-vars DIALPAD_ORIGIN=https://dialpadbeta.com,BASE_URL=https://placeholder.example.com \
  --set-secrets DIALPAD_CLIENT_SECRET=dialpad-client-secret:latest,APP_SECRET=acme-app-secret:latest
```

- **`--allow-unauthenticated`:** Dialpad's iframe has to reach the service
  without a Google login.
- **`--min-instances 1 --max-instances 1`:** see the next section; this keeps
  the in-memory state in one place.
- **`BASE_URL` placeholder:** the service's URL isn't known until it exists, but
  the app refuses to start without a `BASE_URL`. Deploy with a placeholder, then
  set the real one:

```sh
URL=$(gcloud run services describe acme-crm-demo --region REGION --format='value(status.url)')
gcloud run services update acme-crm-demo --region REGION --update-env-vars BASE_URL=$URL
```

Until that update finishes, the authorize URLs the app builds point at the
placeholder.

You can also set a startup probe on `/healthz`, which answers `ok` once the app
is up.

### 5. Point Dialpad at it

Set the beta OAuth app's conversation sidebar URI to the service URL with a
trailing slash, for example `https://acme-crm-demo-xxxxxxxx-uc.a.run.app/`,
following Dialpad's runbook. Dialpad appends `?idtoken=...` itself. Open a
contact in dialpadbeta and the panel should appear.

## What to know before relying on it

- **State is in memory.** Access tokens and finished OAuth results live in one
  instance's memory. If Cloud Run ran several instances, the OAuth callback
  could record a result on one while the panel's polling asked another, and
  Connect would never finish. A restart or a scale-to-zero also forgets every
  access token, so open panels show "Reload the panel". Pinning to one instance,
  as above, avoids this for a demo. Anything beyond a demo needs a shared store
  (Redis, Firestore) and a durable access token store, as `backend/stores.py`
  says.
- **The idtoken is in the page URL.** It never expires, and the app avoids
  logging it (no access log, and a quiet error handler). Cloud Run also writes
  its own request log, which I believe includes the full request URL with the
  query string, but I have not verified that. Check what your project logs, and
  if the URL is there, add a Cloud Logging exclusion for the service's request
  logs or restrict who can read them.
- **The OAuth is fake.** `/oauth/fake-authorize` and `/oauth/callback` stand in
  for a CRM; a real partner replaces them (see the README's "What to replace").
- **Cookies.** The connection cookie is `Secure`, `HttpOnly`, `SameSite=None`
  and `Partitioned`, so it works in a third-party iframe over HTTPS. Cloud Run
  terminates TLS and the app sets the cookie regardless of the scheme it sees
  internally.

## What was checked

On a laptop, with Docker:

- The image builds for arm64 and for linux/amd64.
- The arm64 container runs as a non-root user and serves the page,
  `/assets/...`, `/healthz`, the fake authorize page and the callback;
  `ext-connection` then answers "connected" and sets the cookie with all its
  attributes. Neither the idtoken nor the access token appears in its logs.
- With a missing or malformed setting the container exits immediately with a
  clear message.
- The amd64 image, run under emulation with an HTTPS `BASE_URL` and `PORT=8080`,
  answers `/healthz` and serves the page.

Not checked: a real Cloud Run deployment, Cloud Build, Secret Manager, or what
Cloud Run logs.
