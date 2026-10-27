import {
  createRightbar,
  RightbarError,
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
import { setUpPanelMenu } from './panelMenu';

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
