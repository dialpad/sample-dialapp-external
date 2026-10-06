# SDK browser tests

These tests exist to exercise `@dialpad/dialapp-external-sdk` in a real browser.
They run from dialapp-external's CI against every new build of the libraries,
together with `e2e/smoke.spec.ts`.

They are not part of the template: partners can delete this folder when they
copy the app. Nothing else in the repository depends on it.

They run with the rest of the Playwright tests (`pnpm run test:e2e`), in
Chromium against the dev page, and use `window.mockHost`, the mock host that
`dev/main.ts` exposes.

| Test                     | What it checks in the SDK                                                                                                            |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ |
| Opened outside Dialpad   | The framing check (`not_framed`): the panel page opened directly, not in an iframe, shows "Open this panel from Dialpad"             |
| Connect times out        | Polling gives up after 2 minutes: the timeout state with Try again, and the host is still told "not connected"                       |
| Disconnect from the menu | The host's panel menu Disconnect: the SDK calls `/dialpad/ext-disconnect`, shows the Connect gate and tells the host "not connected" |
