# Acme CRM: a partner rightbar reference app

A small, runnable example of a Dialpad rightbar app. Dialpad loads the page, the
page knows who the user is, the user connects a partner system through an OAuth
popup, and the panel shows data Dialpad passes in.

The partner system here is a fictional "Acme CRM" with no data. The panel proves
data flow by showing the Dialpad user, the OAuth scopes and the open Dialpad
contact with every field "Acme'd" (text gets an `Acme ` prefix).

It uses only Dialpad's two libraries and public packages:

- `dialpad-dialapp-toolkit` (Python): decodes the idtoken, renders the page and
  the close-popup page, and defines the contract models.
- `@dialpad/dialapp-external-sdk` (TypeScript): the headless SDK that speaks
  Dialpad's host protocol and keeps the panel's state.

The backend is bare Sanic on Python 3.14; the frontend is Vite, Vue 3,
TypeScript and Dialtone 10. Copy this repository and replace the parts listed
under [What to replace](#what-to-replace).

## Install

You need Node 24, Corepack (for pnpm 12) and Python 3.14.

```sh
nvm use                                  # reads .nvmrc (24)
corepack enable
pnpm install

python3.14 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

The two libraries are installed from files in `vendor/`, exactly as you install
what Dialpad sends you: `package.json` points at
`vendor/dialpad-dialapp-external-sdk-<version>.tgz` and `requirements.txt` at
`vendor/dialpad_dialapp_toolkit-<version>-py3-none-any.whl`. Nothing here needs
Dialpad's private registry.

### Upgrading the libraries

Put the new `dialpad-dialapp-external-sdk-<version>.tgz` and
`dialpad_dialapp_toolkit-<version>-py3-none-any.whl` in one folder and run:

```sh
pnpm run vendor <folder>
```

It replaces everything in `vendor/` with those two files, updates the two
references (the `file:vendor/...` dependency in `package.json` and the
`./vendor/...` line in `requirements.txt`), then installs them with
`pnpm install --no-frozen-lockfile` and
`pip install --force-reinstall --no-deps` into `.venv`, which must already
exist. The install is not frozen because a new build changes the tarball's
checksum even at the same version. The folder must contain exactly one of each
file; otherwise the command stops with a message before changing anything.
Running it twice with the same files is safe.

## Run locally, without Dialpad (local mode)

Local mode runs everything on `http://localhost`. Browsers treat `localhost` as
a secure context, so the `Secure`, `__Host-` connection cookie works, and the
dev page and the app are the same site, so the cookie isn't even third-party.
This works in Chrome and Firefox. Safari may not treat `localhost` as secure for
cookies; for Safari use a trusted local certificate such as `mkcert`.

In two terminals:

```sh
LOCAL_MODE=1 .venv/bin/python -m backend   # backend on http://localhost:8000
pnpm dev                                    # Vite on http://localhost:5173
```

Open <http://localhost:5173/dev/>. The dev page stands in for Dialpad: it asks
the backend for a page URL carrying a mock idtoken (made by the toolkit with its
test secret), frames the app, answers `init`, and offers buttons to send a
contact, start and end a call, and switch light and dark.

Click **Connect**. The fake authorize URL opens in a popup and redirects
straight to the fake callback, with no login screen. Like the desktop app, the
dev page never replies to Connect, so the SDK's polling completes it (first
check after 7 seconds, then every 5). The panel then shows you, and the contact,
Acme'd. **Disconnect** asks for inline confirmation.

`LOCAL_MODE=1` is configuration only; a request cannot switch it on. It changes
the page's `Content-Security-Policy` in three places and nowhere else:
`frame-ancestors` is the dev page's origin, `script-src` adds the Vite dev
server's origin, and `connect-src` adds its websocket origin.

## Run framed in dialpadbeta (flow 7)

This is documented, not exercised in this repository: it needs a beta OAuth app
that Dialpad sets up for you.

1. Build the frontend (`pnpm build`) and run the backend without `LOCAL_MODE`,
   with the four required variables from [Configuration](#configuration):

   ```sh
   DIALPAD_CLIENT_SECRET=... DIALPAD_ORIGIN=https://dialpadbeta.com APP_SECRET=... \
     BASE_URL=https://your-public-url .venv/bin/python -m backend
   ```

2. Expose the backend at that public HTTPS URL (how is up to you).
3. Point the beta OAuth app's conversation sidebar URI at it, following
   Dialpad's runbook.
4. Open any contact in dialpadbeta: the panel appears, and connect, reconnect,
   and disconnect work against the real host.

Current Chrome, Edge, Firefox and Safari 26.2 or later are supported (the
connection cookie is `Partitioned`). Older Safari rejects partitioned cookies,
so there the panel asks the user to connect again on each new iframe.

## Configuration

The backend reads these environment variables; the frontend reads none. Nothing
loads a `.env` file, so export them in your shell or your host's settings.

| Variable                | Required                | Purpose                                                                                                                                                                                                                                            |
| ----------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DIALPAD_CLIENT_SECRET` | yes, outside local mode | The OAuth app's client secret; decodes the idtoken. At least 48 characters (Dialpad's are 50). Local mode defaults to the toolkit's test secret                                                                                                    |
| `DIALPAD_ORIGIN`        | yes, outside local mode | `https://dialpadbeta.com` for beta or `https://dialpad.com` for production; the page's `frame-ancestors`. Must be a bare origin (scheme, host, optional port; no trailing slash or path), checked at startup. Local mode defaults to `VITE_ORIGIN` |
| `APP_SECRET`            | yes, outside local mode | A random secret that signs the OAuth `state` and the connection cookie. Local mode defaults to a fixed development value                                                                                                                           |
| `BASE_URL`              | yes, outside local mode | The public HTTPS URL of the backend, without a trailing slash; used to build the authorize and callback URLs. Local mode defaults to `http://localhost:8000`                                                                                       |
| `LOCAL_MODE`            | no                      | `1` turns on local mode: the defaults above, the dev page's route, and the Vite dev server's origins in the CSP                                                                                                                                    |
| `VITE_ORIGIN`           | no, local mode only     | The Vite dev server's origin. Default `http://localhost:5173`                                                                                                                                                                                      |
| `DIST_DIR`              | no                      | Where `pnpm build` wrote the frontend. Default `dist`                                                                                                                                                                                              |
| `PORT`                  | no                      | The port to listen on, used only when `BASE_URL` has none. Default `8000`                                                                                                                                                                          |

Keep `DIALPAD_CLIENT_SECRET` and `APP_SECRET` out of source control.

## How it works

1. **Page.** Dialpad loads `GET /?idtoken=…`. The backend decodes the token with
   the toolkit, looks up or issues this user's access token, and renders the
   page with the toolkit: the access token and an `external_connection` (whether
   the user is connected, one authorize URL for the `acme-crm` client, and its
   scopes). The page carries no user data, so nothing from the idtoken's profile
   reaches the browser.
2. **User.** The SDK asks Dialpad for the user (`get/user`) once it starts, and
   the panel shows it from `state.user`.
3. **API.** Every call afterwards carries
   `Authorization: Bearer <access token>`. The idtoken is used only on the page
   request.
4. **Connect.** The SDK asks Dialpad to open the authorize URL. The callback
   verifies a signed `state`, records "connected" for that user in server memory
   for 5 minutes, and returns the toolkit's close-popup page. The next
   `/dialpad/ext-connection` check (the reply-triggered one, a poll, or the next
   iframe's bootstrap check) consumes it and sets the connection cookie.
5. **Later contacts and sessions.** The cookie is signed and bound to the user
   and company, so the first paint is already the connected view.
6. **Disconnect.** `POST /dialpad/ext-disconnect` clears the cookie and answers
   `204`; the SDK then calls `/dialpad/ext-connection` once for a fresh
   authorize URL.

| Endpoint                       | Behaviour                                                                                                |
| ------------------------------ | -------------------------------------------------------------------------------------------------------- |
| `GET /`                        | The page. `401` HTML if the idtoken doesn't decode                                                       |
| `GET /dialpad/ext-connection`  | Bearer token. Consumes a stored OAuth result, else answers from the cookie. Always a fresh authorize URL |
| `POST /dialpad/ext-disconnect` | Bearer token. Clears the cookie, answers `204` with no body                                              |
| `GET /oauth/fake-authorize`    | Demo only. Redirects to the callback with `state` and a fixed `code`                                     |
| `GET /oauth/callback`          | Demo only. Verifies `state`, records the result, close-popup page                                        |

## What to replace

| Here                                            | With                                                                                         |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `/oauth/fake-authorize`, `/oauth/callback`      | Your real OAuth authorize URL and callback. Keep the close-popup page                        |
| `backend/stores.py` (in-memory)                 | A durable store for access tokens and OAuth results (see below)                              |
| The cookie (`backend/signing.py`, `app.py`)     | Wherever you keep your CRM tokens. The cookie is this app's choice, not part of the contract |
| `src/acme.ts`, `src/components/AcmeContact.vue` | Your CRM's data, matched to the Dialpad contact                                              |
| `src/components/ConnectGate.vue`                | Copy it and change the copy; it renders the SDK's `connection` state                         |
| `ACCOUNT_NAME` in `backend/app.py`              | Your CRM's account name                                                                      |

Access tokens and OAuth results live in one process's memory. That is a
reference-app shortcut, not something to copy: a real partner stores tokens
durably so a restart or a second instance doesn't log users out. Here, open
panels get `401` after a restart and show "Reload the panel".

## Checks

```sh
pnpm lint:ci && pnpm format:ci && pnpm types:check && pnpm test:run     # frontend
.venv/bin/ruff check . && .venv/bin/yapf --diff -r backend tests \
  && .venv/bin/ty check && .venv/bin/pytest                             # backend
pnpm test:e2e                                                          # Playwright smoke test
```

The Playwright tests start the backend in local mode and Vite, then drive the
dev page with Playwright's clock. `e2e/smoke.spec.ts` walks Connect, a reload
and Disconnect. The three tests in `e2e/sdk/` exist to check the SDK in a real
browser from the libraries' CI (opened outside Dialpad, Connect that times out,
Disconnect from the host's panel menu); they are not part of the template, so
delete that folder when you copy the app. Install the browser once with
`pnpm exec playwright install chromium`.
