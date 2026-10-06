// The dev page: a stand-in for Dialpad, for running the panel locally without Dialpad.
//
// It is a thin wrapper around the SDK's `mountMockHostPage()`. On load it asks the backend (in local
// mode) for the panel's page URL with a mock idtoken made by the Python toolkit, and frames it in
// an iframe, answering the SDK's `init` and `get/user` like Dialpad does. Connect opens the fake
// authorize URL in a popup (a page marked as fake, with an Authorize button) and, like the desktop
// app, never replies, so the SDK's polling completes the connection once Authorize is pressed.
// The buttons in `dev/index.html` send a contact, start and end a call, and switch light and dark.
// Playwright tests drive the same host through `window.mockHost`.
import {
  makeCall,
  makeContact,
  mountMockHostPage,
  type MockHostPage,
} from '@dialpad/dialapp-external-sdk/testing';

declare global {
  interface Window {
    /** The mock host, for browser tests: `page.evaluate(() => window.mockHost?.received)`. */
    mockHost?: MockHostPage;
  }
}

/** Where the backend runs in local mode; the backend allows this page's origin by CORS. */
const BACKEND = 'http://localhost:8000';

const response = await fetch(`${BACKEND}/dev/frame-url`);
const { url } = (await response.json()) as { url: string };

const host = mountMockHostPage({
  src: url,
  container: document.getElementById('panel') ?? undefined,
});

window.mockHost = host;

/** The theme the host is showing; the toggle button flips it. */
let mode: 'light' | 'dark' = 'light';

/** Run `handler` when the dev page's button with this id is clicked. */
function onClick(id: string, handler: () => void): void {
  document.getElementById(id)?.addEventListener('click', handler);
}

onClick('send-contact', () => {
  host.sendContact(
    makeContact({
      displayName: 'Pat Customer',
      primaryPhone: '+1 555 0199',
      phones: ['+1 555 0199'],
      primaryEmail: 'pat@example.com',
      emails: ['pat@example.com'],
    }),
  );
});
onClick('start-call', () => {
  host.sendCall(makeCall({ state: 'ringing' }));
});
onClick('end-call', () => {
  host.sendCall(makeCall({ state: 'hangup' }));
});
onClick('toggle-theme', () => {
  mode = mode === 'light' ? 'dark' : 'light';
  host.setTheme({ mode });
});
