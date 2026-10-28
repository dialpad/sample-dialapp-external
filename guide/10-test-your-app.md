# 10. Test your app

The SDK ships a mock Dialpad, so you can test your panel without Dialpad: in
memory for unit tests, and in a real browser for end-to-end tests.

## The SDK's testing helpers

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

With `globals: true`, or in Jest, the setup file disposes every mock host after
each test. Otherwise, call `disposeAllMockHosts()` in your own `afterEach`.

## Write a unit test

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

- **The mock host has its own clock.** A Connect test calls
  `await host.advance(7_000)` instead of using fake timers.
- **`host.received`** records what the panel asked Dialpad to do: toasts, the
  linked record, the panel menu, screen pops, the refresh button, and authorize
  requests.
- **Pass `fetch` to `host.createRightbar()`** to answer the two Connect endpoints.

## Test in a real browser

`mountMockHostPage()` frames your real page in a browser page that plays
Dialpad. Your server renders the page data from a mock idtoken, so the helper
takes no page data itself. This app's local mode serves such a page URL at
`/dev/frame-url`, and the dev host uses it.

## This repository's tests

- **`client/src/App.test.ts`** drives every state of the panel against the mock
  host, and **`client/src/crm/CrmRecord.test.ts`** the CRM record's. Both use
  the harness in `client/src/testing.ts`. Run them with `pnpm test:run`.
- **`client/e2e/sdk/`** drives the dev host in Chromium with Playwright, using
  Playwright's clock so polling costs no real time. Run it with `pnpm test:e2e`,
  after installing the browser once with `pnpm exec playwright install chromium`.
  It starts the server and Vite itself. Its [README](../client/e2e/sdk/README.md)
  lists the tests. They test this repository, not your app, so delete the folder
  when you copy the app.
- **`server/tests/`** tests the server, including the idtoken decoder, the pages'
  headers and escaping, and the logs. `test_crm.py` tests the CRM record's
  routes.

## Run the checks

Each folder has its own checks:

```sh
# client/
pnpm lint:ci && pnpm format:ci && pnpm types:check && pnpm test:run
pnpm test:e2e                                   # browser tests

# server/
uvx tox                                         # tests, linter, type checker, code style
uvx tox -e apply_python_code_style              # reformat with yapf
```

The server's tox environments build their own virtual environments with
[tox-uv](https://github.com/tox-dev/tox-uv), so they need no `.venv`. They run
pytest (warnings as errors), Ruff (every rule), ty (every rule as an error), and
yapf. In the `.venv` from [chapter 2](02-run-the-demo.md#install), the same checks
run directly: `.venv/bin/pytest`, `.venv/bin/ruff check acme_dialpad_rightbar tests`,
`.venv/bin/ty check acme_dialpad_rightbar tests`, and
`.venv/bin/yapf --style .style.yapf --diff -r acme_dialpad_rightbar tests`.

`pnpm format:ci` also checks the Markdown files, including this guide.

GitHub Actions (`.github/workflows/ci.yaml`) runs all of these on every pull
request and every push to `main`, plus a Docker build with a start-up check. The
`sample-dialapp-external check` job passes only when all of them pass, so require
it on `main`.

---

**Previous:** [9. Security checklist](09-security-checklist.md) ·
**Next:** [11. Turn the demo into your app](11-from-demo-to-your-app.md) ·
[Contents](../README.md#the-guide)
