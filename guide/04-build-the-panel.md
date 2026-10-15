# 4. Build the panel with the SDK

`@dialpad/dialapp-external-sdk` connects your panel to Dialpad. It's headless: it
has no UI, so you build the panel with any framework, or none. It supports Chrome
109 and later and the Dialpad desktop app, and it's ES modules only, so use a
bundler such as Vite.

## Start the SDK

`createRightbar()` reads the page data, checks that Dialpad frames the page,
completes the handshake with Dialpad, and loads the call, the theme, the user,
and the open contact. Call it once, before your first render:

```ts
import { createRightbar, RightbarError } from "@dialpad/dialapp-external-sdk";
import { api } from "./api"; // your own fetch wrapper (chapter 5)

const root = document.getElementById("app")!;
try {
  const rightbar = await createRightbar({
    heightRoot: root,
    fetch: api,
    onDisconnect: () => {
      // clear any CRM data the panel holds
    },
  });
  // render your UI from rightbar.state
} catch (error) {
  if (!(error instanceof RightbarError)) throw error;
  root.textContent = "Open this panel from Dialpad.";
}
```

- **`heightRoot`** (required) is the element that holds the panel's content,
  usually your mount element. The SDK reports its height to Dialpad, which sizes
  the iframe to fit. Overlays placed under `body` take no space in it, so the SDK
  doesn't count them.
- **`fetch`** makes the SDK's own requests to your server. It defaults to the
  browser's `fetch`, and the SDK adds the `Authorization` header itself. Pass your
  own wrapper so you can notice a `401` ([chapter 5](05-authenticate-requests.md)).
- **`onDisconnect`** runs after the user disconnects
  ([chapter 6](06-connect-to-the-crm.md#disconnect)).

If the SDK can't start, `createRightbar()` rejects with a `RightbarError`. Its
`code` says why:

| Code            | Meaning                                                 |
| --------------- | ------------------------------------------------------- |
| `bad_options`   | `heightRoot` is missing, or a callback isn't a function |
| `not_framed`    | The page isn't open inside Dialpad                      |
| `bad_page_data` | The page data element is missing or invalid             |
| `init_timeout`  | Dialpad didn't answer the handshake within 10 seconds   |

In every case the panel can't work, so show a short "Open this panel from
Dialpad" message instead of the app, as the example does.

When the panel unmounts, call `rightbar.destroy()`. It stops listening to
Dialpad, stops any polling, and stops the height reports.

## Render from the state

`rightbar.state` is a snapshot of everything the panel knows:

```ts
rightbar.state;
// { ready, user, contact, call, theme: { mode, brand },
//   connection: { connected, pending, authorizationUrls, name, scopes, error } }
```

| Field        | What it holds                                                                                                                                                                        |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `ready`      | `true` once the handshake and the first loads are done, which is always the case after `createRightbar()` resolves                                                                   |
| `user`       | The Dialpad user (IDs, names, emails, phone numbers, licenses, admin flags, and availability), or `null`. Dialpad sends no updates, so the status fields are as of the panel's start |
| `contact`    | The contact open in Dialpad, or `null`. The SDK reloads it when the user presses Dialpad's refresh button or the contact's record changes                                            |
| `call`       | The active call, updated on every call event, or `null`                                                                                                                              |
| `theme`      | `{ mode: 'light' \| 'dark', brand }`. `brand` is `null` in this SDK version                                                                                                          |
| `connection` | The user's connection to the CRM ([chapter 6](06-connect-to-the-crm.md#the-connection))                                                                                              |

Every change produces a new snapshot, and the parts that didn't change keep
their references. To follow changes:

- `rightbar.subscribe((next, prev) => …)` runs on every change.
- `rightbar.watch((state) => state.contact, (contact) => …)` runs its callback now
  and again whenever that part changes.

With Vue, the SDK's `/vue` entry does this for you. Install the plugin with
`app.use(rightbarPlugin, rightbar)`, and read the SDK in any component with
`const { state, authorize, disconnect } = useRightbar()`, where `state` is a ref.

```vue
<script setup lang="ts">
import { useRightbar } from "@dialpad/dialapp-external-sdk/vue";
const { state } = useRightbar();
</script>

<template>
  <p v-if="state.call">Call: {{ state.call.state }}</p>
  <p v-else>No active call.</p>
</template>
```

## Follow the theme

Follow Dialpad's light and dark mode. With Dialtone:

```ts
import { initDialtoneTheme, setMode } from "@dialpad/dialtone/themes/config";
import dp from "@dialpad/dialtone/themes/dp";

initDialtoneTheme(dp, rightbar.state.theme.mode);
rightbar.watch(
  (state) => state.theme.mode,
  (mode) => setMode(mode),
);
```

## Design for the panel's size

The panel is 318 pixels wide in the right sidebar by default (266 to 414 as the
user resizes it) and 250 pixels in Dialpad Everywhere. Design it to be responsive
across that range, and test it at 250 pixels at the very least. Its height
follows `heightRoot`.

This app shrinks everything by a fifth below 260 pixels. Dialtone sizes spacing
in `rem` but text from `--dt-font-size-root`, so it changes both:

```css
@media (max-width: 260px) {
  html {
    font-size: 8px;
  }
  :root {
    --dt-font-size-root: 8px;
  }
}
```

The same panel at both widths, at actual size:

| Right sidebar, 318 pixels                                                                                  | Dialpad Everywhere, 250 pixels                                                                                                          |
| ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| <img src="images/panel-318.png" width="318" alt="The connected panel at 318 pixels wide, at normal size."> | <img src="images/panel-250.png" width="250" alt="The same panel at 250 pixels wide, with its text and spacing scaled down by a fifth."> |

A few more things about the space you have:

- **No modal dialogs.** A dialog can't leave the iframe, and the panel is narrow,
  so confirm actions inline, as this app's **Disconnect** button does.
- **Use Dialtone** for a panel that looks like the rest of Dialpad. Its
  components are Vue components, which is why this app uses Vue. Other frameworks
  can use Dialtone's CSS and tokens.
- **Isolate your CSS by naming.** This app avoids Vue's `scoped` styles and uses
  BEM classes with an `acme-` prefix (`acme-<block>__<element>--<modifier>`), one
  class per selector, so they can't collide with Dialtone's classes.

## Use Dialpad's UI

Some things appear outside your panel, in Dialpad:

| Call                             | What it does                                                                                                                                                        |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `showToast({ text, type })`      | Shows a short message in Dialpad, outside the panel. `type` is `info` (the default), `success`, or `error`                                                          |
| `showRefreshButton(show)`        | Shows or hides the refresh button in the panel's header. When the user presses it, the SDK reloads `state.contact` and then emits `refreshContact`                  |
| `on('refreshContact', callback)` | Runs `callback` after the SDK reloads `state.contact`, from the refresh button or because the contact's record changed in Dialpad. Returns a function that stops it |

This app shows a toast when Connect finishes, when the user disconnects, and when
a contact lookup fails.

## Pass your own data to the panel

The page data's `app` field carries any JSON your server wants the panel to have
when it loads. The SDK gives it to you as `rightbar.app`, or `null` when there's
none. Validate it before you use it, as with any input.

## In this demo

- `client/src/bootstrap.ts` starts the SDK, follows the theme, and mounts the Vue
  app, or `BootstrapError.vue` when the SDK can't start.
- `App.vue` shows the reload notice and either the Connect screen
  (`ConnectGate.vue`) or the connected view (`ConnectedView.vue`), which holds a
  card for the user, the call, the open contact, and the demo's call to Dialpad's
  API.
- `client/src/style.css` has the shared styles and the narrow-panel media query.
- The demo puts the result of its call to Dialpad's API in the page data's `app`
  field, and `customPageAppData.ts` validates it.

---

**Previous:** [3. Load the panel page](03-load-the-panel-page.md) ·
**Next:** [5. Authenticate the panel's requests](05-authenticate-requests.md) ·
[Contents](../README.md#the-guide)
