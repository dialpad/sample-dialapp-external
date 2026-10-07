// The dev page: a stand-in for Dialpad, for running the panel locally without Dialpad.
//
// It is a thin wrapper around the SDK's `mountMockHostPage()`. On load it asks the backend (in local
// mode) for the panel's page URL with a mock idtoken made by the Python toolkit, and frames it in
// an iframe, answering the SDK's `init` and `get/user` like Dialpad does. Connect opens the fake
// authorize URL in a popup (a page marked as fake, with an Authorize button) and, like the desktop
// app, never replies, so the SDK's polling completes the connection once Authorize is pressed.
// The first of three contacts is open when the panel starts, as when Dialpad opens the panel for a
// contact. The buttons in `dev/index.html` cycle to the next contact, step a call through its
// states, and switch light and dark.
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

/**
 * The Dialpad contacts the "Change contact" button cycles through. The first is open from the
 * start, so the panel shows a contact as soon as the user connects, like a real Dialpad.
 */
const CONTACTS = [
  makeContact({
    id: '4800000000000001',
    displayName: 'Pat Customer',
    firstName: 'Pat',
    lastName: 'Customer',
    companyName: 'Customer Co',
    jobTitle: 'Buyer',
    primaryPhone: '+1 555 0199',
    phones: ['+1 555 0199'],
    primaryEmail: 'pat@example.com',
    emails: ['pat@example.com'],
  }),
  makeContact({
    id: '4800000000000002',
    displayName: 'Sam Prospect',
    firstName: 'Sam',
    lastName: 'Prospect',
    companyName: 'Prospect Inc',
    jobTitle: 'Founder',
    primaryPhone: '+1 555 0142',
    phones: ['+1 555 0142', '+1 555 0143'],
    primaryEmail: 'sam@example.com',
    emails: ['sam@example.com'],
  }),
  makeContact({
    id: '4800000000000003',
    displayName: 'Robin Partner',
    firstName: 'Robin',
    lastName: 'Partner',
    companyName: 'Partner LLC',
    jobTitle: null,
    primaryPhone: '+1 555 0177',
    phones: ['+1 555 0177'],
    primaryEmail: 'robin@example.com',
    emails: ['robin@example.com', 'robin@partner.example.com'],
  }),
];

/** Which of `CONTACTS` the host currently has open. */
let contactIndex = 0;

const host = mountMockHostPage({
  src: url,
  container: document.getElementById('panel') ?? undefined,
  contact: CONTACTS[contactIndex],
});

window.mockHost = host;

/**
 * The states the "Change call state" button steps a call through, in order: ringing, connected and
 * ended (`hangup`, which is what Dialpad sends). After ended, the next click is a new call
 * ringing: Dialpad never reports "no call" once a call has been reported, so neither does this.
 */
const CALL_STATES = ['ringing', 'connected', 'hangup'] as const;

/** Which of `CALL_STATES` the host last sent; -1 until the first click, when there is no call. */
let callStateIndex = -1;

/**
 * The contact of the current call. A new call takes the contact open when it starts, as Dialpad
 * opens the caller's contact in the right bar. Pressing "Change contact" during the call then makes
 * the panel's contact differ from the call's, so the panel shows both.
 */
let callContact = CONTACTS[0];

/** The theme the host is showing; the toggle button flips it. */
let mode: 'light' | 'dark' = 'light';

/** Run `handler` when the dev page's button with this id is clicked. */
function onClick(id: string, handler: () => void): void {
  document.getElementById(id)?.addEventListener('click', handler);
}

onClick('change-contact', () => {
  contactIndex = (contactIndex + 1) % CONTACTS.length;
  host.sendContact(CONTACTS[contactIndex] ?? null);
});
onClick('change-call-state', () => {
  callStateIndex = (callStateIndex + 1) % CALL_STATES.length;
  const state = CALL_STATES[callStateIndex];
  if (state) {
    if (state === 'ringing') {
      callContact = CONTACTS[contactIndex];
    }
    host.sendCall(makeCall({ state, contact: callContact }));
  }
});
onClick('toggle-theme', () => {
  mode = mode === 'light' ? 'dark' : 'light';
  host.setTheme({ mode });
});
