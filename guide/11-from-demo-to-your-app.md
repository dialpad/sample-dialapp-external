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
| [The CRM record](07-show-the-crm-record.md)            | Prefixes every text field with `Acme `                                                                     | Maps the contact to a CRM record, fetches it with the CRM token, and calls `linkRecord`  |
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

## What to replace

| Here                                                                                             | With                                                                                                              |
| ------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| `/oauth/fake-authorize`                                                                          | Your CRM's authorize URL; delete `server/acme_dialpad_rightbar/fake_oauth.py`                                     |
| `/oauth/callback`                                                                                | Keep the route, its `state` check, and the close-popup page; make it exchange the `code` and store the CRM tokens |
| `server/acme_dialpad_rightbar/stores.py`                                                         | Nothing: store the CRM tokens in the callback and answer from them                                                |
| The session cookie (`database.py`, `signing.py`)                                                 | Your stored CRM tokens and a real session table, or expiring tokens                                               |
| `server/acme_dialpad_rightbar/endpoints/app/contact.py`, `client/src/components/AcmeContact.vue` | Your contact mapping and CRM record ([chapter 7](07-show-the-crm-record.md))                                      |
| `client/src/components/ConnectGate.vue`                                                          | Copy it and change the text; it renders the SDK's `connection`                                                    |
| `ACCOUNT_NAME` in `server/acme_dialpad_rightbar/context.py`                                      | Your CRM's account name                                                                                           |
| `server/acme_dialpad_rightbar/dialpad_api.py`, `DialpadApiCard.vue`                              | Delete both, and the call in `endpoints/dialpad/page.py`. Store the API key and call Dialpad when you need to     |
| `client/e2e/sdk/`                                                                                | Delete it, with `playwright.config.ts`, the `test:e2e` script, and `@playwright/test`, or adapt it to your app    |

Keep `idtoken.py` (the decoder), `pages.py` (the page, close-popup, and error
pages, with their security headers), and `contract.py` (the models the SDK
reads). They're the server half of the contract. Keep `TEST_CLIENT_SECRET` and
`encode_mock_idtoken` if you keep local mode.

To run your app as a container, see
[`deployment/README.md`](../deployment/README.md).

---

**Previous:** [10. Test your app](10-test-your-app.md) ·
**Next:** [12. Build the panel in plain JavaScript](12-plain-javascript.md) ·
[Contents](../README.md#the-guide)
