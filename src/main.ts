import '@dialpad/dialtone/css';
import './style.css';

import { createRightbar } from '@dialpad/dialapp-external-sdk';
import { rightbarPlugin } from '@dialpad/dialapp-external-sdk/vue';
import { initDialtoneTheme, setMode } from '@dialpad/dialtone/themes/config';
import dp from '@dialpad/dialtone/themes/dp';
import { createApp } from 'vue';

import { api, useAuthHeaders } from './api';
import App from './App.vue';
import BootstrapError from './BootstrapError.vue';

const root = document.getElementById('app');
if (!root) {
  throw new Error('Missing #app element');
}

try {
  const rightbar = await createRightbar({ heightRoot: root, fetch: api });
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
} catch {
  // bad_options, not_framed, bad_page_data and init_timeout all mean the same to the user.
  createApp(BootstrapError).mount(root);
}
