// The page's entry module: the server's page loads it, and it only starts `bootstrap`.
// Dialtone's CSS is imported once, here, and components are imported one by one where used.
import '@dialpad/dialtone/css';
import './style.css';

import { bootstrap } from './bootstrap';

const root = document.getElementById('app');
if (!root) {
  throw new Error('Missing #app element');
}

await bootstrap(root);
