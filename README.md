# Acme for Dialpad: A partner rightbar reference app

A small, runnable example of a Dialpad rightbar app, for partners who build one.
Dialpad loads the page, the page knows who the user is, the user connects a CRM
through an OAuth popup, and the iframe panel shows data Dialpad passes in.

There are two things here: the **rightbar app**, "Acme for Dialpad", which is this
repository, and the **CRM** it integrates with, "Acme CRM". The CRM is fictional,
with no data. The iframe panel proves
data flow by showing the Dialpad user, the active call, the OAuth scopes, and the
open Dialpad contact (plus the call's own contact when it is a different person)
with every field "Acme'd" (text gets an `Acme ` prefix).

**The frontend uses Dialpad's SDK for everything on the Dialpad side.** It is
`@dialpad/dialapp-external-sdk` (TypeScript), which Dialpad provides as a tarball
(see [Install](#install)). It is headless, so you build the panel with any
framework or none (this repository uses Vue; see the sections on
[plain JavaScript](#the-same-iframe-panel-in-plain-javascript) and
[React](#adapt-the-iframe-panel-to-react)). Vue is the preferred choice:
Dialtone, Dialpad's design system, ships its components as Vue components, so a
Dialpad-like UI is simpler and faster to build. The SDK does all of this, so your
code never touches it:

- Reads the page data the server put in the iframe's HTML, and checks that
  Dialpad frames the page.
- Speaks the host protocol with Dialpad over `postMessage`.
- Keeps one state snapshot: the Dialpad user, the open contact, the active call,
  the theme, and the connection to the CRM.
- Connects the user to the CRM through OAuth. It asks Dialpad to open the OAuth
  popup, notices when your OAuth callback finishes and the popup closes, and
  updates the connection state, so your panel shows the contact's CRM data
  without a reload. It also disconnects the user from the CRM, and tells Dialpad
  whether the user is connected.
- Sizes the panel's height, provides the `Authorization` header for your own
  requests (`authHeaders()`), and tells Dialpad about a matched CRM record
  (`linkRecord`).
- Provides mock Dialpad hosts for unit tests and browser tests.

See [Use the SDK](#use-the-sdk) for everything your panel code needs from it, and
[Test your panel](#test-your-panel) for its mock Dialpad.

**The Python server is a reference, not a requirement.** Use any backend in any
language. It only has to do four things: decode the idtoken, serve the page with
the page data in it (an access token and the connection status), answer the two
endpoints the SDK calls (`GET /dialpad/ext-connection` and
`POST /dialpad/ext-disconnect`), and serve your own routes. [`contract/openapi.json`](contract/openapi.json)
specifies the first three (see [The contract](#the-contract)). The pieces in
`server/acme_dialpad_rightbar/` that implement the contract are `idtoken.py`,
`pages.py`, and `contract.py` (built on `pydantic` and `joserfc`); port those and
keep the rest of your server as it is.

The repository has four parts:

| Folder        | What it is                                                                                                                                                                                      |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `client/`     | The iframe panel that Dialpad frames: Vite, Vue 3, TypeScript, and Dialtone 10. `pnpm` project                                                                                                  |
| `server/`     | The Python server (`acme_dialpad_rightbar/`): bare Sanic on Python 3.14, with its tests. Its endpoints are one file each, in `endpoints/dialpad/` and `endpoints/app/`. `tox` and `pip` project |
| `contract/`   | `openapi.json`: the language-neutral contract between Dialpad, a backend and the SDK (see [below](#the-contract))                                                                               |
| `deployment/` | The Dockerfile and how to run the app as a container on Cloud Run                                                                                                                               |

The iframe panel's CSS does not use Vue's `scoped` styles. Naming isolates the
classes instead: BEM with an `acme-` namespace
(`acme-<block>__<element>--<modifier>`), one class per selector, and no tag or
descendant selectors, so they cannot collide with Dialtone's classes or anything
else on the page. See the comment at the top of `client/src/style.css`.

Copy this repository and replace the parts listed under
[What to replace](#what-to-replace). The security side (the idtoken and its API
key, authenticating every request, CSP and nonces, and cookies) is collected in
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

The client installs the SDK from a file in `client/vendor/`, the same way you
install what Dialpad sends you: `client/package.json` points at
`vendor/dialpad-dialapp-external-sdk-<version>.tgz`. Nothing here needs
Dialpad's private registry. The server installs only public packages:
`requirements.txt` has what it runs on, and the `dev` dependency group in
`server/pyproject.toml` adds the test, lint, type-check, and style tools.

### Upgrade the SDK

Dialpad sends you each SDK build as a `dialpad-dialapp-external-sdk-<version>.tgz`
file. To move to a new one, from `client/`:

1. Replace the old tarball in `vendor/` with the new one (delete the old file).
2. Install it, which also updates `pnpm-lock.yaml`:

   ```sh
   pnpm add ./vendor/dialpad-dialapp-external-sdk-<version>.tgz
   ```

   This also updates the `file:vendor/...` dependency in `package.json`.

3. Run the client's checks (`pnpm types:check && pnpm test:run`, and
   `pnpm test:e2e` if you keep the browser tests).

The server has nothing to update: it uses no Dialpad library.

`client/scripts/vendor.mjs` (the `pnpm run vendor` script) is internal tooling
that Dialpad's own checks use to point this app at a freshly built tarball.
Partners can ignore it, and delete it together with the `vendor` script in
`client/package.json`.

The [contract](#the-contract) is not part of the tarball: `contract/openapi.json` is a
copy, and its `info.version` is the SDK version it describes. When you upgrade
the SDK, check that it still matches.

## Run locally, without Dialpad (local mode)

Local mode runs everything on `http://localhost`. Browsers treat `localhost` as
a secure context, so the `Secure`, `__Host-` connection cookie works, and the
dev host and the app are the same site, so the cookie isn't even third-party.
This works in Chrome and Firefox. Safari may not treat `localhost` as secure for
cookies; for Safari, use a trusted local certificate such as `mkcert`.

In two terminals:

```sh
cd server && LOCAL_MODE=1 .venv/bin/python -m acme_dialpad_rightbar   # server on http://localhost:8000
cd client && pnpm dev                                    # Vite on http://localhost:5173
```

Open <http://localhost:5173/dev-host/>. The dev host (`client/dev-host/`) stands
in for Dialpad: it asks the server for a page URL carrying a mock idtoken (made
by `server/acme_dialpad_rightbar/idtoken.py` with its test secret), frames the app, answers
`init`, opens the first of three contacts, and offers buttons to change contact
(cycling through the three), change the call state (ringing, connected, ended,
and a new call ringing), switch light and dark, and disconnect the way Dialpad's
panel menu does. Under the panel it lists the toasts the app shows (Connect
finished, Disconnected, and a failed contact lookup), which Dialpad shows
outside the panel.

Click **Connect**. The fake authorize URL opens in a popup showing a page that
says it is a fake OAuth page, with an **Authorize** button. The popup stays
open, and the iframe panel shows "Waiting for you to finish connecting", until you
press **Authorize**; the popup then goes to the callback and closes itself. Like the
desktop app, the dev host never replies to Connect, so the SDK's polling
completes it (first check after 7 seconds, then every 5). The iframe panel then shows
you, and the contact, Acme'd. **Disconnect** asks for inline confirmation.

`LOCAL_MODE=1` is configuration only; a request cannot switch it on. It changes
the page's `Content-Security-Policy` in three places and nowhere else:
`frame-ancestors` is the dev host's origin, `script-src` adds the Vite dev
server's origin, and `connect-src` adds its websocket origin.

## Run framed in Dialpad

This repository documents these steps but doesn't run them, because they need an
OAuth app that Dialpad sets up for you.

1. Build the iframe panel (`pnpm build` in `client/`) and run the server from `server/`
   without `LOCAL_MODE`, with the four required variables from
   [Configuration](#configuration):

   ```sh
   cd server && DIALPAD_CLIENT_SECRET=... DIALPAD_ORIGIN=https://dialpad.com \
     APP_SECRET=... BASE_URL=https://your-public-url .venv/bin/python -m acme_dialpad_rightbar
   ```

2. Expose the server at that public HTTPS URL (how is up to you).
3. Ask Dialpad to set the OAuth app's conversation sidebar URI to it.
4. Enable the app from Dialpad's admin settings.
5. Open any contact in Dialpad: the iframe panel appears, and connect, reconnect,
   and disconnect work against the real host.

The demo works in the Dialpad desktop app and the latest versions of Chrome, Edge,
Firefox, and Safari. The SDK itself supports Chrome 109 and later and the Dialpad desktop app (see
[Use the SDK](#use-the-sdk)).

## Configuration

The server reads these environment variables; the iframe panel reads none. Nothing
loads a `.env` file, so export them in your shell or your host's settings.

| Variable                | Required                | Purpose                                                                                                                                                                                                              |
| ----------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DIALPAD_CLIENT_SECRET` | yes, outside local mode | The OAuth app's client secret; decodes the idtoken. At least 48 characters (Dialpad's are 50). Local mode defaults to this app's own test secret (`TEST_CLIENT_SECRET` in `server/acme_dialpad_rightbar/idtoken.py`) |
| `DIALPAD_ORIGIN`        | yes, outside local mode | `https://dialpad.com`; the page's `frame-ancestors`. Must be a bare origin (scheme, host, and optional port; no trailing slash or path), checked at startup. Local mode defaults to `VITE_ORIGIN`                    |
| `APP_SECRET`            | yes, outside local mode | Demo only. A random secret the demo uses to sign the OAuth `state` and its session cookie (a real app keeps these in a database). Local mode defaults to a fixed development value                                   |
| `BASE_URL`              | yes, outside local mode | The public HTTPS URL of the server, without a trailing slash; used to build the authorize and callback URLs. Local mode defaults to `http://localhost:8000`                                                          |
| `HOST`                  | no                      | The address to listen on. Default `127.0.0.1` (this machine only); a container sets `0.0.0.0`. See [deployment/](deployment/README.md)                                                                               |
| `LOCAL_MODE`            | no                      | `1` turns on local mode: the defaults above, the dev host's route, and the Vite dev server's origins in the CSP                                                                                                      |
| `VITE_ORIGIN`           | no, local mode only     | The Vite dev server's origin. Default `http://localhost:5173`                                                                                                                                                        |
| `DIST_DIR`              | no                      | Where `pnpm build` in `client/` wrote the iframe panel. Default `../client/dist` (relative to `server/`); the container sets `dist`                                                                                  |
| `PORT`                  | no                      | The port to listen on. If unset, the port in `BASE_URL`, else `8000`. A container host sets it                                                                                                                       |

Keep `DIALPAD_CLIENT_SECRET` and `APP_SECRET` out of source control. The app reads
them from the environment; on Cloud Run, Secret Manager holds them and
passes them in as environment variables (see [deployment/](deployment/README.md)).

To run it as a container, for example on Cloud Run, see
[deployment/](deployment/README.md).

## Use the SDK

`@dialpad/dialapp-external-sdk` is headless: it ships no UI, so you build the panel
with your own components (this app uses Vue 3 and Dialtone 10). It supports Chrome
109 and later and the Dialpad desktop app, and it is ES modules only, so use a
bundler. This section is everything your panel code needs from it.

### Start it

`createRightbar()` reads the page data your server rendered, checks that Dialpad is
framing the page, completes the handshake with Dialpad, and loads the active call,
the theme, the Dialpad user, and the open contact. It resolves with the running
panel, whose `state` is ready to render. Start it once, before your first render
(`client/src/bootstrap.ts` does):

```ts
import { createRightbar, RightbarError } from "@dialpad/dialapp-external-sdk";
import { api } from "./api"; // your own module, with the standard fetch signature

const root = document.getElementById("app")!;
try {
  const rightbar = await createRightbar({
    heightRoot: root,
    fetch: api,
    onDisconnect: () => {
      // clear any partner data the panel holds
    },
  });
  // render your UI from rightbar.state
} catch (error) {
  if (!(error instanceof RightbarError)) throw error;
  root.textContent = "Open this panel from Dialpad.";
}
```

- **`heightRoot`** (required) is the element that holds the panel's content, normally
  your mount element. The SDK reports its height to Dialpad, which sizes the iframe
  to it. Overlays placed under `body` take no space in it and are not counted.
- **`fetch`** is the request function for the SDK's own calls (`/dialpad/ext-connection`,
  `/dialpad/ext-disconnect`, and the polling). It defaults to the browser's `fetch`,
  and the SDK adds the `Authorization` header to each call. This app passes its
  `api()` wrapper (`client/src/api.ts`), which also notices a `401`.
- **`onDisconnect`** is called after your `/dialpad/ext-disconnect` endpoint
  succeeded, whether the user disconnected from your button or from Dialpad's panel
  menu. The state already shows the panel as not connected; use it to clear partner
  data your panel holds. The SDK doesn't call it when the call fails.

`createRightbar()` rejects with a `RightbarError` whose `code` says why:

| Code            | Meaning                                                  |
| --------------- | -------------------------------------------------------- |
| `bad_options`   | `heightRoot` is missing, or a callback is not a function |
| `not_framed`    | The page is not open inside Dialpad                      |
| `bad_page_data` | The page data element is missing or invalid              |
| `init_timeout`  | Dialpad did not answer the handshake within 10 seconds   |

In every case the panel cannot work, so show a short "Open this panel from Dialpad"
message instead of the app, as the example does. Call `rightbar.destroy()` when the
panel unmounts: it stops listening to Dialpad, the polling, and the height reports.

With Vue, `app.use(rightbarPlugin, rightbar)` (from
`@dialpad/dialapp-external-sdk/vue`) provides the instance, and a component reads it
with `const { state, authorize, disconnect } = useRightbar()`, where `state` is a
ref. With any other framework, read `rightbar.state` and follow its changes
yourself; see [plain JavaScript](#the-same-iframe-panel-in-plain-javascript) and
[React](#adapt-the-iframe-panel-to-react).

The page data's `app` field, which your server fills with whatever JSON the panel
needs when it loads, is `rightbar.app` (`null` when there is none). This demo puts
the result of its server-side call to Dialpad's API there.

### The panel's size

The panel is 318 pixels wide in the right sidebar by default (266 to 414 as the
user resizes it) and 250 pixels in Dialpad Everywhere. Design the panel to be
responsive across that range, and test it at 250 pixels at the very least. This
app shrinks itself in narrower panels with a media query in
[`client/src/style.css`](client/src/style.css). Its height follows `heightRoot`.
A modal dialog can't leave the iframe, and the panel is narrow, so confirm
actions inline, as this app's **Disconnect** button does.

### The state

```ts
rightbar.state;
// { ready, user, contact, call, theme: { mode, brand },
//   connection: { connected, pending, authorizationUrls, name, scopes, error } }
```

Every change produces a new snapshot, and the parts that did not change keep their
references. `rightbar.subscribe((next, prev) => …)` follows every change, and
`rightbar.watch((state) => state.contact, (contact) => …)` runs its callback now and
then whenever that part changes.

| Field        | What it holds                                                                                                                                                                                                            |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `ready`      | `true` once the handshake and the first loads are done, which is always the case when `createRightbar()` has resolved                                                                                                    |
| `user`       | The Dialpad user, from what Dialpad answered at start (IDs, names, emails, phone numbers, licenses, admin flags, and availability), or `null`. Dialpad sends no update, so the status fields are as of the panel's start |
| `contact`    | The contact open in Dialpad, or `null`. It is reloaded when the user presses Dialpad's refresh button or the contact's record changes                                                                                    |
| `call`       | The active call, updated on every call event, or `null` without one                                                                                                                                                      |
| `theme`      | `{ mode: 'light' \| 'dark', brand }`. Follow `mode`, as `bootstrap.ts` does; `brand` is `null` in this SDK version                                                                                                       |
| `connection` | The user's connection to the CRM, in the next table                                                                                                                                                                      |

`connection` holds:

| Field               | What it holds                                                                                                                                                     |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `connected`         | The user has a working connection: show the connected view                                                                                                        |
| `pending`           | Connect is in progress                                                                                                                                            |
| `authorizationUrls` | Where Connect can send the user, by OAuth client name. Most apps have one; a company with several OAuth clients has one per client                                |
| `name`              | The name of the integration's OAuth client                                                                                                                        |
| `scopes`            | The OAuth scopes the client has. Use them to hide actions the user cannot take. Empty when not connected                                                          |
| `error`             | `null`, or why the last connection call failed: `{ code: 'request_failed', status }`, `{ code: 'network' }`, or `{ code: 'timeout' }`. The next success clears it |

### Actions and events

| Call                                                          | What it does                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `authorize(client?)`                                          | Starts Connect: asks Dialpad to open one of `connection.authorizationUrls` and polls until connected, or for 2 minutes. `client` names the OAuth client and can be left out when there is only one; it rejects for an unknown name, or when there are several and none is named. Does nothing when already connected, and starts over when called during Connect                                                                                                            |
| `refresh()`                                                   | Calls `GET /dialpad/ext-connection` and updates `connection`. The SDK also calls it at start when the page data says not connected, which picks up a Connect finished in an earlier panel. Never rejects: a failure goes in `connection.error`                                                                                                                                                                                                                              |
| `disconnect()`                                                | Calls `POST /dialpad/ext-disconnect`, shows the panel as not connected, and calls `onDisconnect`. Dialpad's panel menu does the same. On failure `connected` stays as it was and `connection.error` is set; it never rejects                                                                                                                                                                                                                                                |
| `authHeaders()`                                               | `{ Authorization: 'Bearer <access token>' }`, for your own requests to your backend                                                                                                                                                                                                                                                                                                                                                                                         |
| `linkRecord({ type, url })` / `linkRecord(null)`              | Tells Dialpad which of your records matches the open contact, typically after your server found it. Dialpad shows a **View `<type>`** button in the panel's header that opens `url` in a new tab (only while connected and the panel menu has Disconnect), and uses `url` as `screenPop()`'s default. `null` unlinks. Linking also changes the panel menu (see below)                                                                                                       |
| `showRefreshButton(show)`                                     | Shows or hides the refresh button in the panel's header. When the user presses it, the SDK reloads `state.contact` and then emits `refreshContact`                                                                                                                                                                                                                                                                                                                          |
| `showToast({ text, type })`                                   | Shows a short message in Dialpad, outside the panel. `type` is `info` (the default), `success`, or `error`. This app shows one when Connect finishes, when the user disconnects, and when a contact lookup fails                                                                                                                                                                                                                                                            |
| `screenPop({ url?, force? })`                                 | Asks Dialpad to open a record for the active call, by default the linked record's URL. Without `force`, Dialpad pops only when the user has screen pops turned on, during a live inbound call, at most once per call, and not for an office or department contact                                                                                                                                                                                                           |
| `on('rematch' \| 'refreshContact' \| 'createTask', callback)` | Calls `callback` when the event happens and returns a function that stops it. `refreshContact` fires after the SDK reloaded `state.contact`, either because the user pressed the header refresh button or because the contact's record changed in Dialpad. `rematch` and `createTask` fire when the user picks **Rematch** or **Create Task** in the panel menu, which Dialpad offers only to apps whose menu configuration includes them, and only once a record is linked |
| `destroy()`                                                   | Shuts the panel down when it unmounts                                                                                                                                                                                                                                                                                                                                                                                                                                       |

The panel menu depends on `linkRecord()`. Dialpad shows no menu until the app is
connected, then only **Disconnect** while no record is linked. Once a record is linked,
the menu becomes the app's own entry in Dialpad's menu configuration, which Dialpad
looks up by the app's name in lower case with the first space replaced by `_`; an app
without an entry gets an empty menu. This demo never links a record, so its menu is
only **Disconnect**. If you link records, ask Dialpad to set up your app's menu entry
first.

### Connect

Connect links the Dialpad user to their account in the CRM through the CRM's OAuth
flow.

1. Your Connect button calls `authorize()`. Dialpad opens the authorize URL (a popup
   on the web, a separate window on the desktop app) and `connection.pending` turns
   `true`. When a company has several OAuth clients, show their names and pass the
   chosen one: `authorize('sandbox')`.
2. The user signs in. Your OAuth callback stores their tokens and returns the
   close-popup page. On the web that page tells Dialpad (`close_popup`), which
   answers the SDK's pending request, and the SDK checks `/dialpad/ext-connection` at
   once. The desktop app's login window has no opener, so there the SDK's polling
   completes Connect.
3. Meanwhile the SDK checks `GET /dialpad/ext-connection` after 7 seconds, then every
   5 seconds. A failed check does not end Connect; the next one decides.
4. When `/dialpad/ext-connection` answers `connected: true`, the state turns
   `connected: true, pending: false`. After 2 minutes without that, Connect stops
   with `pending: false` and `error: { code: 'timeout' }`, and your UI should offer
   to try again (`ConnectGate.vue` does).

Disconnect works the same way from your button and from Dialpad's panel menu. The
SDK keeps the authorization URLs, so Connect shows straight away, and when your
endpoint answers with no body it checks `/dialpad/ext-connection` for current ones.
If the call fails, the state keeps `connected` and sets `connection.error`.

## Test your panel

The SDK ships a mock Dialpad, so you can test your own panel without Dialpad.

| Helper                                                                                 | Entry point                             |
| -------------------------------------------------------------------------------------- | --------------------------------------- |
| `createMockHost()`, with `host.createRightbar()`, `advance()`, `settle()`, `received`  | `@dialpad/dialapp-external-sdk/testing` |
| `mountMockHostPage({ src })`, for real browsers (Playwright, a dev page)               | `/testing`                              |
| `makePageData()`, `makeUser()`, `makeContact()`, `makeCall()`, `disposeAllMockHosts()` | `/testing`                              |
| A setup file for Vitest or Jest                                                        | `/testing/setup`                        |
| `mountWithRightbar(component, options)`, for Vue components                            | `/vue/testing`                          |

For Vitest, add the setup file:

```ts
// vitest.config.ts
test: {
  environment: 'jsdom',
  globals: true,
  setupFiles: ['@dialpad/dialapp-external-sdk/testing/setup'],
}
```

`createMockHost()` runs in memory with its own clock, so a Connect test calls
`await host.advance(7_000)` instead of using fake timers. `host.received` records what
the panel asked Dialpad to do (toasts, the linked record, screen pops, the refresh
button, and authorize requests). `mountMockHostPage()` frames your real page, whose
backend renders the page data from a mock idtoken (this app's local mode serves such
a URL at `/dev/frame-url`), so it takes no page data itself. Pass `fetch` to
`host.createRightbar()` to answer the two Connect endpoints. With `globals: true` (or
in Jest) the setup file disposes every mock host after each test; otherwise call
`disposeAllMockHosts()` in your own `afterEach`.

A first test:

```ts
import { expect, test } from "vitest";
import {
  createMockHost,
  makeCall,
  makeContact,
} from "@dialpad/dialapp-external-sdk/testing";

test("shows the call as it connects", async () => {
  const host = createMockHost({ contact: makeContact({ displayName: "Ada" }) });
  const rightbar = await host.createRightbar({
    heightRoot: document.createElement("div"),
  });
  expect(rightbar.state.contact?.displayName).toBe("Ada");

  host.sendCall(makeCall({ state: "connected" }));
  await host.settle();
  expect(rightbar.state.call?.state).toBe("connected");

  await rightbar.linkRecord({ type: "Contact", url: "https://crm.example/1" });
  expect(host.received.linkedRecord?.url).toBe("https://crm.example/1");
});
```

This repository's own tests are worked examples: `client/src/App.test.ts` drives every
state of the panel against the mock host (`pnpm test:run`), and `client/e2e/sdk/` drives
the dev host in a real browser (`pnpm test:e2e`).

## The contract

[`contract/openapi.json`](contract/openapi.json) is an OpenAPI 3.1 document that
specifies what a backend must expose for the SDK and Dialpad, in any language. Its
`info.version` is the SDK version it describes (check it against the SDK in
`client/vendor/` when you upgrade). It is generated, so don't edit it by hand.

| Operation                      | Authenticated by        | Answers                                                                                                                                                                                    |
| ------------------------------ | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `GET /`                        | `?idtoken=…`            | The panel page, served at the app's conversation sidebar URI. `401` is a minimal error page when the idtoken doesn't decode; `403` is the same kind of page when your app refuses the user |
| `GET /dialpad/ext-connection`  | The bearer access token | `200` with an `ExternalConnection`: this Dialpad user's connection to the CRM. `401` when your token is rejected                                                                           |
| `POST /dialpad/ext-disconnect` | The bearer access token | `204` with no body (a `200` with an `ExternalConnection` works too): disconnects this Dialpad user. `401` when your token is rejected                                                      |
| `GET /oauth/callback`          | Your own OAuth `state`  | `200` with the close-popup page, after storing the tokens. The path is your choice                                                                                                         |

Its schemas are `IdTokenClaims` (what decoding the idtoken returns), `PageData` (what
the page embeds for the SDK), `ExternalConnection` (the connection status), and
`ErrorResponse`. The SDK always calls the contract endpoints under `/dialpad`. Your own
feature endpoints sit beside these and are not part of the contract.

An `ExternalConnection`, which `ext-connection` answers and the page data carries, has
four fields: `connected`; `authorization_urls`, the authorize URL for each OAuth client
by client name, with at least one entry when `connected` is false; `name`, the OAuth
client's name; and `scopes`, the client's OAuth scopes, empty when not connected.
`server/acme_dialpad_rightbar/contract.py` is this app's Python implementation of the
schemas. The flows in [FLOWS.md](FLOWS.md) show when each operation is called.

## How it works

Dialpad loads the page with an idtoken; the server decodes it, starts a session,
and renders the iframe panel; the panel authenticates every later request with an
access token in a header; the user connects through an OAuth popup, and the panel
then shows their data and the CRM's view of the open contact.

**[FLOWS.md](FLOWS.md)** explains each flow of a real partner app with diagrams:
[page load](FLOWS.md#1-initial-iframe-page-load),
[authenticating requests](FLOWS.md#2-authenticating-every-request-from-the-iframe-panel),
[OAuth](FLOWS.md#3-external-oauth-connect),
[disconnect](FLOWS.md#4-external-disconnect),
[contact pulling](FLOWS.md#5-external-contact-pulling),
[server-to-server calls to Dialpad's API](FLOWS.md#6-server-to-server-calling-dialpads-api),
and [event subscriptions and webhooks](FLOWS.md#7-event-subscriptions-and-webhooks).
This README says how the demo simplifies them
([below](#how-the-demo-differs-from-a-real-app)).

Each endpoint is one file under `server/acme_dialpad_rightbar/endpoints/`: the ones Dialpad or
its SDK calls (the [contract](#the-contract)) are in `dialpad/`, and the application's own
are in `app/`. Each folder's `__init__.py` lists them.

| Endpoint                       | File                          | Behavior                                                                                                                                                                                                                                                                                       |
| ------------------------------ | ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /`                        | `dialpad/page.py`             | The page. `401` HTML if the idtoken doesn't decode                                                                                                                                                                                                                                             |
| `GET /dialpad/ext-connection`  | `dialpad/ext_connection.py`   | Bearer token matching the cookie's. Consumes a stored OAuth result, else answers from the cookie. Fresh authorize URL                                                                                                                                                                          |
| `POST /dialpad/ext-disconnect` | `dialpad/ext_disconnect.py`   | Bearer token matching the cookie's. Turns the connection off in the cookie, answers `204` with no body                                                                                                                                                                                         |
| `POST /api/contact`            | `app/contact.py`              | A sample endpoint that the client library doesn't invoke but the application's own frontend does, showcasing feature extensibility. Bearer token matching the cookie's, user connected. Answers with the CRM's view of a Dialpad contact (see [below](#the-contact-lookup-demo-vs-a-real-app)) |
| `GET /oauth/fake-authorize`    | `app/oauth_fake_authorize.py` | Demo only. A page labelled fake, with an Authorize button that goes to the callback with `state` and a fixed `code`                                                                                                                                                                            |
| `GET /oauth/callback`          | `app/oauth_callback.py`       | The OAuth redirect URI. Verifies `state`, closes the popup. The demo only records that the user connected; a real app also exchanges the `code` for CRM tokens and persists them in a database                                                                                                 |
| `GET /healthz`                 | `app/healthz.py`              | Answers `ok`. Mainly for the Playwright e2e setup; partners can ignore it                                                                                                                                                                                                                      |
| `GET /dev/frame-url`           | `app/dev_frame_url.py`        | Local mode only. The dev host's page URL with a mock idtoken                                                                                                                                                                                                                                   |

## How the demo differs from a real app

The demo uses a signed cookie as its persistent storage, to avoid needing a real
database. It holds the user's access token and whether they are connected (to an external CRM), which
a real app keeps in database rows (a session, and the CRM tokens its OAuth
callback stored).

| Flow                                                                                        | This demo                                                                                                                                    | A real app                                                                                 |
| ------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| [1. Page load](FLOWS.md#1-initial-iframe-page-load)                                         | Embeds a random access token and sets a signed session cookie that holds it; uses the `api_key` once for a demo call and drops it            | Stores the `api_key`, creates a session row, no cookie                                     |
| [2. Authenticating requests](FLOWS.md#2-authenticating-every-request-from-the-iframe-panel) | The bearer token must equal the cookie's token (a double submit)                                                                             | Looks the bearer token up in a session table; no cookie                                    |
| [3. OAuth](FLOWS.md#3-external-oauth-connect)                                               | A fake authorize page; the callback leaves an in-memory note that the iframe panel's next check collects, and the cookie records "connected" | The CRM's authorize page; the callback exchanges the `code` for CRM tokens and stores them |
| [4. Disconnect](FLOWS.md#4-external-disconnect)                                             | Turns "connected" off in the cookie, in that browser only                                                                                    | Revokes and deletes the user's CRM tokens                                                  |
| [5. Contact pulling](FLOWS.md#5-external-contact-pulling)                                   | Prefixes every text field with `Acme `                                                                                                       | Maps the contact to a CRM record, fetches it with the CRM token, calls `linkRecord`        |
| [6. Server to server](FLOWS.md#6-server-to-server-calling-dialpads-api)                     | One call on the page request                                                                                                                 | Stores the key and calls Dialpad's API whenever needed                                     |
| [7. Webhooks](FLOWS.md#7-event-subscriptions-and-webhooks)                                  | Not implemented                                                                                                                              | A receiver that verifies each event's signed JWT                                           |

### Why the demo has an `APP_SECRET`

`APP_SECRET` is this demo's own device, not something Dialpad or the SDK asks for. The demo has no
database and no cache, so it keeps what it must remember in values it signs and
hands to the browser: the OAuth `state` carries the user and an expiry, and the
session cookie carries the access token and the connection. Signing is what lets
the server trust them when they come back.

Applications usually keep that state on the server instead:

- **Sessions** — On the first page load, create a session row in your database
  or cache for that Dialpad user, with a random token; embed the token in the page
  data and have the iframe panel send it as the bearer. The server looks the token up on
  each request. No signed cookie is needed, because the browser holds only an
  opaque ID, and you can revoke a session by deleting the row.
- **OAuth `state`** — Generate a random `state` for each Connect, store its context
  (the Dialpad user, where to return to) in Redis or the database with a short
  expiry, and look it up in the callback.
- **The connection** — The callback stores the CRM tokens durably, keyed by the
  Dialpad user, and "connected" means those tokens exist.
- **A secret of your own is still useful**, but for other jobs: deriving the
  signing secret of each event subscription's webhook, and encrypting at rest what
  you store (CRM tokens, the Dialpad `api_key`).

The demo's approach has no storage to run, but it cannot revoke a session, its
values live in the browser (30 days, per browser), and rotating `APP_SECRET`
signs everyone out.

### How the demo authenticates requests (a cookie as the persistence workaround for a database)

The demo has no session table, so the session lives in a signed cookie, and every
request must send the bearer token **and** the cookie, which must hold the same
token (compared in constant time, with the cookie's signature and age valid):

```http
GET /dialpad/ext-connection
Authorization: Bearer <the access token from the page data>
Cookie: __Host-acme_session=<signed session>
```

`ctx.state_for(request)` does that check and returns the user's
`CookieBackedDatabaseStorage`, or `None`. The cookie has to be `SameSite=None`,
because the iframe panel runs in a third-party iframe, so browsers also attach it
to requests made by other sites. The header can only be added by code that holds
the page data, so requiring the two to match is the "double submit" defense
against cross-site request forgery. A real app, with a session table, needs only
the header (see [Security, section 2](#2-authenticate-requests-to-your-server)).

The cookie's attributes and the signed values:

- **The session cookie** is `__Host-` prefixed (so `Secure`, `Path=/`, host only),
  `Secure`, `HttpOnly`, `SameSite=None` (required in a third-party iframe),
  `Partitioned` (kept separately per embedding site) and lasts 30 days. Its value
  is signed with HMAC-SHA256 using the demo's signing secret: readable, but nobody
  without the secret can forge or change it.
- **Each signed value carries a `kind`**, so a value signed for one purpose, such
  as an OAuth `state`, is never accepted as another, such as a session cookie.
  Signatures and tokens are compared in constant time.
- **The OAuth `state`** is signed too: tied to the Dialpad user, unique, and valid
  for 10 minutes. The callback verifies it and records a result only for the user
  it names, so a callback cannot be used to connect someone else.

### The contact lookup (demo vs. a real app)

**What the demo does.** There is no CRM, so there is no mapping. The iframe panel
(`client/src/components/AcmeContact.vue`) sends the Dialpad contact to
`POST /api/contact`, and the server (`server/acme_dialpad_rightbar/endpoints/app/contact.py`,
whose docstring also describes the real thing) answers with every non-empty field
prefixed `Acme `. That proves the contact reached the server and came back, and
that the request was authenticated as the right user. The iframe panel shows a
loading state and a failure message, and ignores a late answer for a contact that
is no longer open. A real app does what
[flow 5](FLOWS.md#5-external-contact-pulling) describes.

### The demo call to Dialpad's API

**Unnecessary for the app, and for demo purposes only.** While it renders the
page, the server uses the idtoken's `api_key` to call Dialpad's public API, to
show how the key is used: `GET {DIALPAD_ORIGIN}/api/v2/users/me` with
`Authorization: Bearer <api_key>`, made by Dialpad's own Python client
([`python-dialpad`](https://pypi.org/project/python-dialpad/)), in
`server/acme_dialpad_rightbar/dialpad_api.py`. The iframe panel shows the user's name, email, ID,
and state in a "From Dialpad's API" card.

- The call has a 3-second timeout and no retry. If Dialpad's API refuses the
  key, fails, or is slow, the page renders anyway and the card says "Dialpad API
  unavailable".
- Local mode makes no call (the mock idtoken's key isn't real), and the card
  says so.
- The server uses the key for this one call and drops it. It never puts the key
  in the page, logs it, or returns it, and it doesn't store the idtoken.

A real application works differently: it **persists the API key in long-term
storage** and **uses it to call Dialpad whenever it needs to**
([flow 6](FLOWS.md#6-server-to-server-calling-dialpads-api)).

Dialpad's public API, with every endpoint and its rate limit, is documented at
[developers.dialpad.com](https://developers.dialpad.com/).

**Event subscriptions.** A real app often has to react to what happens in
Dialpad when nobody has the panel open, for example logging a finished call or
an SMS on the CRM's record. Dialpad can push such events (calls, SMS, contacts,
agent status, and change logs) to a webhook URL on the app's server. The app
registers that URL as a webhook, and the events it wants as subscriptions,
through the same API with a key, as described in Dialpad's
[Event Subscriptions](https://developers.dialpad.com/docs/event-subscriptions)
guide. When an event occurs, Dialpad calls the webhook URL on your server (the
**webhook callback**) with the event as a JWT signed with a secret you chose, so
the callback verifies the signature before trusting it. The demo has no
subscriptions and no webhook receiver;
[flow 7](FLOWS.md#7-event-subscriptions-and-webhooks) shows how to set one up
and validate the callbacks.

### Why the demo keeps connection results in memory

The Connect flow in short: the iframe panel's page says "not connected" with an
authorize URL; Connect makes Dialpad open it in a popup while the iframe panel polls
`/dialpad/ext-connection`; the user approves at the CRM, which sends the popup
to `/oauth/callback`; the callback verifies the signed `state` and closes the
popup; the iframe panel's next poll learns it is connected and gets its session cookie
rewritten with the connection on.

The catch is that the callback and the iframe panel are different windows. The
callback runs in the popup, and the session cookie belongs to the iframe panel
(it is `Partitioned`), so the callback cannot set it. The only thing both sides know
is which Dialpad user this is, so the callback leaves a short-lived note in
server memory ("this user finished connecting", kept for 5 minutes and
collected once), and the iframe panel's next check picks it up. That note is
`OAuthResults` in `server/acme_dialpad_rightbar/stores.py`, whose docstring tells the whole
flow.

**This exists only because the demo has no real CRM.** A real partner's
callback exchanges the `code` for CRM tokens and stores them durably, keyed by
the Dialpad user, and `ext-connection` answers "connected" when those tokens
exist, from the database, on any instance and after any restart. Then there is
no handoff and no expiry, and both `OAuthResults` and the cookie can go.

Without a database, this demo keeps what has to last, the user's access token and
"this user is connected to the CRM", in the signed, 30-day session cookie, which
survives a server restart or scale-to-zero. The cookie's limits are listed under
[Why the demo has an `APP_SECRET`](#why-the-demo-has-an-app_secret) and in
[section 6](#6-what-the-demo-does-not-do); a real partner's stored tokens and
sessions have none of them.

## Security: What the demo shows

A rightbar iframe panel is a web page that Dialpad frames, opened with a long-lived
credential in its URL, that then talks to your server. This section lists what
the app does about each risk. The last subsection says what it deliberately does
not do.

**Which secret is which.** Four different secrets appear below, and they are not
interchangeable:

| Secret                                                | Who issues it                               | What it is used for                                                                             |
| ----------------------------------------------------- | ------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| **OAuth app client secret** (`DIALPAD_CLIENT_SECRET`) | Dialpad, when it sets up your OAuth app     | Decrypting and verifying the **idtoken** on the page request. Nothing else in this app uses it. |
| **`api_key`** (inside the idtoken)                    | Dialpad, per user and app                   | `Authorization: Bearer` on your server's calls to Dialpad's public API                          |
| **Access token** (in the page data and cookie)        | Your server, per browser session            | `Authorization: Bearer` on every request the iframe panel makes to your server                  |
| **Webhook signing secret**                            | You, when you create a webhook with Dialpad | Verifying the JWT on events Dialpad sends to you (not implemented in this demo)                 |

### 1. The idtoken and its API key

When Dialpad loads the iframe panel it appends `?idtoken=<token>` to your conversation
sidebar URI. The token is encrypted (a JWE using `dir` and `A192CBC-HS384`,
keyed with the first 48 characters of your **OAuth app's client secret**, the
`DIALPAD_CLIENT_SECRET`) and wraps a
JWT signed with `HS256` and the full client secret. Its claims are the Dialpad
`user_id`, `company_id`, and `office_id`; the user's `name`, `email`,
`phone_number`, and `image_url`; an internal `csr` claim; and the `api_key`.

**How to decode it.** Any JOSE library can do this; the demo uses `joserfc`
(`decode_idtoken` in `server/acme_dialpad_rightbar/idtoken.py`).

1. Read the `idtoken` query parameter. If it is missing or empty, answer `401`.
2. Decrypt it as a compact JWE. The key is the first 48 characters of the client
   secret, as UTF-8 bytes, used directly: `dir` means no key wrapping, hashing or
   derivation. Allow only `alg: dir` and `enc: A192CBC-HS384`, and refuse a token
   with any other header. Dialpad generates client secrets 50 characters long, so
   a shorter secret is a configuration error, not a bad token.
3. The decrypted payload is a compact JWT. Verify its signature with the full
   client secret, as UTF-8 bytes, allowing only `HS256`, so `none` or any other
   algorithm is refused.
4. Read the claims. `user_id`, `company_id`, `office_id`, and `api_key` are
   required; the profile claims (`name`, `email`, `phone_number`, and `image_url`)
   may be missing. Drop `csr`, and ignore claims you don't know, since Dialpad may
   add more. The token has no `exp` claim, so don't make your JWT library require
   one.
5. Treat a failure at any step the same way: answer `401` with an error page,
   render no page data, and don't log the token.

To test a decoder in another language, use the tokens in
`server/tests/vectors/dialpad_idtokens.json`. They are built the way Dialpad
builds them, with a test client secret that is in the same file, and each one
lists the claims it must decode to.

**Where to use it: on your server, on that one page request, and nowhere else.**
`decode_idtoken` (`server/acme_dialpad_rightbar/idtoken.py`) accepts only those two
algorithms, treats a client secret shorter than 48 characters as a configuration
error, and raises one error type whose message never contains the token or the
secret. A page that fails to decode gets a `401` page and no page data. The
claims tell you who opened the iframe panel; they are never rendered into the page, and
`csr` is dropped while decoding.

**The `api_key` is a credential for Dialpad's public API**, scoped to that user
and this app. It is server-side only: `IdTokenClaims` holds it as a `SecretStr`,
`PageData` has no field for it, and tests check it appears in no page, response,
header, or log.

**Why a real app persists the API key (this demo does not).** The idtoken arrives
only while a user has the iframe panel open, but your server needs to call Dialpad at
other times: from a background job, when a webhook arrives, or after the iframe panel
is closed. The API key does not expire, so the first time you see it for a
Dialpad user, store it in long-term storage keyed by company ID and user ID
(protected like your CRM tokens: encrypted at rest, never logged), and replace
it whenever a newer idtoken carries a different one. This demo stores nothing: it
uses the key once, on the page request, for the demo call described in
[The demo call to Dialpad's API](#the-demo-call-to-dialpads-api), and drops it.

The idtoken has no expiry that this app checks, and it travels in a URL, so
treat that URL as a secret: the page is served with `Referrer-Policy:
no-referrer` and `Cache-Control: no-store`, the access log is off, and the
idtoken is never stored (see [Secrets and logs](#5-secrets-and-logs)).

### 2. Authenticate requests to your server

There are two kinds, and they use different credentials.

- **The page request** is authenticated by the idtoken (above). There is no
  session yet; decoding the token with your client secret is the authentication.
- **Every request the iframe panel makes to your server** comes from the iframe, which
  has no idtoken. That includes the two requests the SDK makes itself
  (`ext-connection` and `ext-disconnect`, the only two the SDK invokes) and every
  route your application adds (a real app has many). The page
  response therefore starts a session: the server stores a session for the Dialpad
  user (its token's hash, the user, and an expiry) and embeds the random, opaque
  **access token** in the page data. Each request must send it as a bearer token:

  ```http
  GET /dialpad/ext-connection
  Authorization: Bearer <the access token from the page data>
  ```

  The server looks the token up and answers only when it finds an unexpired
  session; the session says which Dialpad user is asking. Otherwise it answers
  `401`, and the iframe panel asks the user to reload. Deleting the session row
  revokes it.

Keep the token in memory, not in `localStorage`, and let the CSP in
[section 4](#4-framing-csp-and-nonces) keep injected scripts out.

**Adding your own routes.** On the iframe panel side, send them through the `api()`
wrapper in `client/src/api.ts`, which adds the bearer header (the SDK's
`authHeaders()`) to every request and turns a `401` into the "Reload the panel"
notice. On the server side, add a file under `server/acme_dialpad_rightbar/endpoints/app/` with
a `register(app, ctx)` function (copy `contact.py`) and list it in that folder's
`__init__.py`. Authenticate the route the way the SDK's own two routes do, with
`ctx.state_for(request)`, which turns the bearer token into the user's state, or
`None` when it is missing or unknown. Use that, not the idtoken, to know who is
asking (a sketch):

```python
@app.get('/api/notes')
async def notes(request: Request) -> HTTPResponse:
  state = ctx.state_for(request)
  if state is None:
    return unauthorized()  # from acme_dialpad_rightbar.responses
  user = state.user_key()  # the Dialpad company and user making the request
  ...
```

The contract only needs _some_ token the iframe panel can send; a signed JWT with a
short expiry works as well as a session table, without the lookup.

### 3. Authenticate requests to Dialpad

Calls from your server to Dialpad's public API carry the API key as a bearer
token, against the Dialpad origin you are configured for (`DIALPAD_ORIGIN`,
`https://dialpad.com`):

```http
GET https://dialpad.com/api/v2/users/me
Authorization: Bearer <api_key>
```

`server/acme_dialpad_rightbar/dialpad_api.py` does this with Dialpad's own Python client,
`AsyncDialpadClient(token=api_key, base_url=origin)`, which adds that header to
every request. Use a short timeout and no retries for anything on the page
request path, and treat a `401` as "the key was refused". The key goes only in
that header, from your server. **The browser never has it and never calls
Dialpad's API directly**; what the iframe panel needs from Dialpad (the user, the open
contact, the call) arrives through the SDK's host protocol, which needs no key
because Dialpad itself framed the page.

**Incoming event subscriptions** (events for calls, SMS, contacts, and agent
status, plus change logs) go the other way: Dialpad sends a request to a webhook URL on your
server, so you have to authenticate Dialpad. When you create the webhook you
provide a **signing secret**, and Dialpad then sends every event as a JWT signed
(`HS256`) with it. If you provide no secret, events arrive as unsigned JSON that
anyone could forge, so always provide one. Verify the JWT's signature with that
secret and only then trust the payload.

That secret is a string _you_ choose and hand to Dialpad when creating the
webhook: Dialpad does not issue it, it is not the API key, and Dialpad's docs do
not say it has to be your OAuth app's client secret. Dialpad recommends a unique
one per subscription, so a leak exposes only one subscription (you could, for
example, derive each from a secret of your own). See Dialpad's
[Event Subscriptions](https://developers.dialpad.com/docs/event-subscriptions)
guide (its security paragraph) and the
[Webhook Create](https://developers.dialpad.com/reference/webhookscreate)
reference, which describe the signed events and the secret. This demo has no
webhook receiver, so none of this is exercised here.

### 4. Framing, CSP and nonces

Every page the server renders carries a `Content-Security-Policy`, plus
`Referrer-Policy: no-referrer`, `Cache-Control: no-store`, and
`X-Content-Type-Options: nosniff`.

| Page                              | `Content-Security-Policy`                                                                                           |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| The iframe panel, `GET /`         | `frame-ancestors <DIALPAD_ORIGIN>; script-src 'self' 'nonce-…' <asset origins>; object-src 'none'; base-uri 'none'` |
| Close-popup page (OAuth callback) | `default-src 'none'; script-src 'nonce-…'; style-src 'nonce-…'; frame-ancestors 'none'; base-uri 'none'`            |
| Error page (`401`)                | `default-src 'none'; style-src 'nonce-…'; frame-ancestors <DIALPAD_ORIGIN>; base-uri 'none'`                        |
| Fake authorize page (demo OAuth)  | `default-src 'none'; style-src 'nonce-…'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`              |

- **`frame-ancestors`** lets only Dialpad embed the iframe panel, which prevents other
  sites from framing it (clickjacking). The popup pages cannot be framed at all.
- **`script-src 'self' 'nonce-…'`, with no `'unsafe-inline'` or
  `'unsafe-eval'`**, means only the app's own script files run. An inline script
  that an XSS bug injects into the page doesn't run.
- **The nonce** is a fresh random value for each response
  (`secrets.token_urlsafe`), written both into the CSP header and onto the
  inline elements that are allowed. The close-popup page's one inline script and
  style run only because they carry it; reusing a nonce across responses
  defeats the policy. The iframe panel page has no inline script of its own (the page
  data sits in a non-executing JSON element that carries the nonce, so a script
  you add later can share it).
- **`object-src 'none'` and `base-uri 'none'`** block plugins and an injected
  `<base>` tag that redirects relative URLs.
- **Local mode** changes three things and nothing else: `frame-ancestors` becomes
  the dev host's origin, `script-src` adds the Vite dev server's origin, and
  `connect-src` adds its websocket (a test checks this).
- **Only partly locked down** — The iframe panel page sets no `default-src`,
  `style-src`, or `connect-src`, so other resource types are not restricted there. Tighten it
  for your own app if your assets allow.

Other protections around the page:

- **Escaping** — Every value put into HTML goes through `html.escape` (the title,
  the asset URLs, and the error page's code and message). The page data JSON has its own
  rule; see [Escape the page data](#escape-the-page-data). Tests use hostile
  values for both.
- **The Dialpad origin is checked twice before it reaches a header or a
  script:** `DIALPAD_ORIGIN` must be a bare origin at startup, and the renderers
  refuse anything that isn't one, because a `;` or a space in a CSP value adds
  directives.
- **The popup talks only to Dialpad.** The close-popup page calls
  `window.opener.postMessage('close_popup', <Dialpad origin>)`, never `'*'`, and
  only when it has an opener.
- **The SDK checks it is framed and who it talks to.** Opened directly (not in an
  iframe), the iframe panel shows "Open this panel from Dialpad" (`not_framed`, covered
  by a browser test), and the SDK talks only to the `dialpad_origin` in the page
  data.
- **The page data holds no secrets** — No API key and no user profile, only the
  access token the iframe panel needs, the connection status, and the demo result.

#### Escape the page data

The page data travels inside the page as JSON, in this element:

```html
<script type="application/json" id="dialpad-page-data" nonce="…">
  {"version": 1, …}
</script>
```

`html.escape` is the wrong tool here. The browser doesn't decode HTML entities
inside a `<script>` element, so `&lt;` reaches the SDK as those four
characters, not as `<`. Plain `json.dumps` isn't enough either: the browser ends
the element at the first `</script>` in the text, wherever it appears, including
inside a JSON string. A contact name such as `</script><script>alert(1)</script>`
closes the element and injects a script.

So after encoding the JSON, replace these four characters everywhere in it:

| Character | Write it as |
| --------- | ----------- |
| `<`       | `\u003c`    |
| `>`       | `\u003e`    |
| `&`       | `\u0026`    |
| `'`       | `\u0027`    |

JSON reads each escape back as the same character, so `JSON.parse` in the SDK
gets the original values, but the text can no longer close the element, open an
HTML comment (`<!--`), or break out of a quoted attribute. The replacement is
safe to do on the whole encoded text, because those characters can only appear
inside JSON strings. Other characters stay as they are.

Or use a library that does this for you, such as Jinja2's `tojson` filter in
Python or Gson's `new Gson().toJson(value)` on the JVM.

### 5. Secrets and logs

- `DIALPAD_CLIENT_SECRET` (at least 48 characters, checked at startup) and
  the demo's signing secret are kept out of the settings' `repr`, so they cannot appear in a
  log line or a traceback.
- **The access log is off**, because it prints every page URL and, with it,
  the idtoken. A quiet error handler logs only the method, path and exception
  type, never the query string. A test checks that the server never logs the
  idtoken, the access token, or the cookie.
- **Local mode is configuration only.** No request can switch it on, and its
  `/dev/frame-url` route, which mints a mock idtoken, exists only when it is on
  and allows cross-origin access only from the Vite origin.
- One thing the app cannot fix: Cloud Run's own request log records the full URL,
  idtoken included. See [deployment/README.md](deployment/README.md).

### 6. What the demo does not do

- **It does not persist the API key** or call Dialpad outside the page request
  (section 1).
- **The OAuth is fake**, and nothing is stored for a real CRM: no CRM tokens, no
  refresh.
- **Sessions are a cookie, not a server-side session**: it lasts 30 days, is per
  browser, can't be revoked early except by changing the demo's signing secret, and a browser
  that refuses the cookie can't use the iframe panel. A real partner uses stored
  sessions or expiring tokens.
- **No event-subscription receiver** (section 3), and no replay protection for
  the idtoken beyond keeping it out of logs, caches, and referrers.

## What to replace

| Here                                                                                             | With                                                                                                                                                                                                  |
| ------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/oauth/fake-authorize`                                                                          | Your CRM's real authorize URL; delete `server/acme_dialpad_rightbar/fake_oauth.py`                                                                                                                    |
| `/oauth/callback`                                                                                | Keep the route, its `state` check and the close-popup page; replace what it records with the `code` exchange and persisting the CRM tokens in a database                                              |
| `server/acme_dialpad_rightbar/stores.py` (in-memory)                                             | Nothing: store the CRM tokens in the callback and answer from them (see [flow 3](FLOWS.md#3-external-oauth-connect))                                                                                  |
| The session cookie (`server/acme_dialpad_rightbar/database.py`, `signing.py`)                    | Your stored CRM tokens, and a real session (a durable store or expiring tokens). The signed cookie is this demo's persistent storage of the access token and the connection, not part of the contract |
| `server/acme_dialpad_rightbar/endpoints/app/contact.py`, `client/src/components/AcmeContact.vue` | The contact lookup: map the Dialpad contact to a CRM record with the user's CRM token, and return its fields (see [flow 5](FLOWS.md#5-external-contact-pulling))                                      |
| `client/src/components/ConnectGate.vue`                                                          | Copy it and change the copy; it renders the SDK's `connection` state                                                                                                                                  |
| `ACCOUNT_NAME` in `server/acme_dialpad_rightbar/context.py`                                      | Your CRM's account name                                                                                                                                                                               |
| `server/acme_dialpad_rightbar/dialpad_api.py`, `DialpadApiCard.vue`                              | Delete both, and the call in `endpoints/dialpad/page.py`. Store the API key and call Dialpad when you need to                                                                                         |

Keep `server/acme_dialpad_rightbar/idtoken.py` (the decoder), `server/acme_dialpad_rightbar/pages.py` (the
page, close-popup, and error rendering, with their security headers), and
`server/acme_dialpad_rightbar/contract.py` (the models the SDK reads, as specified in
`contract/openapi.json`): they are the contract's server half, and the OAuth callback's close-popup page stays as it is. Replace
`TEST_CLIENT_SECRET` and `encode_mock_idtoken` only if you drop local mode.

## Checks

GitHub Actions (`.github/workflows/ci.yaml`) runs all of these on every pull
request and every push to `main`: the server's tox environments; the client's
lint, format, types, unit tests, and build; the Playwright browser tests; and a
Docker build with a start-up check. The `sample-dialapp-external check` job
passes only when all of them pass, so it is the one to require on `main`.

Each folder has its own checks; there is nothing to run at the repository root.

```sh
# client/ (the iframe panel)
pnpm lint:ci && pnpm format:ci && pnpm types:check && pnpm test:run
pnpm test:e2e                                   # browser tests

# server/ (the Python server): the tox environments
uvx tox                                         # tests, linter, typechecker, check_python_code_style
uvx tox -e apply_python_code_style              # reformat with yapf
```

The server's tox environments build their own virtual environments with
[tox-uv](https://github.com/tox-dev/tox-uv) on Python 3.14, from
`server/requirements.txt` and the groups in `server/pyproject.toml`, so they
need no `.venv`. The pieces are: pytest (`filterwarnings = error`), Ruff
(`select = ALL`), ty (all rules as errors), and yapf
(`server/.style.yapf`). In the `.venv` from [Install](#install), the same checks
run directly: `.venv/bin/pytest`, `.venv/bin/ruff check acme_dialpad_rightbar tests`,
`.venv/bin/ty check acme_dialpad_rightbar tests`, and
`.venv/bin/yapf --style .style.yapf --diff -r acme_dialpad_rightbar tests`.

`pnpm format:ci` also checks this README and `deployment/README.md`. `pnpm
test:e2e` starts the server (from `server/`, with its `.venv`, in local mode) and
Vite, then drives the dev host in Chromium with Playwright's clock. These tests
check this repository and the libraries in a real browser; they are not part of
the template, so delete `client/e2e/sdk/` (see its README) when you copy the
app. Install the browser once with `pnpm exec playwright install chromium`.

## The same iframe panel in plain JavaScript

This app's iframe panel is written in Vue 3, but nothing about the contract needs
a framework. The SDK's main entry (`@dialpad/dialapp-external-sdk`) is plain
TypeScript with no framework in it; the `/vue` entry the app also uses is a thin
binding of three things (turn the SDK's snapshot into a reactive value, provide
the SDK instance to every component, and let a component read both). This section
sketches the iframe panel without Vue; this repository doesn't build or run it.

### What does not change

- **The whole server.** The page, the contract endpoints, `POST /api/contact`, the
  OAuth screens, the session cookie, the CSP, and everything in
  [Security](#security-what-the-demo-shows) stay exactly as they are. The iframe
  panel only needs a `<div id="app">` and a script, which `pages.py` already
  renders.
- **The SDK calls.** `createRightbar`, `rightbar.state`, `rightbar.subscribe`,
  `rightbar.watch`, `authorize`, `disconnect`, `authHeaders`, `linkRecord`, and the
  rest.
- **The framework-free modules**: `contactApi.ts` (the request to
  `POST /api/contact`), `customPageAppData.ts` (validates the page data's `app`
  field), and `contacts.ts` (compares two contacts) import nothing from Vue.
  `client/src/api.ts` (adds the bearer header and turns a `401` into the "reload"
  notice) needs one small change: its `sessionExpired` flag is a Vue `ref`, so it
  becomes a plain variable plus a callback that re-renders (shown below).
- **The CSS.** `style.css` and the BEM classes (such as `acme-contact__label`)
  carry over; each component's `<style>` block becomes a plain `.css` file.
- **The bundler.** Vite still builds one entry, and the server still links it from
  Vite's manifest (`ENTRY` in `server/acme_dialpad_rightbar/assets.py` changes from
  `src/main.ts` to `src/main.js` if you rename it).

### What is replaced

| In the Vue app                                                                                    | In plain JavaScript                                                                   |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `main.ts`, `bootstrap.ts`                                                                         | One `main.js`: create the SDK instance, then render and subscribe                     |
| `App.vue`                                                                                         | `renderApp(state)`: the title, the reload notice, then the gate or the connected view |
| `ConnectGate.vue`                                                                                 | `renderConnectGate(connection)`                                                       |
| `ConnectedView.vue`, `UserCard.vue`, `CallCard.vue`, `DialpadApiCard.vue`, `DisconnectButton.vue` | One render function each, returning DOM nodes                                         |
| `AcmeContact.vue`                                                                                 | A small object that owns its own lookup state (see below)                             |
| `useRightbar()` and `rightbarPlugin`                                                              | `rightbar.state` and `rightbar.subscribe(...)` directly                               |
| Dialtone's Vue components (`DtButton`, `DtNotice`, `DtAvatar`)                                    | Dialtone's CSS (`@dialpad/dialtone/css`) and tokens on your own markup                |
| Vue's reactivity                                                                                  | You decide when to re-render: on every snapshot, or only for the part that changed    |

### The shape of it

The SDK gives you an immutable snapshot (`rightbar.state`) and calls you back with
the next one, so the simplest vanilla panel renders everything from the snapshot
each time:

```js
// main.js
import { createRightbar, RightbarError } from "@dialpad/dialapp-external-sdk";
import { initDialtoneTheme, setMode } from "@dialpad/dialtone/themes/config";
import dp from "@dialpad/dialtone/themes/dp";
import "@dialpad/dialtone/css";
import "./style.css";

// api.ts, with `sessionExpired` as a plain flag and a hook the 401 handler calls:
//   export let sessionExpired = false;
//   export function onSessionExpired(callback) { ... call it when a 401 sets the flag ... }
import { api, onSessionExpired, sessionExpired, useAuthHeaders } from "./api";

const root = document.getElementById("app");

async function start() {
  let rightbar;
  try {
    // Reads the page data, checks the page is framed by Dialpad, does the `init` handshake.
    rightbar = await createRightbar({ heightRoot: root, fetch: api });
  } catch (error) {
    if (!(error instanceof RightbarError)) throw error;
    root.textContent = "Open this panel from Dialpad."; // not_framed, bad_page_data, init_timeout...
    return;
  }
  useAuthHeaders(() => rightbar.authHeaders());

  // Follow Dialpad's light and dark mode.
  initDialtoneTheme(dp, rightbar.state.theme.mode);
  rightbar.watch(
    (state) => state.theme.mode,
    (mode) => setMode(mode),
  );

  const contact = createContactSection(rightbar); // owns its own lookups, see below
  const render = (state) =>
    root.replaceChildren(...renderApp(state, rightbar, contact));
  render(rightbar.state);
  rightbar.subscribe((next) => render(next)); // every new snapshot from the SDK
  contact.subscribe(() => render(rightbar.state)); // a contact lookup finished
  onSessionExpired(() => render(rightbar.state)); // a request got a 401
}

await start();
```

Rendering is ordinary DOM code. Build elements and set `textContent`; never put
CRM or Dialpad data into `innerHTML` (a contact name can contain markup), which is
the same reason the Vue templates only ever interpolate text:

```js
// A tiny element helper: h('p', { class: 'acme-muted' }, 'No active call.')
function h(tag, props = {}, ...children) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(props)) {
    if (name.startsWith("on"))
      element.addEventListener(name.slice(2).toLowerCase(), value);
    else if (value !== false && value != null)
      element.setAttribute(name, value === true ? "" : value);
  }
  element.append(
    ...children.flat().filter((child) => child != null && child !== false),
  );
  return element;
}

function renderApp(state, rightbar, contact) {
  return [
    h("h1", { class: "acme-title" }, "Acme for Dialpad (demo)"),
    sessionExpired &&
      h(
        "div",
        { role: "alert", class: "acme-notice" },
        "Reload the panel to keep going.",
      ),
    state.connection.connected
      ? renderConnectedView(state, rightbar, contact)
      : renderConnectGate(state.connection, rightbar),
  ];
}

const ERROR_COPY = {
  timeout: "Acme didn't respond in time.",
  network: "We couldn't reach Acme. Check your connection.",
  request_failed: "Something went wrong while checking your Acme connection.",
};

function renderConnectGate(connection, rightbar) {
  const code = connection.error?.code;
  return h(
    "section",
    { class: "acme-gate", "data-testid": "connect-gate" },
    h("p", {}, "Connect your Acme account to see your records here."),
    code && h("div", { role: "alert" }, ERROR_COPY[code]),
    connection.pending &&
      h(
        "p",
        { role: "status" },
        "Waiting for you to finish connecting in the Acme window...",
      ),
    h(
      "button",
      {
        type: "button",
        class: "d-btn d-btn--primary", // Dialtone's CSS on your own markup
        disabled: connection.pending,
        onClick: () => rightbar.authorize(), // opens the authorize URL, then the SDK polls
      },
      code ? "Try again" : "Connect",
    ),
  );
}
```

Replacing all the children on every snapshot is fine for a panel this small, but it
drops focus, scroll position, and text typed into an input. If that matters, either
render only the part whose state changed (`rightbar.watch((s) => s.call, ...)`
re-runs only when the call changes, because unchanged parts of the snapshot keep
their references) or use a tiny DOM-diffing library such as `lit-html` or
`morphdom` for the render step.

### The contact section

`AcmeContact.vue` is the one component with state of its own: it asks the server for
the CRM's view of whichever contact is open, shows loading and failure, and must
ignore a late answer for an earlier contact. Vanilla, that is a watcher and a
counter, the same as the `watch` and `lookup` counter in the Vue file:

```js
import { fetchAcmeFields } from "./contactApi";

function createContactSection(rightbar) {
  const view = { status: "idle", fields: [] };
  let lookup = 0;
  let onChange = () => {};

  // Runs now and whenever `state.contact` changes (a new contact object), not on other changes.
  rightbar.watch(
    (state) => state.contact,
    async (contact) => {
      lookup += 1;
      const mine = lookup;
      view.fields = [];
      view.status = contact ? "loading" : "idle";
      onChange();
      if (!contact) return;
      try {
        const fields = await fetchAcmeFields(contact);
        if (mine === lookup) Object.assign(view, { status: "ready", fields });
      } catch {
        if (mine === lookup) view.status = "failed";
      }
      onChange();
    },
  );

  return {
    view,
    // main.js passes its `render` here, so a finished lookup re-renders the panel.
    subscribe: (callback) => {
      onChange = callback;
    },
  };
}
```

A real app also calls `rightbar.linkRecord(...)` here once the server has
returned a mapped CRM record (see
[The contact lookup](#the-contact-lookup-demo-vs-a-real-app)).

### Tests and build

The SDK's testing entry (`@dialpad/dialapp-external-sdk/testing`) is not Vue
specific: `createMockHost()`, `makePageData()`, and `host.sendContact(...)` give a
fake Dialpad, and `host.createRightbar(...)` returns a real `Rightbar` to render
from. Only the Vue helper `mountWithRightbar` (from `/vue/testing`) goes away: mount
by calling your `render` into a jsdom element. The browser tests (Playwright
against the dev host) do not change at all, since they only look at the DOM through
`data-testid` and roles.

What you give up is the framework: no components with scoped state, no templates to
check, and no reactivity, so keeping the DOM in step with the snapshot is your code. What
you gain is a much smaller bundle: this app's is about 116 kB gzipped (Vue, Dialtone's
Vue components, and the SDK).

## Adapt the iframe panel to React

Replace only the Vue code with React. The server does not change: it can be this
app's Python server or any server you already have. Nothing here is built or run in
this repository; the snippets are sketches.

Everything under "What does not change" in the plain JavaScript section applies:
the server, the SDK calls, the framework-free modules (with `sessionExpired` as a
plain flag, as there), and the BEM CSS.
Dialtone's Vue components do not apply, so use Dialtone's CSS and design tokens on
your own React components.

**Start the SDK outside React**, before the first render, as the Vue app does in
`bootstrap.ts`. If you start it inside a `useEffect`, React's Strict Mode (on by
default in development) mounts, unmounts and remounts the component, which
creates two SDK instances and runs the `init` handshake twice.

```tsx
// main.tsx
import { createRightbar, RightbarError } from "@dialpad/dialapp-external-sdk";
import { initDialtoneTheme, setMode } from "@dialpad/dialtone/themes/config";
import dp from "@dialpad/dialtone/themes/dp";
import "@dialpad/dialtone/css";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { RightbarProvider } from "./rightbar";
import { api, useAuthHeaders } from "./api";

const root = document.getElementById("app")!;
try {
  const rightbar = await createRightbar({ heightRoot: root, fetch: api });
  useAuthHeaders(() => rightbar.authHeaders());
  // Follow Dialpad's light and dark mode. Dialtone's theme module is plain
  // JavaScript, so it works the same without Vue.
  initDialtoneTheme(dp, rightbar.state.theme.mode);
  rightbar.watch(
    (state) => state.theme.mode,
    (mode) => setMode(mode),
  );
  createRoot(root).render(
    <RightbarProvider rightbar={rightbar}>
      <App />
    </RightbarProvider>,
  );
} catch (error) {
  if (!(error instanceof RightbarError)) throw error;
  root.textContent = "Open this panel from Dialpad.";
}
```

**The binding is about 15 lines.** The SDK's snapshot is immutable, replaced
on every change, and unchanged parts keep their references. That is exactly what
`useSyncExternalStore` expects, so a hook over `subscribe` and `state` replaces
`useRightbar()` and `rightbarPlugin`:

```tsx
// rightbar.tsx
import type { Rightbar, RightbarState } from "@dialpad/dialapp-external-sdk";
import {
  createContext,
  useContext,
  useSyncExternalStore,
  type ReactNode,
} from "react";

const RightbarContext = createContext<Rightbar | null>(null);

export function RightbarProvider({
  rightbar,
  children,
}: {
  rightbar: Rightbar;
  children: ReactNode;
}) {
  return (
    <RightbarContext.Provider value={rightbar}>
      {children}
    </RightbarContext.Provider>
  );
}

/** The SDK instance, for actions: `authorize()`, `disconnect()`, `linkRecord(...)`. */
export function useRightbar(): Rightbar {
  const rightbar = useContext(RightbarContext);
  if (!rightbar) throw new Error("Wrap the app in <RightbarProvider>");
  return rightbar;
}

/** A selected part of the snapshot; the component re-renders only when that part changes. */
export function useRightbarState<T>(select: (state: RightbarState) => T): T {
  const rightbar = useRightbar();
  return useSyncExternalStore(
    (onChange) => rightbar.subscribe(() => onChange()),
    () => select(rightbar.state),
  );
}
```

`useRightbarState((s) => s.connection)` is the React form of
`computed(() => state.value.connection)`. Pick selectors that return a part of the
snapshot as it is (`s.call`, `s.connection`), not a freshly built object, or the
component re-renders on every change.

**The one component with state of its own** is the contact section. With hooks
it is an effect with an "ignore" flag, which is the React form of the `lookup`
counter in `AcmeContact.vue`:

```tsx
function AcmeContact({ contact }: { contact: Contact | null }) {
  const [view, setView] = useState<{
    status: "idle" | "loading" | "ready" | "failed";
    fields: AcmeField[];
  }>({ status: "idle", fields: [] });
  useEffect(() => {
    if (!contact) return setView({ status: "idle", fields: [] });
    let stale = false; // set by the cleanup when the contact changes or the component unmounts
    setView({ status: "loading", fields: [] });
    fetchAcmeFields(contact).then(
      (fields) => !stale && setView({ status: "ready", fields }),
      () => !stale && setView({ status: "failed", fields: [] }),
    );
    return () => {
      stale = true;
    };
  }, [contact]);
  // ...render view.status and view.fields as AcmeContact.vue does
}
```

Everything else maps one to one: `App.vue` to `App`, `ConnectGate.vue` to
`ConnectGate` (reading `useRightbarState((s) => s.connection)` and calling
`useRightbar().authorize()`), the cards to components, and `sessionExpired` (a Vue
`ref`) to a small store or context read through `useSyncExternalStore`. Tests use
React Testing Library with the SDK's mock host, and the Playwright tests do not
change. Build with `@vitejs/plugin-react`, and point the server's `ENTRY`
(`server/acme_dialpad_rightbar/assets.py`) and `rollupOptions.input` in
`vite.config.ts` at `src/main.tsx`.
