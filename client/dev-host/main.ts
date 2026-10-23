// The dev host: a stand-in for Dialpad, for running the iframe panel locally without Dialpad.
//
// It is a thin wrapper around the SDK's `mountMockHostPage()`. On load it asks the server (in local
// mode) for the iframe panel's page URL with a mock idtoken made by `server/acme_dialpad_rightbar/idtoken.py`, and frames it in
// an iframe, at the right sidebar's width or, with `?dpe`, at DPE's, answering the SDK's `init` and
// `get/user` like Dialpad does. Connect opens the fake
// authorize URL in a popup (a page marked as fake, with an Authorize button) and, like the desktop
// app, never replies, so the SDK's polling completes the connection once Authorize is pressed.
// The first of three contacts is open when the iframe panel starts, as when Dialpad opens the iframe panel for a
// contact. The buttons in `dev-host/index.html` cycle to the next contact, step a call through its
// states, switch light and dark, and disconnect the way Dialpad's panel menu does. Every toast the
// panel shows is listed under the panel, since Dialpad would show them outside it, and so is the
// record the panel linked, which Dialpad would show as a "View <type>" button in the panel header.
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

/** Where the server runs in local mode; the server allows this page's origin by CORS. */
const SERVER = 'http://localhost:8000';

const response = await fetch(`${SERVER}/dev/frame-url`);
const { url } = (await response.json()) as { url: string };

/**
 * The Dialpad contacts the "Change contact" button cycles through. The first is open from the
 * start, so the iframe panel shows a contact as soon as the user connects, like a real Dialpad.
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

/**
 * The panel's width: the right sidebar's default, or with `?dpe` in the URL Dialpad Everywhere's
 * 250 pixels, where the app's CSS scales itself down.
 */
const dpe = new URLSearchParams(window.location.search).has('dpe');
const panelName = dpe ? 'DPE (250 px)' : 'right sidebar (318 px)';
const panelNameElement = document.getElementById('panel-name');
if (panelNameElement) {
  panelNameElement.textContent = panelName;
}

const host = mountMockHostPage({
  src: url,
  container: document.getElementById('panel') ?? undefined,
  contact: CONTACTS[contactIndex],
  width: dpe ? 250 : 318,
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
 * the iframe panel's contact differ from the call's, so the iframe panel shows both.
 */
let callContact = CONTACTS[0];

/** The theme the host is showing; the toggle button flips it. */
let mode: 'light' | 'dark' = 'light';

/** Redraw the list of toasts under the panel from what the mock host has received. */
function showToasts(): void {
  const list = document.getElementById('toasts');
  if (!list) {
    return;
  }
  list.replaceChildren(
    ...host.received.toasts.map((toast) => {
      const item = document.createElement('li');
      // textContent, never innerHTML: the text comes from the app in the iframe.
      item.textContent = `${toast.type}: ${toast.text}`;
      return item;
    }),
  );
}

/**
 * Redraw the record the panel linked, as the link Dialpad's header button would open, or "None".
 * Only an http(s) URL becomes a link, since the URL comes from the app in the iframe.
 */
function showLinkedRecord(): void {
  const element = document.getElementById('linked-record');
  if (!element) {
    return;
  }
  const record = host.received.linkedRecord;
  if (!record) {
    element.textContent = 'None';
    return;
  }
  const label = `View ${record.type}`;
  // The URL constructor rather than `URL.canParse`, which Chrome added only in 120.
  let isWebUrl = false;
  try {
    isWebUrl = ['http:', 'https:'].includes(new URL(record.url).protocol);
  } catch {
    // Not a URL; shown as text below.
  }
  if (!isWebUrl) {
    element.textContent = `${label}: ${record.url}`;
    return;
  }
  const link = document.createElement('a');
  link.href = record.url;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  link.textContent = label;
  element.replaceChildren(link, ` (${record.url})`);
}

// The mock host's own listener (added by `mountMockHostPage`) runs first and records the toast or
// the linked record, so by the time these run `host.received` is current.
window.addEventListener('message', showToasts);
window.addEventListener('message', showLinkedRecord);

/** Run `handler` when the dev host's button with this id is clicked. */
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
onClick('disconnect-from-menu', () => {
  host.trigger('disconnect');
});
onClick('toggle-theme', () => {
  mode = mode === 'light' ? 'dark' : 'light';
  host.setTheme({ mode });
});
