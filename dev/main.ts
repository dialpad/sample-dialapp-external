// The dev page: a thin wrapper around the SDK's `mountMockHostPage()`. The backend, in local mode,
// hands out a page URL carrying a mock idtoken made by the Python toolkit.
import {
  makeCall,
  makeContact,
  mountMockHostPage,
} from '@dialpad/dialapp-external-sdk/testing';

const BACKEND = 'http://localhost:8000';

const response = await fetch(`${BACKEND}/dev/frame-url`);
const { url } = (await response.json()) as { url: string };

const host = mountMockHostPage({
  src: url,
  container: document.getElementById('panel') ?? undefined,
});

let mode: 'light' | 'dark' = 'light';

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
