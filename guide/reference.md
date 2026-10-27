# Reference

Look things up here. The [chapters](../README.md#the-guide) explain them.

## The server's environment variables

The server reads these environment variables; the panel reads none. Nothing
loads a `.env` file, so export them in your shell or set them in your host.

| Variable                | Required                | Purpose                                                                                                                                                                                                       |
| ----------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DIALPAD_CLIENT_SECRET` | Yes, outside local mode | Your OAuth app's client secret, for decoding the idtoken. At least 48 characters (Dialpad's are 50). Local mode defaults to a test secret (`TEST_CLIENT_SECRET` in `server/acme_dialpad_rightbar/idtoken.py`) |
| `DIALPAD_ORIGIN`        | Yes, outside local mode | `https://dialpad.com`, used in the page's `frame-ancestors`. Must be a bare origin (scheme, host, and optional port; no trailing slash or path), checked at startup. Local mode defaults to `VITE_ORIGIN`     |
| `APP_SECRET`            | Yes, outside local mode | Demo only. A random secret that signs the OAuth `state` and the storage cookie ([chapter 11](11-from-demo-to-your-app.md#the-storage-cookie)). Local mode defaults to a fixed development value               |
| `BASE_URL`              | Yes, outside local mode | The server's public HTTPS URL, without a trailing slash, for building the authorize and callback URLs. Local mode defaults to `http://localhost:8000`                                                         |
| `HOST`                  | No                      | The address to listen on. Defaults to `127.0.0.1`, this machine only; a container sets `0.0.0.0`                                                                                                              |
| `LOCAL_MODE`            | No                      | `1` turns on local mode: the defaults above, the dev host's route, and the Vite dev server in the CSP ([chapter 2](02-run-the-demo.md#run-it-locally))                                                        |
| `VITE_ORIGIN`           | No, local mode only     | The Vite dev server's origin. Defaults to `http://localhost:5173`                                                                                                                                             |
| `DIST_DIR`              | No                      | Where `pnpm build` in `client/` wrote the panel. Defaults to `../client/dist`, relative to `server/`; the container sets `dist`                                                                               |
| `PORT`                  | No                      | The port to listen on. If unset, the port in `BASE_URL`, else `8000`. A container host sets it                                                                                                                |

Keep `DIALPAD_CLIENT_SECRET` and `APP_SECRET` out of source control. On Cloud Run,
Secret Manager holds them and passes them in as environment variables
([`deployment/README.md`](../deployment/README.md)).

## This app's endpoints

Each endpoint is one file under `server/acme_dialpad_rightbar/`: the contract's
in `endpoints/dialpad/`, the app's own in `endpoints/app/`, the CRM record's in
`crm/`, and the demo's in `demo/endpoints/`
([chapter 11](11-from-demo-to-your-app.md#what-to-keep-replace-and-delete)).
Each folder's `__init__.py` lists them.

| Endpoint                       | File                                  | What it does                                                                                                                                               |
| ------------------------------ | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /`                        | `endpoints/dialpad/page.py`           | The panel page ([chapter 3](03-load-the-panel-page.md)). `401` HTML when the idtoken doesn't decode                                                        |
| `GET /dialpad/ext-connection`  | `endpoints/dialpad/ext_connection.py` | The user's connection to the CRM ([chapter 6](06-connect-to-the-crm.md)). Collects a finished Connect, and builds a fresh authorize URL                    |
| `POST /dialpad/ext-disconnect` | `endpoints/dialpad/ext_disconnect.py` | Turns the connection off and answers `204` with no body                                                                                                    |
| `GET /oauth/callback`          | `endpoints/app/oauth_callback.py`     | The OAuth redirect URI. Checks `state` and closes the popup                                                                                                |
| `POST /api/contact`            | `crm/contact.py`                      | The app's own route: the CRM's view of a Dialpad contact and the record to link ([chapter 7](07-show-the-crm-record.md)). Needs a connected user           |
| `GET /records/<contact id>`    | `crm/fake_record.py`                  | Demo only. A page labelled fake that stands in for the CRM's page for a record, showing the contact ID. The panel links it, so Dialpad's ↗ button opens it |
| `GET /oauth/fake-authorize`    | `demo/endpoints/fake_authorize.py`    | Demo only. A page labelled fake, with an **Authorize** button that goes to the callback                                                                    |
| `GET /healthz`                 | `demo/endpoints/healthz.py`           | Answers `ok`. Used by the browser tests                                                                                                                    |
| `GET /dev/frame-url`           | `demo/endpoints/dev_frame_url.py`     | Local mode only. A page URL with a mock idtoken, for the dev host                                                                                          |

The contract routes and `/api/contact` need the bearer access token ([chapter 5](05-authenticate-requests.md)).

## The SDK at a glance

| SDK                                                                                                           | What it's for                                                        | Explained in                                                       |
| ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `createRightbar({ heightRoot, fetch, onDisconnect })`, `RightbarError`                                        | Start the SDK                                                        | [Chapter 4](04-build-the-panel.md#start-the-sdk)                   |
| `state`, `subscribe()`, `watch()`, `rightbarPlugin`, `useRightbar()`                                          | Render from Dialpad's state                                          | [Chapter 4](04-build-the-panel.md#render-from-the-state)           |
| `showToast()`, `setMenu()`, `on('menuSelect')`, `linkRecord()`, `showRefreshButton()`, `on('refreshContact')` | Toasts, and the panel header's menu, View button, and refresh button | [Chapter 4](04-build-the-panel.md#use-dialpads-ui)                 |
| `app`                                                                                                         | Your own data from the page                                          | [Chapter 4](04-build-the-panel.md#pass-your-own-data-to-the-panel) |
| `destroy()`                                                                                                   | Shut the panel down                                                  | [Chapter 4](04-build-the-panel.md#start-the-sdk)                   |
| `authHeaders()`                                                                                               | Authenticate requests to your server                                 | [Chapter 5](05-authenticate-requests.md#in-the-panel)              |
| `state.connection`, `authorize()`, `refresh()`, `disconnect()`                                                | Connect and disconnect                                               | [Chapter 6](06-connect-to-the-crm.md)                              |
| `linkRecord()` with a CRM record, `screenPop()`                                                               | Link the CRM record, Rematch, screen pops                            | [Chapter 7](07-show-the-crm-record.md#link-the-record-in-dialpad)  |
| `/testing`, `/testing/setup`, `/vue/testing`                                                                  | Test your panel                                                      | [Chapter 10](10-test-your-app.md)                                  |

---

**Previous:** [13. Build the panel in React](13-react.md) ·
[Contents](../README.md#the-guide)
