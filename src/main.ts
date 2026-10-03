import '@dialpad/dialtone/css';
import './style.css';

import { bootstrap } from './bootstrap';

const root = document.getElementById('app');
if (!root) {
  throw new Error('Missing #app element');
}

await bootstrap(root);
