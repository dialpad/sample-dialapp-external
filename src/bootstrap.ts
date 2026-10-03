import { createRightbar, type Rightbar, type RightbarOptions } from '@dialpad/dialapp-external-sdk';
import { rightbarPlugin } from '@dialpad/dialapp-external-sdk/vue';
import { initDialtoneTheme, setMode } from '@dialpad/dialtone/themes/config';
import dp from '@dialpad/dialtone/themes/dp';
import { createApp } from 'vue';

import { api, useAuthHeaders } from './api';
import App from './App.vue';
import BootstrapError from './BootstrapError.vue';

export type CreateRightbar = (options: RightbarOptions) => Promise<Rightbar>;

/**
 * Starts the panel: `createRightbar()` before mounting, then the theme, then the app. When the SDK
 * rejects (`bad_options`, `not_framed`, `bad_page_data`, `init_timeout`), the user is told to open
 * the panel from Dialpad instead. `create` is injectable so tests can use the mock host.
 */
export async function bootstrap(root: HTMLElement, create: CreateRightbar = createRightbar): Promise<void> {
  let rightbar: Rightbar;
  try {
    rightbar = await create({ heightRoot: root, fetch: api });
  } catch {
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

  createApp(App).use(rightbarPlugin, rightbar).mount(root);
}
