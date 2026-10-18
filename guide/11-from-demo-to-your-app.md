# 11. Turn the demo into your app

The demo has no database and no real CRM, so it fakes the parts that need them.
This chapter shows what it does instead, why, and what to replace when you copy
it.

## The demo and a real app, flow by flow

| Flow                                                   | This demo                                                                                                  | A real app                                                                               |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| [Page load](03-load-the-panel-page.md)                 | Embeds a random access token and sets a signed cookie that holds it; uses the API key once for a demo call | Stores the API key and creates a session row; no cookie                                  |
| [Authenticating requests](05-authenticate-requests.md) | The bearer token must equal the token in the cookie                                                        | Looks the bearer token up in a session table                                             |
| [Connect](06-connect-to-the-crm.md)                    | A fake authorize page; the callback leaves a note in memory, and the cookie records "connected"            | The CRM's authorize page; the callback exchanges the code for CRM tokens and stores them |
| [Disconnect](06-connect-to-the-crm.md#disconnect)      | Turns "connected" off in the cookie, in that browser only                                                  | Revokes and deletes the user's CRM tokens                                                |
| [The CRM record](07-show-the-crm-record.md)            | Prefixes every text field with `Acme `, and links a fake record page                                       | Maps the contact to a CRM record, fetches it with the CRM token, and calls `linkRecord`  |
| [Calling Dialpad](08-call-dialpad.md)                  | One call while rendering the page                                                                          | Calls Dialpad's API whenever needed, with the stored key                                 |
| [Webhooks](08-call-dialpad.md#receive-dialpads-events) | None                                                                                                       | A receiver that verifies each signed event                                               |

## The session cookie

Without a database, the demo keeps what it must remember in a cookie it signs:
the user's access token and whether they're connected. Signing is what lets the
server trust the cookie when it comes back.

- **Every request needs both** the bearer token and the cookie, holding the same
  token. Browsers attach the cookie to requests from any site, but only code
  that has the page data can add the header, so requiring both stops cross-site
  request forgery. This is a "double submit".
- **The cookie is** `__Host-` prefixed, `Secure`, `HttpOnly`, `SameSite=None`
  (required in a third-party iframe), and `Partitioned` (kept separately for each
  embedding site), and it lasts 30 days. Its value is signed with HMAC-SHA256:
  readable, but nobody without the secret can forge or change it.
- **`APP_SECRET`** is the demo's signing secret, for the cookie and the OAuth
  `state`. Dialpad and the SDK don't ask for it. Each signed value carries a
  `kind`, so a value signed for one purpose is never accepted as another.
- **The limits:** a session can't be revoked early, it lives in one browser for
  30 days, a browser that refuses the cookie can't use the panel, and changing
  `APP_SECRET` signs everyone out.

A real app keeps this on the server instead. It creates a session row with a
random token on each page load, keeps the OAuth `state` in a store with a short
expiry, and treats "connected" as "CRM tokens exist". A secret of your own is
still useful there, for encrypting what you store and deriving webhook secrets.

## OAuth results in memory

The OAuth callback runs in the popup, but the session cookie belongs to the
panel (it's `Partitioned`), so the callback can't update it. The only thing both
know is the Dialpad user. So the callback leaves a note in server memory, "this
user finished connecting", kept for 5 minutes and collected once, and the panel's
next check picks it up and rewrites the cookie. The note is `OAuthResults` in
`server/acme_dialpad_rightbar/stores.py`.

This only exists because there's no real CRM. A real callback stores the CRM
tokens in your database, and `ext-connection` reads them from there, on any
instance and after any restart.

## The demo call to Dialpad's API

The panel doesn't need it; it's there to show how the API key is used. While it
renders the page, the server calls `GET {DIALPAD_ORIGIN}/api/v2/users/me` with
the idtoken's API key, using
[`python-dialpad`](https://pypi.org/project/python-dialpad/), in
`server/acme_dialpad_rightbar/dialpad_api.py`. The panel shows the result in a
"From Dialpad's API" card.

- The call has a 3-second timeout and no retry. If it fails, the page renders
  anyway and the card says "Dialpad API unavailable".
- Local mode makes no call, because the mock idtoken's key isn't real.
- The server uses the key for this one call and drops it. It never puts the key
  in the page, logs it, or returns it.

A real app stores the key and calls Dialpad whenever it needs to
([chapter 8](08-call-dialpad.md)).

## What the demo doesn't do

- It doesn't store the API key, or call Dialpad outside the page request.
- Its OAuth is fake: there are no CRM tokens and no refresh.
- It has no webhook receiver, and no replay protection for the idtoken beyond
  keeping it out of logs, caches, and referrers.

## What to keep, change, and delete

These two tables cover every source file, and they're the complete list of what
the demo fakes. A fake they don't list is a bug in the tables.

The server's files are in `server/acme_dialpad_rightbar/`:

| File                                                       | Do     | What                                                                                                                                        |
| ---------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `idtoken.py`                                               | Keep   | The idtoken decoder. `TEST_CLIENT_SECRET` and `encode_mock_idtoken` are for local mode                                                      |
| `pages.py`                                                 | Keep   | The page, close-popup, and error pages, with their security headers and escaping                                                            |
| `contract.py`                                              | Keep   | The models the SDK reads, the server half of the [contract](01-the-big-picture.md#the-contract)                                             |
| `app.py`, `__main__.py`, `assets.py`, `responses.py`       | Keep   | Remove the routes you delete from `endpoints/`                                                                                              |
| `settings.py`                                              | Change | Point `authorize_url` at your CRM's authorize URL, delete `record_url`, and drop `APP_SECRET` if nothing signs with it                      |
| `context.py`                                               | Change | Replace the session cookie (`state_from_cookie`, `save_state`, `state_for`) with your session table. Set the names and scopes to your CRM's |
| `database.py`                                              | Delete | It plays a database row in a cookie. Use your database ([chapter 3](03-load-the-panel-page.md#start-a-session))                             |
| `signing.py`                                               | Change | Delete the cookie half. Keep the signed OAuth `state`, or keep `state` in a store with a short expiry                                       |
| `stores.py`                                                | Delete | Store the CRM tokens in the callback and answer from them ([OAuth results in memory](#oauth-results-in-memory))                             |
| `fake_oauth.py`, `endpoints/app/oauth_fake_authorize.py`   | Delete | Your CRM's authorize page replaces them                                                                                                     |
| `dialpad_api.py`                                           | Delete | Store the API key and call Dialpad when you need to ([chapter 8](08-call-dialpad.md))                                                       |
| `fake_record.py`, `endpoints/app/fake_record.py`           | Delete | It stands in for the CRM's page for a record. Link the CRM's own page ([chapter 7](07-show-the-crm-record.md#link-the-record-in-dialpad))   |
| `endpoints/dialpad/page.py`                                | Change | Store the API key, create a session row, and drop the demo call to Dialpad's API                                                            |
| `endpoints/dialpad/ext_connection.py`, `ext_disconnect.py` | Change | Answer from the stored CRM tokens; Disconnect revokes and deletes them ([chapter 6](06-connect-to-the-crm.md))                              |
| `endpoints/app/oauth_callback.py`                          | Change | Keep the `state` check and the close-popup page. Exchange the `code` and store the CRM tokens                                               |
| `endpoints/app/contact.py`                                 | Change | Your contact mapping, and the CRM record with its URL in the CRM ([chapter 7](07-show-the-crm-record.md))                                   |
| `endpoints/app/dev_frame_url.py`                           | Keep   | Only if you keep local mode                                                                                                                 |
| `endpoints/app/healthz.py`                                 | Delete | Only the browser tests use it                                                                                                               |
| `server/tests/`                                            | Change | Keep the tests of the files you keep, and test your own                                                                                     |

The client's files are in `client/`:

| File                                                                                     | Do     | What                                                                                                                                                                                             |
| ---------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `src/main.ts`, `src/bootstrap.ts`, `src/api.ts`, `src/App.vue`, `src/BootstrapError.vue` | Keep   | Starting the SDK, the panel menu and refresh button, the fetch wrapper, and the root. Change "Acme" in the text, and add your menu items ([chapter 7](07-show-the-crm-record.md#the-panel-menu)) |
| `src/style.css`, `src/contacts.ts`, `src/vue-shim.d.ts`                                  | Keep   | The panel's styles, comparing Dialpad contacts, and a type shim for ESLint                                                                                                                       |
| `src/components/ConnectGate.vue`, `DisconnectButton.vue`                                 | Change | Change the text. They render the SDK's `connection`                                                                                                                                              |
| `src/components/ConnectedView.vue`                                                       | Change | What your panel shows once connected                                                                                                                                                             |
| `src/components/AcmeContact.vue`, `src/contactApi.ts`                                    | Change | Your CRM record ([chapter 7](07-show-the-crm-record.md))                                                                                                                                         |
| `src/components/UserCard.vue`, `CallCard.vue`                                            | Keep   | Examples of the SDK's user and call. Delete them if your panel doesn't show these                                                                                                                |
| `src/components/DialpadApiCard.vue`                                                      | Delete | It shows the demo call to Dialpad's API                                                                                                                                                          |
| `src/customPageAppData.ts`                                                               | Change | Check your own [page data](04-build-the-panel.md#pass-your-own-data-to-the-panel), or delete it if you have none                                                                                 |
| `src/App.test.ts`, `src/contacts.test.ts`                                                | Change | Adapt them to your panel ([chapter 10](10-test-your-app.md))                                                                                                                                     |
| `dev-host/`                                                                              | Keep   | Only if you keep local mode                                                                                                                                                                      |
| `e2e/sdk/`, `playwright.config.ts`                                                       | Delete | They test this repository. Also remove the `test:e2e` script and `@playwright/test`, or adapt the tests                                                                                          |
| `scripts/vendor.mjs`, `scripts/guide-images.mjs`                                         | Delete | Dialpad's tooling for this repository. Also remove their scripts in `package.json`                                                                                                               |
| `vendor/`                                                                                | Keep   | The SDK tarball ([chapter 2](02-run-the-demo.md#upgrade-the-sdk))                                                                                                                                |

To run your app as a container, see
[`deployment/README.md`](../deployment/README.md).

---

**Previous:** [10. Test your app](10-test-your-app.md) ·
**Next:** [12. Build the panel in plain JavaScript](12-plain-javascript.md) ·
[Contents](../README.md#the-guide)
