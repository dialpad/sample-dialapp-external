# Deploy the app

The app runs as one container on any host that serves it over HTTPS. This page
has two parts:

- **[On any host](#on-any-host)** applies to every host: what's in the image,
  the settings it needs, and what your host must provide.
- **[Example: Google Cloud Run](#example-google-cloud-run)** shows one way to
  run it, on Google Cloud Run, which Dialpad uses to test this demo. On another
  host, skip it and follow your host's documentation.

> **A demo, not a production setup.** The OAuth round trip is fake, and finished
> OAuth results live in one process's memory. See the guide's
> [What to keep, replace, and delete](../guide/11-from-demo-to-your-app.md#what-to-keep-replace-and-delete).

## On any host

### What's in the image

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
the built iframe panel). It contains no secret or URL: you pass the environment
variables below when the container runs.

### Environment variables

See the [environment variables reference](../guide/reference.md#the-servers-environment-variables) for all
of them. A container needs these four, none of which is baked into the image:

| Variable                | Value                                                         |
| ----------------------- | ------------------------------------------------------------- |
| `DIALPAD_CLIENT_SECRET` | The OAuth app's client secret                                 |
| `APP_SECRET`            | Demo only. A random secret that signs `state` and the cookie  |
| `DIALPAD_ORIGIN`        | `https://dialpad.com`                                         |
| `BASE_URL`              | The public HTTPS URL of the service, without a trailing slash |

Don't set `LOCAL_MODE`. The listen port comes from `PORT`; the port in
`BASE_URL` is ignored when `PORT` is set, which is what a container host does.

If a variable is missing or malformed, the container exits at once with a
message such as `DIALPAD_CLIENT_SECRET is required` or
`DIALPAD_ORIGIN must be a bare origin ...`, rather than failing on the first
request.

### Build and run the image

```sh
docker build -f deployment/Dockerfile -t acme-crm-demo .   # from the repository root

docker run --rm -p 8080:8080 \
  -e DIALPAD_CLIENT_SECRET=... \
  -e APP_SECRET=... \
  -e DIALPAD_ORIGIN=https://dialpad.com \
  -e BASE_URL=http://localhost:8080 \
  acme-crm-demo

curl http://localhost:8080/healthz   # ok
```

The app uses `BASE_URL` only to build the authorize and callback URLs, so
locally it can be the address you reach the container at.
`http://localhost:8080/` with a real Dialpad `idtoken` renders the iframe panel
page; a browser opening it directly shows "Open this panel from Dialpad",
because the SDK needs Dialpad to frame it.

Most container hosts run x86-64. On an Apple-silicon Mac, `docker build` makes
an arm64 image, so add `--platform linux/amd64` to build what such a host runs.

### What your host must provide

| Your host must                                                    | Why                                                                                                                                                                                                                                                         |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Serve the container over HTTPS at a public URL                    | Dialpad frames only HTTPS pages, and the storage cookie is `Secure`. The host can end TLS in front of the container                                                                                                                                         |
| Let requests in without a sign-in                                 | Dialpad's iframe can't sign in to your host                                                                                                                                                                                                                 |
| Pass `DIALPAD_CLIENT_SECRET` and `APP_SECRET` from a secret store | Anyone who can view the service can read its plain environment variables                                                                                                                                                                                    |
| Run one instance, for this demo                                   | The demo keeps OAuth results in one process's memory. With several instances, Connect can't finish, and a restart drops a Connect in flight. Your app keeps them in a database ([chapter 11](../guide/11-from-demo-to-your-app.md#oauth-results-in-memory)) |
| Keep the idtoken out of request logs, or limit who reads them     | The page URL carries the idtoken, which never expires                                                                                                                                                                                                       |
| Allow outbound HTTPS to `DIALPAD_ORIGIN`                          | The demo calls Dialpad's API on each page load                                                                                                                                                                                                              |
| Use one URL for both `BASE_URL` and the sidebar URI               | The OAuth popup and the iframe panel must share an origin                                                                                                                                                                                                   |
| Keep `APP_SECRET` the same across deploys                         | Changing it signs everyone out                                                                                                                                                                                                                              |

### Point Dialpad at it

Your OAuth app's sidebar URI is your service's URL with a trailing slash, such
as `https://acme.example.com/`. Dialpad appends `?idtoken=...` itself. Send the
URL to Dialpad when you ask for your app
([Get your app from Dialpad](../guide/02-run-the-demo.md#get-your-app-from-dialpad)),
or ask Dialpad to update it if the URL changed.

Then, as a company admin, open
[Integrations settings](https://dialpad.com/adminsettings/integrations), and
turn on **Enable this feature** for the app. Open a contact in Dialpad, and the
iframe panel appears.

## Example: Google Cloud Run

Everything in this part is specific to Cloud Run. It meets each row of
[What your host must provide](#what-your-host-must-provide).

You need `gcloud` signed in (`gcloud auth login`) with permission to turn on
APIs and create Cloud Run services, Artifact Registry repositories, Cloud Build
builds and Secret Manager secrets in the project. The project owner role has
these. Pass `--project` on every command, as below, so nothing depends on your
default project. Replace `PROJECT`, `REGION` and the names to suit. Cloud Run's
commands change over time, so check them against the current documentation.

> **Already deployed? Go to [Deploy a new version](#deploy-a-new-version).** Steps
> 1 to 6 create the service. On a service that exists, step 4's `--set-env-vars`
> and `--set-secrets` replace all its environment variables and secrets,
> including a `DIALPAD_ORIGIN` or `BASE_URL` set for another environment. Check
> first; a URL in the output means the service exists:
>
> ```sh
> gcloud run services describe acme-crm-demo --project PROJECT --region REGION --format='value(status.url)'
> ```

### 1. Enable the services and create a repository

```sh
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com secretmanager.googleapis.com

gcloud artifacts repositories create acme-crm \
  --repository-format=docker --location=REGION
```

If a later command fails with a permission error right after you enable the APIs,
wait a minute and run it again.

### 2. Build and push the image

Cloud Build builds for the right architecture, from the repository root.
`gcloud builds submit --tag` only accepts a Dockerfile at the root of the
source, so this uses [`cloudbuild.yaml`](cloudbuild.yaml), which runs
`docker build -f deployment/Dockerfile`:

```sh
gcloud builds submit --config deployment/cloudbuild.yaml \
  --substitutions _IMAGE=REGION-docker.pkg.dev/PROJECT/acme-crm/acme-crm-demo:latest .
```

`client/vendor/` is tracked in git, so `gcloud` uploads it with the source; the
image's iframe panel stage needs the SDK tarball in it.

### 3. Put the secrets in Secret Manager

Keep `DIALPAD_CLIENT_SECRET` and `APP_SECRET` in Secret Manager, not in the
service's plain environment variables, which anyone who can view the service
(the console, `gcloud run services describe`) can read. Create one secret for each:

```sh
# The OAuth app's client secret, from Dialpad
printf %s "$DIALPAD_CLIENT_SECRET" | gcloud secrets create dialpad-client-secret --data-file=-
# A random secret of your own that signs `state` and the storage cookie
openssl rand -hex 32 | tr -d '\n' | gcloud secrets create acme-app-secret --data-file=-
```

Then let the service's runtime service account read them. Unless you set another,
that's the default Compute Engine account, `PROJECT_NUMBER-compute@developer.gserviceaccount.com`:

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

### 4. Create the service

```sh
gcloud run deploy acme-crm-demo \
  --image REGION-docker.pkg.dev/PROJECT/acme-crm/acme-crm-demo:latest \
  --region REGION \
  --allow-unauthenticated \
  --port 8080 \
  --max-instances 1 \
  --set-env-vars "DIALPAD_ORIGIN=https://dialpad.com,BASE_URL=https://placeholder.example.com" \
  --set-secrets "DIALPAD_CLIENT_SECRET=dialpad-client-secret:latest,APP_SECRET=acme-app-secret:latest"
```

- **`--allow-unauthenticated`:** Dialpad's iframe has to reach the service
  without a Google sign-in.
- **`--max-instances 1`:** keeps the in-memory OAuth results in one place (see
  [What your host must provide](#what-your-host-must-provide)). There is no minimum:
  Cloud Run typically keeps an instance running long enough for a Connect to
  finish (the SDK gives up after 2 minutes), though it may stop one at any time.
- **`--set-secrets`:** the two secrets from step 3, as environment variables.
- **`BASE_URL` placeholder:** the service's URL doesn't exist until the service
  does, but the app refuses to start without a `BASE_URL`. Deploy with a
  placeholder, then set the real one:

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

### 5. Keep the idtoken out of the logs

Cloud Run's request log, `run.googleapis.com/requests`, records the full request
URL, including `?idtoken=...`. Either restrict who can read the project's logs,
or exclude the service's request logs from the `_Default` sink (check the syntax
against the current Cloud Logging documentation):

```sh
gcloud logging sinks update _Default --project PROJECT \
  --add-exclusion='name=exclude-acme-requests,filter=logName:"run.googleapis.com%2Frequests" AND resource.labels.service_name="acme-crm-demo"'
```

Entries already written stay until their retention ends.

### 6. Point Dialpad at it

Follow [Point Dialpad at it](#point-dialpad-at-it), with the service's URL, such
as `https://acme-crm-demo-xxxxxxxx-uc.a.run.app/`.

The service has two equivalent URLs: the one `gcloud run services describe`
prints in `status.url` (`https://acme-crm-demo-<hash>-uc.a.run.app`) and a
second form built from the project number
(`https://acme-crm-demo-<project-number>.<region>.run.app`). Use the
`status.url` one for both `BASE_URL` and the sidebar URI, so the OAuth popup and
the iframe panel share an origin.

### Day two

#### Deploy a new version

Build again and roll out a new revision. Rebuilding the same `:latest` tag is
enough: Cloud Run resolves the tag to the new image when you deploy, and the
service keeps its environment variables, secret references, scaling settings and
URL.

```sh
gcloud builds submit --config deployment/cloudbuild.yaml --project PROJECT \
  --substitutions _IMAGE=REGION-docker.pkg.dev/PROJECT/acme-crm/acme-crm-demo:latest .

gcloud run deploy acme-crm-demo --project PROJECT --region REGION \
  --image REGION-docker.pkg.dev/PROJECT/acme-crm/acme-crm-demo:latest
```

Pass only `--image`. `--set-env-vars` and `--set-secrets` replace all the
service's settings; to change one, see below.

The new revision takes all traffic once it's ready. Open iframe panels keep
working across the rollout: their access token and connection are in the
browser's storage cookie, signed with `APP_SECRET`, which the new revision
accepts. Only a Connect that was in flight loses its in-memory OAuth result and
has to be retried.

To change a setting without rebuilding, use
`gcloud run services update ... --update-env-vars` (as for `BASE_URL` above); for
a secret, see step 3.

#### Look at it

```sh
gcloud run revisions list --service acme-crm-demo --project PROJECT --region REGION
gcloud run services logs read acme-crm-demo --project PROJECT --region REGION --limit 50
```

#### Roll back

Send all traffic back to an earlier revision, from the list in
[Look at it](#look-at-it):

```sh
gcloud run services update-traffic acme-crm-demo --project PROJECT --region REGION \
  --to-revisions REVISION=100
```
