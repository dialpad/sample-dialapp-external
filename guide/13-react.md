# 13. Build the panel in React

To use React, replace only the Vue code. The server doesn't change. This
repository doesn't build or run these snippets; they're sketches.

Everything in [What stays the same](12-plain-javascript.md#what-stays-the-same)
in chapter 12 applies: the server, the SDK calls, the framework-free modules (with
`sessionExpired` as a plain flag), and the BEM CSS. Dialtone's Vue components
don't, so use Dialtone's CSS and design tokens on your own React components.

## Start the SDK

Start the SDK outside React, before the first render, as the Vue app does in
`bootstrap.ts`. If you start it inside a `useEffect` and wrap your app in
`<StrictMode>`, as most React templates do, React mounts, unmounts, and remounts
the component in development. That creates two SDK instances and runs the `init`
handshake twice.

```tsx
// main.tsx
import { createRightbar, RightbarError } from "@dialpad/dialapp-external-sdk";
import { initDialtoneTheme, setMode } from "@dialpad/dialtone/themes/config";
import dp from "@dialpad/dialtone/themes/dp";
import "@dialpad/dialtone/css";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { RightbarProvider } from "./rightbar";
import { api, useAuthHeaders } from "./api";

const root = document.getElementById("app")!;
try {
  const rightbar = await createRightbar({ heightRoot: root, fetch: api });
  useAuthHeaders(() => rightbar.authHeaders());
  // Follow Dialpad's light and dark mode. Dialtone's theme module is plain
  // JavaScript, so it works the same without Vue.
  initDialtoneTheme(dp, rightbar.state.theme.mode);
  rightbar.watch(
    (state) => state.theme.mode,
    (mode) => setMode(mode),
  );
  createRoot(root).render(
    <RightbarProvider rightbar={rightbar}>
      <App />
    </RightbarProvider>,
  );
} catch (error) {
  if (!(error instanceof RightbarError)) throw error;
  root.textContent = "Open this panel from Dialpad.";
}
```

## Bind the SDK to React

The binding is about 15 lines. The SDK's snapshot is immutable, replaced
on every change, and unchanged parts keep their references. That is exactly what
`useSyncExternalStore` expects, so a hook over `subscribe` and `state` replaces
`useRightbar()` and `rightbarPlugin`:

```tsx
// rightbar.tsx
import type { Rightbar, RightbarState } from "@dialpad/dialapp-external-sdk";
import {
  createContext,
  useContext,
  useSyncExternalStore,
  type ReactNode,
} from "react";

const RightbarContext = createContext<Rightbar | null>(null);

export function RightbarProvider({
  rightbar,
  children,
}: {
  rightbar: Rightbar;
  children: ReactNode;
}) {
  return (
    <RightbarContext.Provider value={rightbar}>
      {children}
    </RightbarContext.Provider>
  );
}

/** The SDK instance, for actions: `authorize()`, `disconnect()`, `linkRecord(...)`. */
export function useRightbar(): Rightbar {
  const rightbar = useContext(RightbarContext);
  if (!rightbar) throw new Error("Wrap the app in <RightbarProvider>");
  return rightbar;
}

/** A selected part of the snapshot; the component re-renders only when that part changes. */
export function useRightbarState<T>(select: (state: RightbarState) => T): T {
  const rightbar = useRightbar();
  return useSyncExternalStore(
    (onChange) => rightbar.subscribe(() => onChange()),
    () => select(rightbar.state),
  );
}
```

`useRightbarState((s) => s.connection)` is the React form of
`computed(() => state.value.connection)`. Pick selectors that return a part of the
snapshot as it is (`s.call`, `s.connection`), not a freshly built object, or the
component re-renders on every change.

## The contact section

The one component with state of its own is the contact section. With hooks,
it's an effect with an "ignore" flag, which is the React form of the `lookup`
counter in `AcmeContact.vue`:

```tsx
function AcmeContact({ contact }: { contact: Contact | null }) {
  const [view, setView] = useState<{
    status: "idle" | "loading" | "ready" | "failed";
    fields: AcmeField[];
  }>({ status: "idle", fields: [] });
  useEffect(() => {
    if (!contact) return setView({ status: "idle", fields: [] });
    let stale = false; // set by the cleanup when the contact changes or the component unmounts
    setView({ status: "loading", fields: [] });
    fetchAcmeFields(contact).then(
      (fields) => !stale && setView({ status: "ready", fields }),
      () => !stale && setView({ status: "failed", fields: [] }),
    );
    return () => {
      stale = true;
    };
  }, [contact]);
  // ...render view.status and view.fields as AcmeContact.vue does
}
```

## Everything else

Everything else maps one to one: `App.vue` to `App`, `ConnectGate.vue` to
`ConnectGate` (reading `useRightbarState((s) => s.connection)` and calling
`useRightbar().authorize()`), the cards to components, and `sessionExpired` (a Vue
`ref`) to a small store or context read through `useSyncExternalStore`. Tests use
React Testing Library with the SDK's mock host, and the Playwright tests do not
change. Build with `@vitejs/plugin-react`, and point the server's `ENTRY`
(`server/acme_dialpad_rightbar/assets.py`) and `rollupOptions.input` in
`vite.config.ts` at `src/main.tsx`.

---

**Previous:** [12. Build the panel in plain JavaScript](12-plain-javascript.md) ·
**Next:** [Reference](reference.md) ·
[Contents](../README.md#the-guide)
