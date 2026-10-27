# 9. Security checklist

A rightbar panel is a web page that Dialpad frames, opened with a long-lived
credential in its URL, that then talks to your server. The earlier chapters
explain each defense where it comes up. This chapter collects them, and covers
the two that apply everywhere: the content security policy and keeping secrets
out of logs.

## The checklist

| Risk                                        | Defense                                                                                                   | Where                                                            |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| A forged or tampered idtoken                | Accept only `dir` with `A192CBC-HS384`, and `HS256`; a failure at any step is a `401`                     | [Chapter 3](03-load-the-panel-page.md#decode-the-idtoken)        |
| The idtoken leaking from its URL            | `Referrer-Policy: no-referrer`, `Cache-Control: no-store`, and no query strings in logs                   | [Chapter 3](03-load-the-panel-page.md#decode-the-idtoken), below |
| The API key reaching the browser            | Keep it on the server, encrypted; the page data has no field for it                                       | [Chapter 3](03-load-the-panel-page.md#keep-the-api-key)          |
| A script injected through the page data     | Escape `<`, `>`, `&`, and `'` in the JSON                                                                 | [Chapter 3](03-load-the-panel-page.md#escape-the-page-data)      |
| A request from someone other than the panel | A bearer access token on every request, checked against the stored tokens                                 | [Chapter 5](05-authenticate-requests.md)                         |
| The access token being stolen               | Keep it in memory, not `localStorage`, behind a strict CSP                                                | [Chapter 5](05-authenticate-requests.md#in-the-panel), below     |
| A callback connecting the wrong user        | A random, single-use OAuth `state` tied to the Dialpad user, and PKCE                                     | [Chapter 6](06-connect-to-the-crm.md#on-your-server)             |
| The popup talking to the wrong window       | `postMessage` to the Dialpad origin, never `'*'`                                                          | [Chapter 6](06-connect-to-the-crm.md#on-your-server)             |
| CRM tokens leaking                          | Store them encrypted; never put them in a page, a response, or a log                                      | [Chapter 6](06-connect-to-the-crm.md#on-your-server)             |
| Forged webhook events                       | A secret per webhook, `HS256` only, and the signature checked before anything else                        | [Chapter 8](08-call-dialpad.md#handle-an-event)                  |
| The panel opened outside Dialpad            | The SDK refuses to start unless framed (`not_framed`), and talks only to the page data's `dialpad_origin` | [Chapter 4](04-build-the-panel.md#start-the-sdk)                 |
| Another site framing your panel             | `frame-ancestors` set to the Dialpad origin                                                               | Below                                                            |
| Injected HTML                               | `html.escape` (or your framework's escaping) on every value; text, not HTML, in the panel                 | Below                                                            |

## The content security policy

Every page your server renders carries a `Content-Security-Policy`, plus
`Referrer-Policy: no-referrer`, `Cache-Control: no-store`, and
`X-Content-Type-Options: nosniff`. This app uses these policies:

| Page                           | `Content-Security-Policy`                                                                                           |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| The panel, `GET /`             | `frame-ancestors <DIALPAD_ORIGIN>; script-src 'self' 'nonce-…' <asset origins>; object-src 'none'; base-uri 'none'` |
| The close-popup page           | `default-src 'none'; script-src 'nonce-…'; style-src 'nonce-…'; frame-ancestors 'none'; base-uri 'none'`            |
| The error page                 | `default-src 'none'; style-src 'nonce-…'; frame-ancestors <DIALPAD_ORIGIN>; base-uri 'none'`                        |
| The fake authorize page (demo) | `default-src 'none'; style-src 'nonce-…'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`              |

- **`frame-ancestors`** lets only Dialpad embed the panel, so other sites can't
  frame it to trick users (clickjacking). The popup pages can't be framed at all.
- **`script-src 'self' 'nonce-…'`**, with no `'unsafe-inline'` or
  `'unsafe-eval'`, runs only your own script files. An inline script that an XSS
  bug injects doesn't run, which protects the access token in memory.
- **The nonce** is a fresh random value for each response, written into the header
  and onto each inline element you allow. Never reuse one.
- **`object-src 'none'` and `base-uri 'none'`** block plugins, and a `<base>` tag
  that redirects relative URLs.
- **The panel's policy is only partly locked down.** It sets no `default-src`,
  `style-src`, or `connect-src`. Tighten it for your own app if your assets allow.

Two more things protect the pages:

- **Escape every value you put into HTML**, such as titles, asset URLs, and error
  messages. The page data has its own rule
  ([chapter 3](03-load-the-panel-page.md#escape-the-page-data)). In the panel,
  render CRM and Dialpad data as text, never as HTML.
- **Validate the Dialpad origin before it reaches a header or a script.** A `;` or
  a space in a CSP value adds directives. This app checks `DIALPAD_ORIGIN` at
  startup and again when rendering.

## Keep secrets out of logs

- **Turn off your web server's access log**, or strip query strings from it,
  because every page URL carries an idtoken. Log errors with the method and path,
  never the query string.
- **Keep secrets out of your settings' string form**, so they can't appear in a
  log line or a traceback.
- **Check your host's logs too.** Cloud Run's request log records the full URL,
  idtoken included. [`deployment/README.md`](../deployment/README.md) shows how to
  exclude it.

## In this demo

- `server/acme_dialpad_rightbar/pages.py` builds each page's headers and nonce.
- The access log is off, and the error handler logs only the method, the path,
  and the exception type. A test checks that the server never logs the idtoken,
  the access token, or the cookie.
- `DIALPAD_CLIENT_SECRET` and `APP_SECRET` are left out of the settings' `repr`.
- Tests render each page with hostile values to check the escaping.

---

**Previous:** [8. Call Dialpad's API and receive events](08-call-dialpad.md) ·
**Next:** [10. Test your app](10-test-your-app.md) ·
[Contents](../README.md#the-guide)
