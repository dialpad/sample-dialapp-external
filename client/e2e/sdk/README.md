# Browser tests

These tests exercise the panel and `@dialpad/dialapp-external-sdk` in a real
browser. They run from dialapp-external's CI against every new build of the
libraries, and locally with `pnpm run test:e2e`.

They are not part of the template: partners can delete this folder when they
copy the app (along with `playwright.config.ts`, the `test:e2e` script and the
`@playwright/test` dependency). Nothing else in the repository depends on them.

The tests run in Chromium against the dev host, which stands in for Dialpad,
with Playwright's clock so polling and timeouts cost no real time. They read
what the mock host believes through `window.mockHost`, which `dev-host/main.ts`
exposes.

| Test                        | What it checks                                                                                                                                     |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Connect, reload, disconnect | The flow: Connect through the fake OAuth page and polling, the Acme'd contact and changing it, a reload that starts connected, and Disconnect      |
| Calls                       | The call card follows a call (ringing, connected, ended, a new call), and the call's own contact is shown when it differs from the panel's contact |
| Opened outside Dialpad      | The framing check (`not_framed`): the panel page opened directly, not in an iframe, shows "Open this panel from Dialpad"                           |
| Connect times out           | Polling gives up after 2 minutes: the timeout state with Try again, and the host is still told "not connected"                                     |
| Disconnect from the menu    | The host's panel menu Disconnect: the SDK calls `/dialpad/ext-disconnect`, shows the Connect gate and tells the host "not connected"               |
