# Deploying to Cloud Run

This describes how to run the reference app as a container, and how to put that
container on Google Cloud Run so Dialpad can frame it over HTTPS (for example in
dialpadbeta). Any container host works the same way; only the Cloud Run commands
are specific.

> **A demo, not a production setup.** The OAuth round trip is fake, and finished
> OAuth results live in one process's memory. See
> [What to know before relying on it](#what-to-know-before-relying-on-it).

## What is in the image

The [`Dockerfile`](Dockerfile) builds in two stages, from the repository root as
its context (it needs both `client/` and `server/`; its ignore file is
[`Dockerfile.dockerignore`](Dockerfile.dockerignore)):

1. **Iframe panel.** Node 24 with Corepack runs `pnpm install --frozen-lockfile` and
   `pnpm build` in `client/`, producing `dist/` (the hashed assets and Vite's
   manifest). The SDK installs from its tarball in `client/vendor/`.
2. **Server.** A slim Python 3.14 image installs `server/requirements.txt`
   (public packages only), then copies in `server/acme_dialpad_rightbar/` and the built
   `dist/`. It runs as a non-root user and starts `python -m acme_dialpad_rightbar`, which
   serves the page and the API, and the built assets under `/assets`.

The image sets `HOST=0.0.0.0`, `PORT=8080` and `DIST_DIR=dist` (where it keeps
the built iframe panel). It does not contain any secret or URL: the environment
variables below are passed when the container runs.

## Environment variables

See the [Configuration table in the README](../README.md#configuration) for all of
them. A container needs these four, none of which is baked into the image:

| Variable                | Value                                                                    |
| ----------------------- | ------------------------------------------------------------------------ |
| `DIALPAD_CLIENT_SECRET` | The OAuth app's client secret                                            |
| `APP_SECRET`            | A random secret that signs `state` and the cookie                        |
| `DIALPAD_ORIGIN`        | `https://dialpadbeta.com` for beta, `https://dialpad.com` for production |
| `BASE_URL`              | The public HTTPS URL of the service, without a trailing slash            |

Do not set `LOCAL_MODE`. The listen port comes from `PORT`; the port in
`BASE_URL` is not used when `PORT` is set, which is what a container host does.

If a variable is missing or malformed the container exits at once with a message
such as `DIALPAD_CLIENT_SECRET is required` or
`DIALPAD_ORIGIN must be a bare origin ...`, rather than failing on the first
request.

## Build and try the image locally

```sh
docker build -f deployment/Dockerfile -t acme-crm-demo .   # from the repository root

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
real Dialpad `idtoken` renders the iframe panel page; a browser opening it directly
shows "Open this panel from Dialpad", because the SDK needs Dialpad to frame it.

Cloud Run runs on x86-64. On an Apple-silicon Mac, `docker build` makes an arm64
image; build with `--platform linux/amd64` to test what Cloud Run will run, or
let Cloud Build do the build (below).

## Deploy

You need `gcloud` signed in (`gcloud auth login`) with permission to enable APIs
and create Cloud Run services, Artifact Registry repositories and Cloud Build
builds in the project. The project owner role does. Pass `--project` on every
command, as below, so nothing depends on your default project.

These are the commands the reference app was deployed with, on a project with
nothing enabled yet. Replace `PROJECT`, `REGION` and the names to suit. Cloud
Run's commands change over time, so check them against the current
documentation.

### 1. Enable the services and create a repository

```sh
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com secretmanager.googleapis.com

gcloud artifacts repositories create acme-crm \
  --repository-format=docker --location=REGION
```

### 2. Build and push the image

Cloud Build builds for the right architecture, from the repository root.
`gcloud builds submit --tag` only accepts a Dockerfile at the root of the
source, so this uses [`cloudbuild.yaml`](cloudbuild.yaml), which runs
`docker build -f deployment/Dockerfile`:

```sh
gcloud builds submit --config deployment/cloudbuild.yaml \
  --substitutions _IMAGE=REGION-docker.pkg.dev/PROJECT/acme-crm/acme-crm-demo:latest .
```

`client/vendor/` is tracked in git, so it is uploaded with the source; the
image's iframe panel stage needs the SDK tarball in it.

### 3. Put the secrets in Secret Manager

`DIALPAD_CLIENT_SECRET` and `APP_SECRET` are kept in Secret Manager, not in the
service's plain environment variables, which anyone who can view the service
(the console, `gcloud run services describe`) can read. Create one secret for each:

```sh
# The OAuth app's client secret, from Dialpad
printf %s "$DIALPAD_CLIENT_SECRET" | gcloud secrets create dialpad-client-secret --data-file=-
# A random secret of your own that signs `state` and the session cookie
openssl rand -hex 32 | tr -d '\n' | gcloud secrets create acme-app-secret --data-file=-
```

Then let the service's runtime service account read them. Unless you set another,
that is the default Compute Engine account, `PROJECT_NUMBER-compute@developer.gserviceaccount.com`:

```sh
RUNTIME_SA=$(gcloud projects describe PROJECT --format='value(projectNumber)')-compute@developer.gserviceaccount.com
for s in dialpad-client-secret acme-app-secret; do
  gcloud secrets add-iam-policy-binding $s --project PROJECT \
    --member serviceAccount:$RUNTIME_SA --role roles/secretmanager.secretAccessor
done
```

Cloud Run reads the secrets when an instance starts and gives them to the app as
the environment variables of the same names, so the app needs no change. To
change a value, add a version (`gcloud secrets versions add NAME --data-file=-`)
and deploy a new revision, so new instances start with it. Changing `APP_SECRET`
signs everyone out.

### 4. Deploy

```sh
gcloud run deploy acme-crm-demo \
  --image REGION-docker.pkg.dev/PROJECT/acme-crm/acme-crm-demo:latest \
  --region REGION \
  --allow-unauthenticated \
  --port 8080 \
  --max-instances 1 \
  --set-env-vars "DIALPAD_ORIGIN=https://dialpadbeta.com,BASE_URL=https://placeholder.example.com" \
  --set-secrets "DIALPAD_CLIENT_SECRET=dialpad-client-secret:latest,APP_SECRET=acme-app-secret:latest"
```

- **`--allow-unauthenticated`:** Dialpad's iframe has to reach the service
  without a Google login.
- **`--max-instances 1`:** keeps the in-memory OAuth results in one place (see
  [What to know](#what-to-know-before-relying-on-it)). There is no minimum:
  Cloud Run typically keeps an instance running long enough for a Connect to
  finish (the SDK gives up after 2 minutes), though it may stop one at any time.
- **`--set-secrets`:** the two secrets from step 3, as environment variables.
- **`BASE_URL` placeholder:** the service's URL isn't known until it exists, but
  the app refuses to start without a `BASE_URL`. Deploy with a placeholder, then
  set the real one:

```sh
URL=$(gcloud run services describe acme-crm-demo --region REGION --format='value(status.url)')
gcloud run services update acme-crm-demo --region REGION --update-env-vars BASE_URL=$URL
```

Until that update finishes, the authorize URLs the app builds point at the
placeholder.

Cloud Run's default startup probe (a TCP check on the port) is enough. The app's
`/healthz` exists mainly for the Playwright end-to-end tests, and you can ignore
it. Don't point a check at it on the public URL: Cloud Run's front end answers
that path itself (with Google's 404 page) before the request reaches the app.

If a command fails with a permission error right after you enable the APIs, wait
a minute and run it again; the first `gcloud builds submit` here did the same
and then succeeded.

### 5. Point Dialpad at it

Set the beta OAuth app's conversation sidebar URI to the service URL with a
trailing slash, for example `https://acme-crm-demo-xxxxxxxx-uc.a.run.app/`
(Dialpad sets this up for you). Dialpad appends `?idtoken=...` itself.

Then enable the app from Dialpad's admin settings. Open a contact in dialpadbeta
and the iframe panel should appear.

## Day two

### Deploy a new version

Build again and roll out a new revision. Rebuilding the same `:latest` tag is
enough: Cloud Run resolves the tag to the new image when you deploy, and the
service keeps its environment variables, scaling settings and URL. (The deploy
command was run to redeploy this app. The build command was run in its earlier
form, `--tag` with the Dockerfile at the repository root; the `--config` form
below, for the Dockerfile's new place in `deployment/`, has not been run.)

```sh
gcloud builds submit --config deployment/cloudbuild.yaml --project PROJECT \
  --substitutions _IMAGE=REGION-docker.pkg.dev/PROJECT/acme-crm/acme-crm-demo:latest .

gcloud run deploy acme-crm-demo --project PROJECT --region REGION \
  --image REGION-docker.pkg.dev/PROJECT/acme-crm/acme-crm-demo:latest
```

The new revision takes all traffic once it is ready. Open iframe panels keep working
across the rollout: their access token and connection are in the browser's
session cookie, signed with `APP_SECRET`, which the new revision accepts. Only a
Connect that was in flight loses its in-memory OAuth result and has to be
retried.

To change a setting without rebuilding, use
`gcloud run services update ... --update-env-vars` (as for `BASE_URL` above); for
a secret, see step 3.

### Look at it

```sh
gcloud run revisions list --service acme-crm-demo --project PROJECT --region REGION
gcloud run services logs read acme-crm-demo --project PROJECT --region REGION --limit 50
```

The service has two equivalent URLs: the one `gcloud run services describe`
prints in `status.url` (`https://acme-crm-demo-<hash>-uc.a.run.app`) and a
second form built from the project number
(`https://acme-crm-demo-<project-number>.<region>.run.app`). Use the same one
for `BASE_URL` and the sidebar URI so the OAuth popup and the iframe panel share an
origin.

### Roll back, or remove it (not run here)

```sh
gcloud run services update-traffic acme-crm-demo --project PROJECT --region REGION \
  --to-revisions REVISION=100

gcloud run services delete acme-crm-demo --project PROJECT --region REGION
```

Deleting the service leaves the image in Artifact Registry and the enabled APIs
in the project.

### Cost

With no minimum, the service scales to zero when idle and is billed only while it
serves requests. The first request after an idle period waits for an instance to
start. A scale-to-zero (or any restart) forgets in-memory OAuth results, so a
Connect in flight has to be retried; connected users stay connected. To keep an
instance warm anyway, add `--min-instances 1`, which is billed even with no traffic.

## What to know before relying on it

- **OAuth results are in memory.** Finished OAuth results (the demo-only handoff
  from the popup to the iframe panel) live in one instance's memory. If Cloud Run ran
  several instances, the OAuth callback could record a result on one while the
  iframe panel's polling asked another, and Connect would never finish. A restart or a
  scale-to-zero forgets results that were in flight, so that Connect has to be
  retried. Limiting the service to one instance, as above, avoids the several-instance
  case for a demo. A real
  partner has no such store: the callback saves the CRM tokens in a shared
  database, as `server/acme_dialpad_rightbar/stores.py` says. The access tokens and the
  "connected" state are not in memory: they are in the session cookie (see
  Cookies below), so they survive restarts and work on any instance.
- **The idtoken ends up in Cloud Run's request log.** The idtoken is in the page
  URL and never expires. The app doesn't log it (no access log, and a quiet
  error handler), but Cloud Run's own request log,
  `run.googleapis.com/requests`, records the full request URL including
  `?idtoken=...`. This was checked on a deployed service. Anyone who can read
  the project's logs can read those tokens. Either restrict who can read them,
  or exclude the service's request logs from the `_Default` sink (not run here;
  check the syntax against the current Cloud Logging documentation):

  ```sh
  gcloud logging sinks update _Default --project PROJECT \
    --add-exclusion='name=exclude-acme-requests,filter=logName:"run.googleapis.com%2Frequests" AND resource.labels.service_name="acme-crm-demo"'
  ```

  Entries already written stay until their retention ends.

- **The page request calls Dialpad's API.** As a demo (unnecessary for the app;
  see the README's [demo call](../README.md#the-demo-call-to-dialpads-api)),
  loading the page makes an outbound HTTPS request to `DIALPAD_ORIGIN` with the
  idtoken's api key, which Cloud Run allows by default. It waits at most 3
  seconds, so a slow or unreachable Dialpad API delays the iframe panel's first paint
  by that much and then shows "Dialpad API unavailable". The key is not logged
  or stored.
- **The OAuth is fake.** `/oauth/fake-authorize` stands in for the CRM's consent
  screen, and `/oauth/callback` only records that the user connected. A real
  partner replaces the fake page and makes the callback exchange the `code` for
  CRM tokens (see the README's "What to replace").
- **Cookies.** The session cookie is the app's persistent storage of the user's
  access token and whether they are connected. It is signed with `APP_SECRET`
  (changing the secret signs everyone out: every open iframe panel gets `401` and
  shows "Reload the panel"), valid for 30 days, and kept in the browser, so it
  survives a restart or scale-to-zero and works on any instance. The API calls
  need the bearer token and the cookie to match, so a browser that refuses the
  cookie (older Safari, or one blocking third-party cookies) can't use the
  iframe panel. It is `Secure`, `HttpOnly`, `SameSite=None` and `Partitioned`, so it
  works in a third-party iframe over HTTPS. Cloud Run terminates TLS and the app
  sets the cookie regardless of the scheme it sees internally.

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

After the files moved into `client/`, `server/` and `deployment/`, the image
was built again with `docker build -f deployment/Dockerfile .` and run: `/healthz`
answered `ok`, the page rendered, a built asset under `/assets` was served, and a
bad idtoken got `401`. The `cloudbuild.yaml` that replaces `--tag` has not been
run.

After the access token moved into the session cookie, the image was built and run
again: the page set the cookie (`Secure`, `HttpOnly`, `SameSite=None`,
`Partitioned`, 30 days), `ext-connection` answered `200` with the matching bearer
token and cookie and `401` with only one of them or a wrong token, it still
answered `200` after `docker restart`, and neither token appeared in the logs.
The Cloud Run service itself was not redeployed with this change.

On Cloud Run, from a deployment to a project that had nothing enabled (with the
layout and build command from before the move):

- Cloud Build built the image, Artifact Registry stored it, and the service came
  up with one instance on port 8080.
- Over the service's HTTPS URL: the page rendered for an idtoken signed with the
  configured client secret and returned `401` for one signed with another
  secret; its headers (the Content-Security-Policy with `frame-ancestors`,
  `no-store`, `no-referrer`) and its hashed assets were right; the fake
  authorize page, the callback and `ext-connection` completed a connection and
  set the cookie with all its attributes.
- `/healthz` on the public URL returns Google's 404, not the app's `ok`.
- The app's own logs held no idtoken; Cloud Run's request log did (see above).
- A second build and `gcloud run deploy` rolled out a new revision with the same
  environment variables and instance limits, and the new bundle was being
  served.

After the secrets moved to Secret Manager, the live service's new revision listed
`DIALPAD_CLIENT_SECRET` and `APP_SECRET` as secret references (no plain value),
took all traffic, and answered `401` for a page request without an idtoken, as
the app does. The values were copied from the old environment variables, so the
client secret is still the placeholder the demo was deployed with, not the OAuth
app's own.

Not checked: the iframe panel framed by dialpadbeta itself, which needs the OAuth app's
conversation sidebar URI to point at the service.
