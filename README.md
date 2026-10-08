# Acme CRM: a partner rightbar reference app

A small, runnable example of a Dialpad rightbar app. Dialpad loads the page, the
page knows who the user is, the user connects a partner system through an OAuth
popup, and the panel shows data Dialpad passes in.

The partner system here is a fictional "Acme CRM" with no data. The panel proves
data flow by showing the Dialpad user, the active call, the OAuth scopes and the
open Dialpad contact (plus the call's own contact when it is a different person)
with every field "Acme'd" (text gets an `Acme ` prefix).

It uses one Dialpad library, plus public packages:

- `@dialpad/dialapp-external-sdk` (TypeScript), from
  [`dialapp-external`](https://github.com/dialpad/dialapp-external): the
  headless SDK that speaks Dialpad's host protocol and keeps the panel's state.

The server carries its own small pieces of the contract, which you keep and
adapt: `server/acme_crm/idtoken.py` decodes the idtoken (and mints mock ones for
local mode), `server/acme_crm/pages.py` renders the panel, close-popup and error
pages with their security headers, and `server/acme_crm/contract.py` has the
models the SDK reads. They are built on `pydantic` and `joserfc`.

The repository has two parts, each with its own tools and checks:

| Folder        | What it is                                                                                          |
| ------------- | --------------------------------------------------------------------------------------------------- |
| `client/`     | The panel, which runs in Dialpad's iframe: Vite, Vue 3, TypeScript and Dialtone 10. `pnpm` project  |
| `server/`     | The Python server (`acme_crm/`): bare Sanic on Python 3.14, with its tests. `tox` and `pip` project |
| `deployment/` | The Dockerfile and how to run the app as a container on Cloud Run                                   |

Copy this repository and replace the parts listed under
[What to replace](#what-to-replace). The security side (the idtoken and its api
key, authenticating every request, CSP and nonces, cookies) is collected in
[Security: what the demo shows](#security-what-the-demo-shows).

## Install

You need Node 24, Corepack (for pnpm 12) and Python 3.14 (plus
[uv](https://docs.astral.sh/uv/) if you want to run the server's checks with
tox).

```sh
nvm use                                  # reads .nvmrc (24)
corepack enable
cd client && pnpm install

cd ../server
python3.14 -m venv .venv
.venv/bin/pip install -r requirements.txt --group dev
```

The SDK is installed from a file in `client/vendor/`, exactly as you install
what Dialpad sends you: `client/package.json` points at
`vendor/dialpad-dialapp-external-sdk-<version>.tgz`. Nothing here needs
Dialpad's private registry. The server installs only public packages:
`requirements.txt` has what it runs on, and the `dev` dependency group in
`server/pyproject.toml` adds the test, lint, type-check and style tools.

### Upgrading the SDK

Put the new `dialpad-dialapp-external-sdk-<version>.tgz` in a folder and run,
from `client/`:

```sh
pnpm run vendor <folder>
```

It replaces everything in `client/vendor/` with that file, updates the
`file:vendor/...` dependency in `client/package.json`, then installs with
`pnpm install --no-frozen-lockfile`. The install is not frozen because a new
build changes the tarball's checksum even at the same version. The folder must
contain exactly one SDK tarball (other files in it are ignored); otherwise the
command stops with a message before changing anything. Running it twice with the
same file is safe. The server has nothing to update: it uses no Dialpad library.

## Run locally, without Dialpad (local mode)

Local mode runs everything on `http://localhost`. Browsers treat `localhost` as
a secure context, so the `Secure`, `__Host-` connection cookie works, and the
dev host and the app are the same site, so the cookie isn't even third-party.
This works in Chrome and Firefox. Safari may not treat `localhost` as secure for
cookies; for Safari use a trusted local certificate such as `mkcert`.

In two terminals:

```sh
cd server && LOCAL_MODE=1 .venv/bin/python -m acme_crm   # server on http://localhost:8000
cd client && pnpm dev                                    # Vite on http://localhost:5173
```

Open <http://localhost:5173/dev-host/>. The dev host (`client/dev-host/`) stands
in for Dialpad: it asks the server for a page URL carrying a mock idtoken (made
by `server/acme_crm/idtoken.py` with its test secret), frames the app, answers
`init`, opens the first of three contacts, and offers buttons to change contact
(cycling through the three), change the call state (ringing, connected, ended,
and a new call ringing), and switch light and dark.

Click **Connect**. The fake authorize URL opens in a popup showing a page that
says it is a fake OAuth page, with an **Authorize** button. The popup stays
open, and the panel shows "Waiting for you to finish connecting", until you
press Authorize; the popup then goes to the callback and closes itself. Like the
desktop app, the dev host never replies to Connect, so the SDK's polling
completes it (first check after 7 seconds, then every 5). The panel then shows
you, and the contact, Acme'd. **Disconnect** asks for inline confirmation.

`LOCAL_MODE=1` is configuration only; a request cannot switch it on. It changes
the page's `Content-Security-Policy` in three places and nowhere else:
`frame-ancestors` is the dev host's origin, `script-src` adds the Vite dev
server's origin, and `connect-src` adds its websocket origin.

## Run framed in dialpadbeta (flow 7)

This is documented, not exercised in this repository: it needs a beta OAuth app
that Dialpad sets up for you.

1. Build the panel (`pnpm build` in `client/`) and run the server from `server/`
   without `LOCAL_MODE`, with the four required variables from
   [Configuration](#configuration):

   ```sh
   cd server && DIALPAD_CLIENT_SECRET=... DIALPAD_ORIGIN=https://dialpadbeta.com \
     APP_SECRET=... BASE_URL=https://your-public-url .venv/bin/python -m acme_crm
   ```

2. Expose the server at that public HTTPS URL (how is up to you).
3. Point the beta OAuth app's conversation sidebar URI at it, following
   Dialpad's runbook.
4. Open any contact in dialpadbeta: the panel appears, and connect, reconnect,
   and disconnect work against the real host.

Current Chrome, Edge, Firefox and Safari 26.2 or later are supported. The
session cookie is `Partitioned` and holds the panel's access token, so a browser
that rejects it (older Safari rejects partitioned cookies, and some browsers block
third-party cookies) can't use the panel at all: every API call gets `401` and
the panel asks the user to reload.

## Configuration

The server reads these environment variables; the panel reads none. Nothing
loads a `.env` file, so export them in your shell or your host's settings.

| Variable                | Required                | Purpose                                                                                                                                                                                                                                            |
| ----------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DIALPAD_CLIENT_SECRET` | yes, outside local mode | The OAuth app's client secret; decodes the idtoken. At least 48 characters (Dialpad's are 50). Local mode defaults to this app's own test secret (`TEST_CLIENT_SECRET` in `server/acme_crm/idtoken.py`)                                            |
| `DIALPAD_ORIGIN`        | yes, outside local mode | `https://dialpadbeta.com` for beta or `https://dialpad.com` for production; the page's `frame-ancestors`. Must be a bare origin (scheme, host, optional port; no trailing slash or path), checked at startup. Local mode defaults to `VITE_ORIGIN` |
| `APP_SECRET`            | yes, outside local mode | A random secret that signs the OAuth `state` and the connection cookie. Local mode defaults to a fixed development value                                                                                                                           |
| `BASE_URL`              | yes, outside local mode | The public HTTPS URL of the server, without a trailing slash; used to build the authorize and callback URLs. Local mode defaults to `http://localhost:8000`                                                                                        |
| `HOST`                  | no                      | The address to listen on. Default `127.0.0.1` (this machine only); a container sets `0.0.0.0`. See [deployment/](deployment/README.md)                                                                                                             |
| `LOCAL_MODE`            | no                      | `1` turns on local mode: the defaults above, the dev host's route, and the Vite dev server's origins in the CSP                                                                                                                                    |
| `VITE_ORIGIN`           | no, local mode only     | The Vite dev server's origin. Default `http://localhost:5173`                                                                                                                                                                                      |
| `DIST_DIR`              | no                      | Where `pnpm build` in `client/` wrote the panel. Default `../client/dist` (relative to `server/`); the container sets `dist`                                                                                                                       |
| `PORT`                  | no                      | The port to listen on. If unset, the port in `BASE_URL`, else `8000`. A container host sets it                                                                                                                                                     |

Keep `DIALPAD_CLIENT_SECRET` and `APP_SECRET` out of source control.

To run it as a container, for example on Cloud Run, see
[deployment/](deployment/README.md).

## How it works

1. **Page.** Dialpad loads `GET /?idtoken=…`. The server decodes the token with
   `server/acme_crm/idtoken.py`, then starts or continues this browser's
   session: a valid session cookie for the same user keeps its access token and
   connection state, anything else gets a new random token, not connected. It
   renders the page with `server/acme_crm/pages.py`, embedding the access token
   and an `external_connection` (whether the user is connected, one authorize URL
   for the `acme-crm` client, and its scopes), and sets the session cookie. The
   page carries no user data, so
   nothing from the idtoken's profile reaches the browser, and the idtoken's
   `api_key` never does either. The one extra thing it embeds is the result of a
   demo call to Dialpad's API (see [below](#the-demo-call-to-dialpads-api)).
2. **User.** The SDK asks Dialpad for the user (`get/user`) once it starts, and
   the panel shows it from `state.user`.
3. **API.** Every call afterwards carries
   `Authorization: Bearer <access token>` and, as the browser adds it, the
   session cookie. The server accepts the call only when the two tokens match
   (compared in constant time). The cookie is `SameSite=None`, so a cross-site
   request would carry it too, but only code that holds the page data knows the
   token to put in the header, which is what keeps another site from driving
   `ext-connection` and `ext-disconnect`. The idtoken is used only on the page
   request (for the user's identity and the demo call below), and is not stored.
4. **Connect.** The SDK asks Dialpad to open the authorize URL, which shows the
   fake authorize page. When the user presses Authorize, the callback verifies a
   signed `state`, records "connected" for that user in server memory for 5
   minutes, and returns the close-popup page from `server/acme_crm/pages.py`. The next
   `/dialpad/ext-connection` check (the reply-triggered one, a poll, or the next
   iframe's bootstrap check) consumes it and rewrites the session cookie with the
   connection on.
5. **Later contacts and sessions.** The session cookie is this demo's persistent
   storage: it holds the access token and the connection, and the server keeps no
   database. The handlers reach it only through `CookieBackedDatabaseStorage`
   (`server/acme_crm/database.py`), whose getters `get_access_token` and
   `is_external_connected` stand in for reading a per-user database row. The
   cookie is signed with `APP_SECRET`, bound to the user and company, and
   lasts 30 days (each page load refreshes it), so the first paint is already
   the connected view, even after a server restart.
6. **Disconnect.** `POST /dialpad/ext-disconnect` turns the connection off in
   the cookie (it keeps the token, so the SDK's next call still authenticates)
   and answers `204`; the SDK then calls `/dialpad/ext-connection` once for a
   fresh authorize URL.

| Endpoint                       | Behaviour                                                                                                             |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| `GET /`                        | The page. `401` HTML if the idtoken doesn't decode                                                                    |
| `GET /dialpad/ext-connection`  | Bearer token matching the cookie's. Consumes a stored OAuth result, else answers from the cookie. Fresh authorize URL |
| `POST /dialpad/ext-disconnect` | Bearer token matching the cookie's. Turns the connection off in the cookie, answers `204` with no body                |
| `GET /oauth/fake-authorize`    | Demo only. A page labelled fake, with an Authorize button that goes to the callback with `state` and a fixed `code`   |
| `GET /oauth/callback`          | Demo only. Verifies `state`, records the result, close-popup page                                                     |

### The demo call to Dialpad's API

**Unnecessary for the app, and for demo purposes only.** While it renders the
page, the server uses the idtoken's `api_key` to call Dialpad's public API, to
show how the key is used: `GET {DIALPAD_ORIGIN}/api/v2/users/me` with
`Authorization: Bearer <api_key>`, made by Dialpad's own Python client
([`python-dialpad`](https://pypi.org/project/python-dialpad/)), in
`server/acme_crm/dialpad_api.py`. The panel shows the user's name, email, id and state
in a "From Dialpad's API" card.

- The call has a 3 second timeout and no retry. If Dialpad's API refuses the
  key, fails or is slow, the page renders anyway and the card says "Dialpad API
  unavailable".
- Local mode makes no call (the mock idtoken's key isn't real), and the card
  says so.
- The key is used for this one call and dropped. It is never put in the page,
  logged or returned, and the idtoken is not stored.
- Doc 11 of the partner rightbar PRD lists calling the public API with the key
  as out of scope; this demo does it anyway, to show the key in use.

A real application would not work this way. The key never expires, so it
**persists the api key in long-term storage** (as it does its CRM tokens) the
first time it sees it, and **uses it to call Dialpad as and when needed**, from
a background job or a webhook handler as much as from a page load.

### Why connection results are kept in memory (demo only)

The Connect flow in short: the panel's page says "not connected" with an
authorize URL; Connect makes Dialpad open it in a popup while the panel polls
`/dialpad/ext-connection`; the user approves at the CRM, which sends the popup
to `/oauth/callback`; the callback verifies the signed `state` and closes the
popup; the panel's next poll learns it is connected and gets its session cookie
rewritten with the connection on.

The catch is that the callback and the panel are different windows. The
callback runs in the popup, and the session cookie belongs to the panel's iframe
(it is `Partitioned`), so the callback cannot set it. The only thing both sides know
is which Dialpad user this is, so the callback leaves a short-lived note in
server memory ("this user finished connecting", kept for 5 minutes and
collected once), and the panel's next check picks it up. That note is
`OAuthResults` in `server/acme_crm/stores.py`, whose docstring tells the whole
flow.

**This exists only because the demo has no real CRM.** A real partner's
callback exchanges the `code` for CRM tokens and stores them durably, keyed by
the Dialpad user, and `ext-connection` answers "connected" when those tokens
exist, from the database, on any instance and after any restart. Then there is
no handoff and no expiry, and both `OAuthResults` and the cookie can go.

Without a database, this demo keeps what has to last, the user's access token
and "this user is connected to external CRM", in the browser: the signed, 30-day session cookie
is its persistent storage. It survives a server restart or scale-to-zero, and it
is signed so it can't be forged. Changing `APP_SECRET` signs everyone out: every
open panel gets `401` and shows "Reload the panel". The cookie is not encrypted
(it is `HttpOnly`, so page scripts can't read it), it is per browser (Disconnect
changes it only in the browser that asked), a browser that refuses it can't use
the panel, and the server can't revoke one early. A real partner's stored tokens,
looked up by Dialpad user, have none of those limits, and a real partner would
keep a durable session or issue expiring tokens instead of this cookie.

## Security: what the demo shows

A rightbar panel is a web page that Dialpad frames, opened with a long-lived
credential in its URL, that then talks to your server. This section lists what
the app does about each risk, where it lives, and which tests cover it. The last
subsection says what it deliberately does not do.

**Which secret is which.** Five different secrets appear below, and they are not
interchangeable:

| Secret                                                | Who issues it                               | What it is used for                                                                             |
| ----------------------------------------------------- | ------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| **OAuth app client secret** (`DIALPAD_CLIENT_SECRET`) | Dialpad, when it sets up your OAuth app     | Decrypting and verifying the **idtoken** on the page request. Nothing else in this app uses it. |
| **`api_key`** (inside the idtoken)                    | Dialpad, per user and app                   | `Authorization: Bearer` on your server's calls to Dialpad's public API                          |
| **App secret** (`APP_SECRET`)                         | You (a random string)                       | Signing this app's own values: the OAuth `state` and the session cookie                         |
| **Access token** (in the page data and cookie)        | Your server, per browser session            | `Authorization: Bearer` on the panel's calls to your server                                     |
| **Webhook signing secret**                            | You, when you create a webhook with Dialpad | Verifying the JWT on events Dialpad sends to you (not implemented in this demo)                 |

### 1. The idtoken and its api key

When Dialpad loads the panel it appends `?idtoken=<token>` to your conversation
sidebar URI. The token is encrypted (a JWE using `dir` and `A192CBC-HS384`,
keyed with the first 48 characters of your **OAuth app's client secret**, the
`DIALPAD_CLIENT_SECRET`) and wraps a
JWT signed with `HS256` and the full client secret. Its claims are the Dialpad
`user_id`, `company_id` and `office_id`, the user's `name`, `email`,
`phone_number` and `image_url`, an internal `csr` claim, and the `api_key`.

**Where to use it: on your server, on that one page request, and nowhere else.**
`decode_idtoken` (`server/acme_crm/idtoken.py`) accepts only those two
algorithms, treats a client secret shorter than 48 characters as a configuration
error, and raises one error type whose message never contains the token or the
secret. A page that fails to decode gets a `401` page and no page data. The
claims tell you who opened the panel; they are never rendered into the page, and
`csr` is dropped while decoding.

**The `api_key` is a credential for Dialpad's public API**, scoped to that user
and this app. It is server-side only: `IdTokenClaims` holds it as a `SecretStr`,
`PageData` has no field for it, and tests check it appears in no page, response,
header or log.

**Why a real app persists the api key (this demo does not).** The idtoken arrives
only while a user has the panel open, but your server needs to call Dialpad at
other times: from a background job, when a webhook arrives, or after the panel
is closed. The api key does not expire, so the first time you see it for a
Dialpad user, store it in long-term storage keyed by company and user id
(protected like your CRM tokens: encrypted at rest, never logged), and replace
it whenever a newer idtoken carries a different one. This demo stores nothing: it
uses the key once, on the page request, for the demo call described in
[The demo call to Dialpad's API](#the-demo-call-to-dialpads-api), and drops it.

The idtoken has no expiry that this app checks, and it travels in a URL, so
treat that URL as a secret: the page is served with `Referrer-Policy:
no-referrer` and `Cache-Control: no-store`, the access log is off, and the
idtoken is never stored (see [Secrets and logs](#6-secrets-and-logs)).

### 2. Authenticating requests to your server

There are two kinds, and they use different credentials.

- **The page request** is authenticated by the idtoken (above). There is no
  session yet; decoding the token with your client secret is the authentication.
- **The panel's API calls** (`ext-connection` and `ext-disconnect`) come from
  the iframe, which has no idtoken. The page response therefore starts a
  session: it embeds a random **access token** in the page data and sets a signed
  **session cookie** holding the same token. Each call must send
  `Authorization: Bearer <access token>` (the SDK's `authHeaders()`, which
  `client/src/api.ts` adds to every request) and, as the browser adds it, the
  cookie:

  ```http
  GET /dialpad/ext-connection
  Authorization: Bearer <the access token from the page data>
  Cookie: __Host-acme_session=<signed session>
  ```

  The server answers only when the two tokens match (compared in constant
  time) and the cookie's signature and age are valid. Otherwise it answers
  `401`, and the panel asks the user to reload.

**Why both the header and the cookie.** The cookie has to be `SameSite=None`,
because the panel runs in a third-party iframe, so browsers also attach it to
requests made by other sites. The header can only be added by code that holds
the page data, that is, the panel's own scripts, so a request from another site
cannot forge it. Requiring the two to match is the "double submit" defence
against cross-site request forgery.

The contract only needs _some_ token the panel can send; a signed JWT or a
server-side session table work as well as this cookie.

### 3. Authenticating requests to Dialpad

Calls from your server to Dialpad's public API carry the api key as a bearer
token, against the Dialpad origin you are configured for (`DIALPAD_ORIGIN`, the
beta or production host):

```http
GET https://dialpadbeta.com/api/v2/users/me
Authorization: Bearer <api_key>
```

`server/acme_crm/dialpad_api.py` does this with Dialpad's own Python client,
`AsyncDialpadClient(token=api_key, base_url=origin)`, which adds that header to
every request. Use a short timeout and no retries for anything on the page
request path, and treat a `401` as "the key was refused". The key goes only in
that header, from your server. **The browser never has it and never calls
Dialpad's API directly**; what the panel needs from Dialpad (the user, the open
contact, the call) arrives through the SDK's host protocol, which needs no key
because Dialpad itself framed the page.

**Incoming event subscriptions** (call, SMS, contact, agent-status events and
change logs) go the other way: Dialpad sends a request to a webhook URL on your
server, so you have to authenticate Dialpad. When you create the webhook you
provide a **signing secret**, and Dialpad then sends every event as a JWT signed
(`HS256`) with it. If you provide no secret, events arrive as unsigned JSON that
anyone could forge, so always provide one. Verify the JWT's signature with that
secret and only then trust the payload.

That secret is a string _you_ choose and hand to Dialpad when creating the
webhook: Dialpad does not issue it, it is not the api key, and Dialpad's docs do
not say it has to be your OAuth app's client secret. Dialpad recommends a unique
one per subscription, so a leak has a small blast radius (you could, for
example, derive each from a secret of your own). See Dialpad's
[Event Subscriptions](https://developers.dialpad.com/docs/event-subscriptions)
guide (its security paragraph) and the
[Webhook Create](https://developers.dialpad.com/reference/webhookscreate)
reference, which describe the signed events and the secret. This demo has no
webhook receiver, so none of this is exercised here.

### 4. Framing, CSP and nonces

Every page the server renders carries a `Content-Security-Policy`, plus
`Referrer-Policy: no-referrer`, `Cache-Control: no-store` and
`X-Content-Type-Options: nosniff`.

| Page                              | `Content-Security-Policy`                                                                                           |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| The panel, `GET /`                | `frame-ancestors <DIALPAD_ORIGIN>; script-src 'self' 'nonce-…' <asset origins>; object-src 'none'; base-uri 'none'` |
| Close-popup page (OAuth callback) | `default-src 'none'; script-src 'nonce-…'; style-src 'nonce-…'; frame-ancestors 'none'; base-uri 'none'`            |
| Error page (`401`)                | `default-src 'none'; style-src 'nonce-…'; frame-ancestors <DIALPAD_ORIGIN>; base-uri 'none'`                        |
| Fake authorize page (demo OAuth)  | `default-src 'none'; style-src 'nonce-…'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`              |

- **`frame-ancestors`** lets only Dialpad embed the panel, which prevents other
  sites from framing it (clickjacking). The popup pages cannot be framed at all.
- **`script-src 'self' 'nonce-…'`, with no `'unsafe-inline'` or
  `'unsafe-eval'`**, means only the app's own script files run. An inline script
  injected into the page, which an XSS bug would produce, does not.
- **The nonce** is a fresh random value for each response
  (`secrets.token_urlsafe`), written both into the CSP header and onto the
  inline elements that are allowed. The close-popup page's one inline script and
  style run only because they carry it; reusing a nonce across responses would
  defeat the policy. The panel page has no inline script of its own (the page
  data sits in a non-executing JSON element that carries the nonce, so a script
  you add later can share it).
- **`object-src 'none'` and `base-uri 'none'`** block plugins and an injected
  `<base>` tag that would redirect relative URLs.
- **Local mode** changes three things and nothing else: `frame-ancestors` becomes
  the dev host's origin, `script-src` adds the Vite dev server's origin, and
  `connect-src` adds its websocket (a test checks this).
- **Only partly locked down:** the panel page sets no `default-src`, `style-src`
  or `connect-src`, so other resource types are not restricted there. Tighten it
  for your own app if your assets allow.

Other protections around the page:

- **Escaping.** Every value put into HTML goes through `html.escape` (title,
  asset URLs, the error page's code and message). The page data JSON in its
  `<script>` element is encoded so `<`, `>`, `&` and `'` become `<`-style
  escapes, so a value containing `</script>` cannot close the element. Tests use
  hostile values for both.
- **The Dialpad origin is checked twice before it reaches a header or a
  script:** `DIALPAD_ORIGIN` must be a bare origin at startup, and the renderers
  refuse anything that isn't one, because a `;` or a space in a CSP value would
  add directives.
- **The popup talks only to Dialpad.** The close-popup page calls
  `window.opener.postMessage('close_popup', <Dialpad origin>)`, never `'*'`, and
  only when it has an opener.
- **The SDK checks it is framed and who it talks to.** Opened directly (not in an
  iframe), the panel shows "Open this panel from Dialpad" (`not_framed`, covered
  by a browser test), and the SDK talks only to the `dialpad_origin` in the page
  data.
- **The page data holds no secrets:** no api key, no user profile, only the
  access token the panel needs, the connection status and the demo result.

### 5. Cookies, OAuth state and signed values

- **The session cookie** is `__Host-` prefixed (so `Secure`, `Path=/`, host only),
  `Secure`, `HttpOnly`, `SameSite=None` (required in a third-party iframe),
  `Partitioned` (kept separately per embedding site) and lasts 30 days. Its
  value is signed with HMAC-SHA256 using `APP_SECRET`: readable, but nobody
  without the secret can forge or change it.
- **Each signed value carries a `kind`**, so a value signed for one purpose, such
  as an OAuth `state`, is never accepted as another, such as a session cookie.
  Signatures and tokens are compared in constant time.
- **The OAuth `state`** is signed, tied to the Dialpad user, unique, and valid
  for 10 minutes. The callback verifies it and records a result only for the user
  it names, so a callback cannot be used to connect someone else.

### 6. Secrets and logs

- `DIALPAD_CLIENT_SECRET` (at least 48 characters, checked at startup) and
  `APP_SECRET` are kept out of the settings' `repr`, so they cannot appear in a
  log line or a traceback.
- **The access log is off**, because it would print every page URL and with it
  the idtoken. A quiet error handler logs only the method, path and exception
  type, never the query string. A test checks that neither the idtoken, the
  access token nor the cookie is logged.
- **Local mode is configuration only.** No request can switch it on, and its
  `/dev/frame-url` route, which mints a mock idtoken, exists only when it is on
  and allows cross-origin access only from the Vite origin.
- One thing the app cannot fix: Cloud Run's own request log records the full URL,
  idtoken included. See [deployment/README.md](deployment/README.md).

### 7. What the demo does not do

- **It does not persist the api key** or call Dialpad outside the page request
  (section 1).
- **The OAuth is fake**, and nothing is stored for a real CRM: no CRM tokens, no
  refresh.
- **Sessions are a cookie, not a server-side session**: it lasts 30 days, is per
  browser, can't be revoked early except by changing `APP_SECRET`, and a browser
  that refuses the cookie can't use the panel. A real partner would use stored
  sessions or expiring tokens.
- **No event-subscription receiver** (section 3), and no replay protection for
  the idtoken beyond keeping it out of logs, caches and referrers.
- **The panel page's CSP is script-focused** (section 4).
- **Secrets are plain environment variables**, which is fine for a demo; use a
  secret manager for anything real.

| Measure                                                   | Code                                      | Tests                                                                                                                                          |
| --------------------------------------------------------- | ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Idtoken algorithms, secret length, vectors from Dialpad   | `idtoken.py`                              | `test_idtoken.py`                                                                                                                              |
| Api key and `csr` never in page, responses, headers, logs | `contract.py`, `app.py`, `dialpad_api.py` | `test_the_page_embeds_page_data_and_never_the_api_key_or_csr`, `test_the_api_key_never_reaches_the_page_or_the_logs`                           |
| Bearer token must match the session cookie                | `database.py`, `app.py`                   | `test_a_call_needs_the_bearer_token_and_the_cookie_to_match`                                                                                   |
| CSP, nonce, security headers                              | `pages.py`                                | `test_page_headers_match_the_contract`, `test_every_script_on_the_page_carries_the_nonce`, `test_close_popup_*`                                |
| Escaping and origin validation                            | `pages.py`, `settings.py`                 | `test_hostile_page_data_stays_inside_its_element_and_round_trips`, `test_error_page_escapes_*`, `test_renderers_refuse_anything_but_an_origin` |
| Signed `state` and session cookie                         | `signing.py`                              | `test_signing.py`, `test_the_page_sets_the_session_cookie_that_holds_the_access_token`                                                         |
| Nothing secret is logged                                  | `app.py`                                  | `test_neither_the_idtoken_nor_the_access_token_is_logged`                                                                                      |
| Local mode only loosens the CSP in three places           | `app.py`, `settings.py`                   | `test_local_mode_changes_the_csp_in_three_places_only`, `test_the_dev_route_exists_only_in_local_mode`                                         |
| The SDK refuses to run outside Dialpad's iframe           | the SDK, `client/src/bootstrap.ts`        | `client/e2e/sdk/sdk.spec.ts` (opened outside Dialpad)                                                                                          |

(Server files are in `server/acme_crm/` and tests in `server/tests/`.)

## What to replace

| Here                                                             | With                                                                                                                                                                                                  |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/oauth/fake-authorize`, `/oauth/callback`                       | Your CRM's real authorize URL and callback; delete `server/acme_crm/fake_oauth.py`. Keep the close-popup page                                                                                         |
| `server/acme_crm/stores.py` (in-memory)                          | Nothing: store the CRM tokens in the callback and answer from them (see above)                                                                                                                        |
| The session cookie (`server/acme_crm/database.py`, `signing.py`) | Your stored CRM tokens, and a real session (a durable store or expiring tokens). The signed cookie is this demo's persistent storage of the access token and the connection, not part of the contract |
| `client/src/acme.ts`, `AcmeContact.vue`                          | Your CRM's data, matched to the Dialpad contact                                                                                                                                                       |
| `client/src/components/ConnectGate.vue`                          | Copy it and change the copy; it renders the SDK's `connection` state                                                                                                                                  |
| `ACCOUNT_NAME` in `server/acme_crm/app.py`                       | Your CRM's account name                                                                                                                                                                               |
| `server/acme_crm/dialpad_api.py`, `DialpadApiCard.vue`           | Delete both, and the call in the `page` handler. Store the api key and call Dialpad when you need to                                                                                                  |

Keep `server/acme_crm/idtoken.py` (the decoder), `server/acme_crm/pages.py` (the
page, close-popup and error rendering with their security headers) and
`server/acme_crm/contract.py` (the models the SDK reads): they are the
contract's server half, and the OAuth callback's close-popup page stays as it is. Replace
`TEST_CLIENT_SECRET` and `encode_mock_idtoken` only if you drop local mode.

## Checks

Each folder has its own checks; there is nothing to run at the repository root.

```sh
# client/ (the panel)
pnpm lint:ci && pnpm format:ci && pnpm types:check && pnpm test:run
pnpm test:e2e                                   # browser tests

# server/ (the Python server): the same tox environments as dialapp-external's contract/
uvx tox                                         # tests, linter, typechecker, check_python_code_style
uvx tox -e apply_python_code_style              # reformat with yapf
```

The server's tox environments build their own virtual environments with
[tox-uv](https://github.com/tox-dev/tox-uv) on Python 3.14, from
`server/requirements.txt` and the groups in `server/pyproject.toml`, so they
need no `.venv`. The pieces are: pytest (`filterwarnings = error`), Ruff
(`select = ALL`, as `contract/` has it), ty (all rules as errors) and yapf
(`server/.style.yapf`). In the `.venv` from [Install](#install), the same checks
run directly: `.venv/bin/pytest`, `.venv/bin/ruff check acme_crm tests`,
`.venv/bin/ty check acme_crm tests` and
`.venv/bin/yapf --style .style.yapf --diff -r acme_crm tests`.

`pnpm format:ci` also checks this README and `deployment/README.md`. `pnpm
test:e2e` starts the server (from `server/`, with its `.venv`, in local mode) and
Vite, then drives the dev host in Chromium with Playwright's clock. These tests
check this repository and the libraries in a real browser; they are not part of
the template, so delete `client/e2e/sdk/` (see its README) when you copy the
app. Install the browser once with `pnpm exec playwright install chromium`.
