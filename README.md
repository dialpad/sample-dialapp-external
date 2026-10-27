# Acme for Dialpad: A partner rightbar reference app

A small, runnable Dialpad rightbar app, for partners who build one. Run it, read
the guide to see how each part works, and copy it to start your own.

## In brief

- **What it is.** "Acme for Dialpad" is a working rightbar app: a panel that
  Dialpad shows beside a contact or call, connected to a fictional CRM, Acme CRM.
  The same shape works for other integrations, such as a panel that shows a
  call's AI transcript or summary.
- **The panel** uses Dialpad's SDK, `@dialpad/dialapp-external-sdk`, for
  everything on the Dialpad side: the handshake, one state snapshot of the user,
  contact, call, theme, and CRM connection, OAuth Connect and Disconnect, linking
  CRM records, toasts, and a mock Dialpad for tests. This app uses Vue and
  Dialtone; plain JavaScript and React work too.
- **Your server** can be in any language. It decodes the idtoken that Dialpad
  adds to the page URL, serves the page with its page data, answers
  `GET /dialpad/ext-connection` and `POST /dialpad/ext-disconnect`, and checks a
  bearer access token on every request from the panel.
  [`contract/openapi.json`](contract/openapi.json) describes all of it, and the
  Python server here is one implementation.
- **The idtoken's API key** lets your server call Dialpad's public API and set
  up webhooks for Dialpad's events, such as a call's AI transcript. It stays on
  your server, and a real app stores it.
  [developers.dialpad.com](https://developers.dialpad.com/) documents the API
  and the events.
- **The demo has no database or real CRM**, so it fakes those parts. The guide
  says what to replace.
- **Security** comes from a content security policy that lets only Dialpad frame
  the panel, a fresh nonce per response, escaped page data, and no secrets in
  logs.
- **Run it** locally with a dev page that stands in for Dialpad, or in Dialpad
  with an OAuth app that Dialpad sets up. Design the panel for 250 to 414 pixels
  wide.
- **Test it** with the SDK's mock Dialpad in unit tests and Playwright in a real
  browser. CI runs every check.

## Try it

You need Node 24, Corepack, and Python 3.14.

```sh
corepack enable
(cd client && pnpm install)
(cd server && python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt --group dev)

cd server && LOCAL_MODE=1 .venv/bin/python -m acme_dialpad_rightbar   # terminal 1
cd client && pnpm dev                                                  # terminal 2
```

Open <http://localhost:5173/dev-host/>, click **Connect**, then click
**Authorize** in the popup. [Chapter 2](guide/02-run-the-demo.md) explains what
you see.

## The guide

Read chapter 1 for the whole picture, then the chapters for the parts you build.
A panel that doesn't show a CRM record skips chapter 7
([which chapters you need](guide/01-the-big-picture.md#which-chapters-you-need)).

| Chapter                                                                   | What you learn                                                                          |
| ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| [1. The big picture](guide/01-the-big-picture.md)                         | The pieces, the life of a panel, key terms, the four secrets, and the contract          |
| [2. Run the demo](guide/02-run-the-demo.md)                               | Install, upgrade the SDK, run locally with the dev host, and run in Dialpad             |
| [3. Load the panel page](guide/03-load-the-panel-page.md)                 | Decode the idtoken, start a session, and render the page and its page data              |
| [4. Build the panel with the SDK](guide/04-build-the-panel.md)            | Start the SDK, render from its state, design for the panel's size, and use Dialpad's UI |
| [5. Authenticate the panel's requests](guide/05-authenticate-requests.md) | The bearer access token, the panel's fetch wrapper, and your own routes                 |
| [6. Connect the user to your service](guide/06-connect-to-the-crm.md)     | Connect through OAuth, the callback, and Disconnect                                     |
| [7. Show the CRM record](guide/07-show-the-crm-record.md)                 | Map a Dialpad contact to a CRM record, link it in Dialpad, and the panel menu           |
| [8. Call Dialpad's API and receive events](guide/08-call-dialpad.md)      | Use the API key, and verify Dialpad's webhook events                                    |
| [9. Security checklist](guide/09-security-checklist.md)                   | Every defense in one place, the content security policy, and keeping logs clean         |
| [10. Test your app](guide/10-test-your-app.md)                            | The SDK's mock Dialpad, browser tests, and the checks CI runs                           |
| [11. Turn the demo into your app](guide/11-from-demo-to-your-app.md)      | What the demo fakes and why, and what to replace                                        |
| [12. Build the panel in plain JavaScript](guide/12-plain-javascript.md)   | The same panel without a framework                                                      |
| [13. Build the panel in React](guide/13-react.md)                         | The same panel in React                                                                 |
| [Reference](guide/reference.md)                                           | The server's environment variables, this app's endpoints, and the SDK at a glance       |

## The repository

| Folder        | What it is                                                                                                                   |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `client/`     | The panel: Vite, Vue 3, TypeScript, and Dialtone 10. A `pnpm` project                                                        |
| `server/`     | The Python server, `acme_dialpad_rightbar/`: Sanic on Python 3.14, with its tests. One file per endpoint, under `endpoints/` |
| `contract/`   | `openapi.json`, the contract between Dialpad, your server, and the SDK                                                       |
| `deployment/` | The Dockerfile, and how to run the app on Cloud Run                                                                          |
| `guide/`      | This guide                                                                                                                   |
