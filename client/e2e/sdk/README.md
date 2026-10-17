# Browser tests

These tests exercise the iframe panel and `@dialpad/dialapp-external-sdk` in a
real browser. Run them with `pnpm run test:e2e`.

They are not part of the template: partners can delete this folder when they
copy the app (along with `playwright.config.ts`, the `test:e2e` script and the
`@playwright/test` dependency). Nothing else in the repository depends on them.

The tests run in Chromium against the dev host, which stands in for Dialpad,
with Playwright's clock so polling and timeouts cost no real time. They read
what the mock host believes through `window.mockHost`, which `dev-host/main.ts`
exposes.

| Test                        | What it checks                                                                                                                                                                                                                                                                            |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Connect, reload, disconnect | The flow: Connect through the fake OAuth page and polling, its success toast, the Acme'd contact and changing it with the linked record following, a reload that starts connected, and Disconnect unlinking it. The panel menu the panel sets follows: empty, then Disconnect, then empty |
| Calls                       | The call card follows a call (ringing, connected, ended, a new call), and the call's own contact is shown when it differs from the iframe panel's contact                                                                                                                                 |
| Opened outside Dialpad      | The framing check (`not_framed`): the iframe panel page opened directly, not in an iframe, shows "Open this panel from Dialpad"                                                                                                                                                           |
| Connect times out           | Polling gives up after 2 minutes: the timeout state with Try again, and the host is still told "not connected"                                                                                                                                                                            |
| Disconnect from the menu    | The Disconnect the panel puts in the host's panel menu: the SDK calls `/dialpad/ext-disconnect`, shows the Connect gate, tells the host "not connected", empties the menu, and shows an info toast                                                                                        |
| Failed contact lookup       | A contact the server cannot look up shows the message in the panel and an error toast in the dev host                                                                                                                                                                                     |
