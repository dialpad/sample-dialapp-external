import {
  createRightbar,
  RightbarError,
  type MenuItem,
  type Rightbar,
  type RightbarOptions,
} from '@dialpad/dialapp-external-sdk';
import { rightbarPlugin } from '@dialpad/dialapp-external-sdk/vue';
import { initDialtoneTheme, setMode } from '@dialpad/dialtone/themes/config';
import dp from '@dialpad/dialtone/themes/dp';
import { createApp } from 'vue';

import { api, useAuthHeaders } from './api';
import App from './App.vue';
import BootstrapError from './BootstrapError.vue';

/** The shape of the SDK's `createRightbar`, so tests can swap in the mock host's. */
export type CreateRightbar = (options: RightbarOptions) => Promise<Rightbar>;

/**
 * Start the iframe panel inside `root`.
 *
 * Called once, as soon as the page's script runs, when `root` is still empty. It asks the SDK to
 * start (the SDK reads the page data, checks the page is framed by Dialpad and does the `init`
 * handshake), applies Dialpad's light or dark mode, sets up Dialpad's panel menu and header refresh
 * button, and mounts the Vue app, which then renders from the SDK's snapshot. If the SDK refuses to start (`bad_options`, `not_framed`, `bad_page_data` or
 * `init_timeout`) the page is not in a working Dialpad iframe, so a short "open this panel from
 * Dialpad" message is mounted instead and nothing else runs. Any other error is a bug and is
 * rethrown. `create` defaults to the real SDK; tests pass the mock host's.
 */
export async function bootstrap(
  root: HTMLElement,
  create: CreateRightbar = createRightbar,
): Promise<void> {
  let rightbar: Rightbar;
  try {
    rightbar = await create({ heightRoot: root, fetch: api });
  } catch (error) {
    if (!(error instanceof RightbarError)) {
      throw error;
    }
    // The user only sees "open this panel from Dialpad"; the code says which of the four reasons it is.
    console.warn('The panel could not start', error.code, error.message);
    createApp(BootstrapError).mount(root);
    return;
  }
  useAuthHeaders(() => rightbar.authHeaders());

  // Follow the host's light/dark mode. `theme.brand` is always null today, so only the mode.
  initDialtoneTheme(dp, rightbar.state.theme.mode);
  rightbar.watch(
    (s) => s.theme.mode,
    (mode) => {
      setMode(mode);
    },
  );

  setUpPanelMenu(rightbar);

  createApp(App).use(rightbarPlugin, rightbar).mount(root);
}

/**
 * The panel menu while the user is connected. The ids are the app's own; the labels are what
 * Dialpad shows, in English only here. A real app picks translated labels from
 * `state.user.language` (chapter 4 of the guide).
 */
export const CONNECTED_MENU = [
  { id: 'rematch', label: 'Rematch' },
  { id: 'create-task', label: 'Create Task' },
  { id: 'disconnect', label: 'Disconnect' },
] as const satisfies readonly MenuItem[];

/**
 * What the panel menu's Rematch and Create Task tell the user here, by item id. The demo has no
 * contact mapping and no CRM tasks, so it offers both to show the round trip and says they aren't
 * built.
 */
export const MENU_NOT_IMPLEMENTED: Readonly<Record<string, string>> = {
  rematch: "Rematch isn't implemented in this sample app",
  'create-task': "Create Task isn't implemented in this sample app",
};

/**
 * Set Dialpad's panel menu and header refresh button from the connection, now and on every change,
 * and answer the menu's items.
 *
 * Dialpad shows exactly these items and forgets them when the panel reloads, so this runs at every
 * start. Disconnect calls the SDK's `disconnect()`, as the panel's own button does. Refresh needs
 * nothing here: the SDK reloads the contact and `AcmeContact.vue` looks it up again (chapter 4 of
 * the guide covers the menu and the button). A real app offers Rematch once its server has matched
 * the contact to a record, and makes it forget that match and look the contact up again; it offers
 * Create Task when the CRM has tasks, and shows a form for one (chapter 7). A menu, button or toast
 * Dialpad rejects is logged and the panel goes on.
 */
function setUpPanelMenu(rightbar: Rightbar): void {
  rightbar.watch(
    (s) => s.connection.connected,
    (connected) => {
      rightbar
        .setMenu(connected ? CONNECTED_MENU : [])
        .catch((error: unknown) => {
          console.warn("Dialpad didn't set the panel menu", error);
        });
      rightbar.showRefreshButton(connected).catch((error: unknown) => {
        console.warn("Dialpad didn't show the refresh button", error);
      });
    },
  );
  rightbar.on('menuSelect', (id) => {
    if (id === 'disconnect') {
      void rightbar.disconnect();
      return;
    }
    const text = MENU_NOT_IMPLEMENTED[id];
    if (text) {
      rightbar.showToast({ text, type: 'info' }).catch((error: unknown) => {
        console.warn("Dialpad didn't show the toast", error);
      });
    }
  });
}
