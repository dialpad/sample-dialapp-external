# 12. Build the panel in plain JavaScript

This app's panel uses Vue 3, but nothing in the contract or the SDK needs a
framework. The SDK's main entry (`@dialpad/dialapp-external-sdk`) has no framework
in it. Its `/vue` entry is a thin binding that turns the SDK's snapshot into a
reactive value and gives it to every component. This chapter sketches the panel
without Vue; this repository doesn't build or run the sketch.

## What stays the same

- **The whole server.** The page, the contract endpoints, `POST /api/contact`, the
  OAuth screens, the storage cookie, the CSP, and everything in
  [chapter 9](09-security-checklist.md) stay exactly as they are. The iframe
  panel only needs a `<div id="app">` and a script, which `dialpad/panel_page.py` already
  renders.
- **The SDK calls.** `createRightbar`, `rightbar.state`, `rightbar.subscribe`,
  `rightbar.watch`, `authorize`, `disconnect`, `authHeaders`, `linkRecord`,
  `setMenu`, and the rest.
- **The framework-free modules**: `crm/contactApi.ts` (the request to
  `POST /api/contact`), `demo/customPageAppData.ts` (validates the page data's
  `app` field), and `crm/contacts.ts` (compares two contacts) import nothing
  from Vue.
  `client/src/api.ts` (adds the bearer header and turns a `401` into the "reload"
  notice) needs one small change: its `accessTokenRejected` flag is a Vue `ref`, so it
  becomes a plain variable plus a callback that re-renders (shown below).
- **The CSS.** `style.css` and the BEM classes (such as `acme-contact__label`)
  carry over; each component's `<style>` block becomes a plain `.css` file.
- **The bundler.** Vite still builds one entry, and the server still links it from
  Vite's manifest (`ENTRY` in `server/acme_dialpad_rightbar/assets.py` changes from
  `src/main.ts` to `src/main.js` if you rename it).

## What changes

| In the Vue app                                                                                                              | In plain JavaScript                                                                   |
| --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `main.ts`, `bootstrap.ts`, `panelMenu.ts`                                                                                   | One `main.js`: create the SDK instance, then render and subscribe                     |
| `App.vue`                                                                                                                   | `renderApp(state)`: the title, the reload notice, then the gate or the connected view |
| `ConnectGate.vue`                                                                                                           | `renderConnectGate(connection)`                                                       |
| `ConnectedView.vue`, `UserCard.vue`, `CallCard.vue`, `demo/DialpadApiCard.vue`, `DisconnectButton.vue`, `crm/CrmRecord.vue` | One render function each, returning DOM nodes                                         |
| `crm/AcmeContact.vue`                                                                                                       | A small object that owns its own lookup state (see below)                             |
| `useRightbar()` and `rightbarPlugin`                                                                                        | `rightbar.state` and `rightbar.subscribe(...)` directly                               |
| [Dialtone](https://dialtone.dialpad.com/)'s Vue components (`DtButton`, `DtNotice`, `DtAvatar`)                             | Dialtone's CSS (`@dialpad/dialtone/css`) and tokens on your own markup                |
| Vue's reactivity                                                                                                            | You decide when to re-render: on every snapshot, or only for the part that changed    |

## The shape of it

The SDK gives you an immutable snapshot (`rightbar.state`) and calls you back with
the next one, so the simplest panel renders everything from the snapshot
each time:

```js
// main.js
import { createRightbar, RightbarError } from "@dialpad/dialapp-external-sdk";
import { initDialtoneTheme, setMode } from "@dialpad/dialtone/themes/config";
import dp from "@dialpad/dialtone/themes/dp";
import "@dialpad/dialtone/css";
import "./style.css";

// api.ts, with `accessTokenRejected` as a plain flag and a hook the 401 handler calls:
//   export let accessTokenRejected = false;
//   export function onAccessTokenRejected(callback) { ... call it when a 401 sets the flag ... }
import {
  api,
  onAccessTokenRejected,
  accessTokenRejected,
  useAuthHeaders,
} from "./api";

const root = document.getElementById("app");

async function start() {
  let rightbar;
  try {
    // Reads the page data, checks the page is framed by Dialpad, does the `init` handshake.
    rightbar = await createRightbar({ heightRoot: root, fetch: api });
  } catch (error) {
    if (!(error instanceof RightbarError)) throw error;
    root.textContent = "Open this panel from Dialpad."; // not_framed, bad_page_data, init_timeout...
    return;
  }
  useAuthHeaders(() => rightbar.authHeaders());

  // Follow Dialpad's light and dark mode.
  initDialtoneTheme(dp, rightbar.state.theme.mode);
  rightbar.watch(
    (state) => state.theme.mode,
    (mode) => setMode(mode),
  );
  // Set Dialpad's panel menu from the connection, now and on every change (chapter 4).
  rightbar.watch(
    (state) => state.connection.connected,
    (connected) =>
      rightbar
        .setMenu(connected ? [{ id: "disconnect", label: "Disconnect" }] : [])
        .catch(console.warn),
  );
  rightbar.on("menuSelect", (id) => {
    if (id === "disconnect") rightbar.disconnect();
  });

  const contact = createContactSection(rightbar); // owns its own lookups, see below
  const render = (state) =>
    root.replaceChildren(...renderApp(state, rightbar, contact));
  render(rightbar.state);
  rightbar.subscribe((next) => render(next)); // every new snapshot from the SDK
  contact.subscribe(() => render(rightbar.state)); // a contact lookup finished
  onAccessTokenRejected(() => render(rightbar.state)); // a request got a 401
}

await start();
```

Rendering is ordinary DOM code. Build elements and set `textContent`; never put
CRM or Dialpad data into `innerHTML` (a contact name can contain markup), which is
the same reason the Vue templates only ever interpolate text:

```js
// A tiny element helper: h('p', { class: 'acme-muted' }, 'No active call.')
function h(tag, props = {}, ...children) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(props)) {
    if (name.startsWith("on"))
      element.addEventListener(name.slice(2).toLowerCase(), value);
    else if (value !== false && value != null)
      element.setAttribute(name, value === true ? "" : value);
  }
  element.append(
    ...children.flat().filter((child) => child != null && child !== false),
  );
  return element;
}

function renderApp(state, rightbar, contact) {
  return [
    h("h1", { class: "acme-title" }, "Acme for Dialpad (demo)"),
    accessTokenRejected &&
      h(
        "div",
        { role: "alert", class: "acme-notice" },
        "Reload the panel to keep going.",
      ),
    state.connection.connected
      ? renderConnectedView(state, rightbar, contact)
      : renderConnectGate(state.connection, rightbar),
  ];
}

const ERROR_COPY = {
  timeout: "Acme didn't respond in time.",
  network: "We couldn't reach Acme. Check your connection.",
  request_failed: "Something went wrong while checking your Acme connection.",
};

function renderConnectGate(connection, rightbar) {
  const code = connection.error?.code;
  return h(
    "section",
    { class: "acme-gate", "data-testid": "connect-gate" },
    h("p", {}, "Connect your Acme account to see your records here."),
    code && h("div", { role: "alert" }, ERROR_COPY[code]),
    connection.pending &&
      h(
        "p",
        { role: "status" },
        "Waiting for you to finish connecting in the Acme window...",
      ),
    h(
      "button",
      {
        type: "button",
        class: "d-btn d-btn--primary", // Dialtone's CSS on your own markup
        disabled: connection.pending,
        onClick: () => rightbar.authorize(), // opens the authorize URL, then the SDK polls
      },
      code ? "Try again" : "Connect",
    ),
  );
}
```

Replacing all the children on every snapshot is fine for a panel this small, but it
drops focus, scroll position, and text typed into an input. If that matters, either
render only the part whose state changed (`rightbar.watch((s) => s.call, ...)`
re-runs only when the call changes, because unchanged parts of the snapshot keep
their references) or use a tiny DOM-diffing library such as `lit-html` or
`morphdom` for the render step.

## The contact section

`crm/AcmeContact.vue` is the one component with state of its own: it asks the server for
the CRM's view of whichever contact is open, shows loading and failure, and must
ignore a late answer for an earlier contact. Without Vue, that's a watcher and a
counter, the same as the `watch` and `lookup` counter in the Vue file:

```js
import { fetchAcmeContact } from "./contactApi";

function createContactSection(rightbar) {
  const view = { status: "idle", fields: [] };
  let lookup = 0;
  let linked = false;
  let onChange = () => {};

  // Runs now and whenever `state.contact` changes (a new contact object), not on other changes.
  rightbar.watch(
    (state) => state.contact,
    async (contact) => {
      lookup += 1;
      const mine = lookup;
      if (linked) {
        linked = false;
        rightbar.linkRecord(null).catch(console.warn);
      }
      view.fields = [];
      view.status = contact ? "loading" : "idle";
      onChange();
      if (!contact) return;
      try {
        const { fields, record } = await fetchAcmeContact(contact);
        if (mine !== lookup) return;
        Object.assign(view, { status: "ready", fields });
        if (record) {
          linked = true;
          rightbar.linkRecord(record).catch(console.warn);
        }
      } catch {
        if (mine === lookup) view.status = "failed";
      }
      onChange();
    },
  );

  return {
    view,
    // main.js passes its `render` here, so a finished lookup re-renders the panel.
    subscribe: (callback) => {
      onChange = callback;
    },
  };
}
```

The section links the record once the lookup succeeds and unlinks when the
contact changes. Also unlink when the user disconnects
([chapter 4](04-build-the-panel.md#the-view-button)).

## Tests and the bundle

The SDK's testing entry (`@dialpad/dialapp-external-sdk/testing`) isn't
Vue-specific: `createMockHost()`, `makePageData()`, and `host.sendContact(...)` give a
fake Dialpad, and `host.createRightbar(...)` returns a real `Rightbar` to render
from. Only the Vue helper `mountWithRightbar` (from `/vue/testing`) goes away: mount
by calling your `render` into a jsdom element. The browser tests don't change at all, because they
find elements only by `data-testid` and role.

What you give up is the framework: no components with scoped state, no templates to
check, and no reactivity, so keeping the DOM in step with the snapshot is your code. What
you gain is a much smaller bundle: this app's is about 116 kB gzipped (Vue, Dialtone's
Vue components, and the SDK).

---

**Previous:** [11. Turn the demo into your app](11-from-demo-to-your-app.md) ·
**Next:** [13. Build the panel in React](13-react.md) ·
[Contents](../README.md#the-guide)
