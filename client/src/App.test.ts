// Every state of the iframe panel, against the SDK's mock host and its clock: Dialpad is `createMockHost()`,
// the server is a fetch function, and time moves with `host.advance()`.
import {
  type FetchLike,
  type Rightbar,
  type RightbarOptions,
  type User,
} from '@dialpad/dialapp-external-sdk';
import { rightbarPlugin } from '@dialpad/dialapp-external-sdk/vue';
import {
  createMockHost,
  makeCall,
  makeContact,
  makePageData,
  makeUser,
} from '@dialpad/dialapp-external-sdk/testing';
import { flushPromises, mount } from '@vue/test-utils';
import { initDialtoneTheme, setMode } from '@dialpad/dialtone/themes/config';
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type MockInstance,
} from 'vitest';

import { api, sessionExpired } from './api';
import App from './App.vue';
import { bootstrap } from './bootstrap';

// Dialtone's theme functions write to the document; here only the calls matter.
vi.mock('@dialpad/dialtone/themes/config', () => ({
  initDialtoneTheme: vi.fn(),
  setMode: vi.fn(),
}));

const AUTHORIZE_URL = 'https://acme.example.com/oauth/fake-authorize?state=s';

/** A JSON response, as the Acme server would send one. */
function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

/** The server's `external_connection`, in the wire format: one OAuth client, `acme-for-dialpad`. */
function externalConnection(connected: boolean) {
  return {
    connected,
    authorization_urls: { 'acme-for-dialpad': AUTHORIZE_URL },
    name: 'acme-for-dialpad',
    scopes: connected ? ['contacts.read'] : [],
  };
}

/**
 * A fake Acme server as a `fetch` function, recording every call it gets.
 *
 * `mode` decides how it answers: `not_connected` or `connected` (an `external_connection` body),
 * `network` (the request throws), or `server_error` (a 500). `ext-disconnect` answers 204 and, when
 * it succeeds, flips the server to `not_connected`, as clearing the cookie does for the real one.
 */
function fakeServer() {
  const server = {
    mode: 'not_connected' as
      'not_connected' | 'connected' | 'network' | 'server_error',
    calls: [] as { method: string; path: string }[],
    fetch: vi.fn<FetchLike>((input, init) => {
      const path = new URL(
        input instanceof Request ? input.url : String(input),
        'https://acme.example.com',
      ).pathname;
      server.calls.push({ method: init?.method ?? 'GET', path });
      if (path.endsWith('/ext-disconnect')) {
        // The server answers 204 with no body; a later check then says "not connected".
        if (server.mode === 'network') {
          return Promise.reject(new TypeError('Failed to fetch'));
        }
        if (server.mode === 'server_error') {
          return Promise.resolve(json({ code: 'oops', message: 'oops' }, 500));
        }
        server.mode = 'not_connected';
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      switch (server.mode) {
        case 'network':
          return Promise.reject(new TypeError('Failed to fetch'));
        case 'server_error':
          return Promise.resolve(json({ code: 'oops', message: 'oops' }, 500));
        case 'connected':
          return Promise.resolve(json(externalConnection(true)));
        default:
          return Promise.resolve(json(externalConnection(false)));
      }
    }),
  };
  return server;
}

/** The rows the server's `POST /api/contact` answers with: non-empty fields, text prefixed "Acme ". */
function acmeRows(contact: Record<string, unknown>) {
  const acme = (value: unknown) =>
    typeof value === 'string' ? `Acme ${value}` : String(value);
  return Object.entries(contact)
    .filter(
      ([, value]) =>
        value !== null &&
        value !== undefined &&
        value !== '' &&
        !(Array.isArray(value) && value.length === 0),
    )
    .map(([label, value]) => ({
      label,
      value: Array.isArray(value)
        ? (value as unknown[]).map(acme).join(', ')
        : acme(value),
    }));
}

/** The fake record page's URL for a contact id, as the fake server answers it. */
function recordOf(id: string) {
  return { type: 'Contact', url: `https://acme.example.com/records/${id}` };
}

/** The record the server answers with for a contact: its fake record page, or null without an id. */
function acmeRecord(contact: Record<string, unknown>) {
  return typeof contact.id === 'string' && contact.id !== ''
    ? recordOf(contact.id)
    : null;
}

/**
 * A fake of the server's `POST /api/contact`, standing in for the global `fetch` the panel's own
 * requests (the ones made through `api()`) use, and recording every request it gets.
 *
 * `mode` decides how it answers: `ok` (the Acme'd rows and the record at once), `empty` (no rows),
 * `error` (a 500), or `hold` (each answer waits in `held` until a test calls its `respond`, to
 * answer out of order).
 */
function fakeContactApi() {
  const contactApi = {
    mode: 'ok' as 'ok' | 'empty' | 'error' | 'hold',
    requests: [] as { method: string; path: string; body: unknown }[],
    held: [] as { contact: Record<string, unknown>; respond: () => void }[],
    fetch: vi.fn(
      (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
        const path = new URL(
          input instanceof Request ? input.url : String(input),
          'https://acme.example.com',
        ).pathname;
        const body = (
          typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
        ) as { contact: Record<string, unknown> } | undefined;
        contactApi.requests.push({ method: init?.method ?? 'GET', path, body });
        if (contactApi.mode === 'error' || !body) {
          return Promise.resolve(json({ code: 'oops', message: 'oops' }, 500));
        }
        const answer = () =>
          json({
            fields: contactApi.mode === 'empty' ? [] : acmeRows(body.contact),
            record: acmeRecord(body.contact),
          });
        if (contactApi.mode === 'hold') {
          return new Promise<Response>((resolve) => {
            contactApi.held.push({
              contact: body.contact,
              respond: () => {
                resolve(answer());
              },
            });
          });
        }
        return Promise.resolve(answer());
      },
    ),
  };
  return contactApi;
}

/** Every component mounted by `setup`, so `afterEach` can unmount them. */
const mounted: { unmount(): void }[] = [];

// Vue reports bad props (for example an invalid Dialtone `kind`) as console warnings.
let warnings: MockInstance<typeof console.warn>;

beforeEach(() => {
  warnings = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
});

/**
 * Start the iframe panel against a mock Dialpad and a fake Acme server, like a user opening it.
 *
 * `connected` is what the page data says at load (a connected user's cookie, or not); `mode` is how
 * the fake server answers connection checks from then on; `user` is what Dialpad's `get/user`
 * answers. Returns the host (to send contacts and move the clock), the server (to change its mode
 * and see its calls) and the mounted wrapper.
 */
async function setup({
  connected = false,
  mode = 'not_connected',
  user,
  app = null,
}: {
  connected?: boolean;
  mode?: ReturnType<typeof fakeServer>['mode'];
  /** What Dialpad's `get/user` answers: the default user, a user, or `null` for none. */
  user?: User | null;
  /** What the server put in the page data's `app` field, for example the demo API call's result. */
  app?: Record<string, unknown> | null;
} = {}) {
  const host = createMockHost(user === undefined ? {} : { user });
  const server = fakeServer();
  const contactApi = fakeContactApi();
  vi.stubGlobal('fetch', contactApi.fetch);
  server.mode = mode;
  const root = document.createElement('div');
  document.body.append(root);
  const rightbar = await host.createRightbar({
    heightRoot: root,
    fetch: server.fetch,
    pageData: makePageData({
      app,
      externalConnection: {
        connected,
        name: 'acme-for-dialpad',
        scopes: connected ? ['contacts.read'] : [],
        authorizationUrls: { 'acme-for-dialpad': AUTHORIZE_URL },
      },
    }),
  });
  const wrapper = mount(App, {
    global: { plugins: [[rightbarPlugin, rightbar]] },
    attachTo: root,
  });
  mounted.push(wrapper);
  await host.settle();
  return { host, server, contactApi, wrapper, rightbar };
}

afterEach(() => {
  const vueWarnings = warnings.mock.calls
    .map((call) => String(call[0]))
    .filter((message) => message.includes('[Vue warn]'));
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  if (vueWarnings.length > 0) {
    throw new Error(`Vue warnings:\n${vueWarnings.join('\n')}`);
  }
  for (const wrapper of mounted.splice(0)) {
    wrapper.unmount();
  }
  sessionExpired.value = false;
  document.body.innerHTML = '';
});

/**
 * Make Dialpad reject every toast, and return a counter of how many were asked for.
 *
 * A plain function, not a `vi.fn()`: a spy attaches its own handler to the promise it returns, which
 * would hide an unhandled rejection from `unhandledRejectionsDuring`.
 */
function rejectToasts(rightbar: Rightbar): { asked: number } {
  const counter = { asked: 0 };
  Object.assign(rightbar, {
    showToast: () => {
      counter.asked += 1;
      return Promise.reject(new Error('Dialpad did not answer'));
    },
  });
  return counter;
}

/** Make Dialpad reject every `linkRecord`, and return a counter of how many were asked for. */
function rejectLinks(rightbar: Rightbar): { asked: number } {
  const counter = { asked: 0 };
  Object.assign(rightbar, {
    linkRecord: () => {
      counter.asked += 1;
      return Promise.reject(new Error('Dialpad did not answer'));
    },
  });
  return counter;
}

/** Run `action`, then report how many promise rejections nobody handled while it ran. */
async function unhandledRejectionsDuring(
  action: () => Promise<void>,
): Promise<number> {
  const unhandled = vi.fn();
  process.on('unhandledRejection', unhandled);
  try {
    await action();
    // Node reports a rejection nobody handled once the current turn's microtasks are done.
    await new Promise((resolve) => setTimeout(resolve, 0));
  } finally {
    process.off('unhandledRejection', unhandled);
  }
  return unhandled.mock.calls.length;
}

describe('Connect gate', () => {
  it('shows Connect when not connected', async () => {
    const { wrapper } = await setup();

    expect(wrapper.find('[data-testid="connect-gate"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Connect your Acme account');
    expect(wrapper.get('[data-testid="connect-button"]').text()).toBe(
      'Connect',
    );
    expect(wrapper.find('[data-testid="connected-view"]').exists()).toBe(false);
  });

  it('asks Dialpad to open the authorize URL and shows connecting while it polls', async () => {
    const { wrapper, host } = await setup();

    await wrapper.get('[data-testid="connect-button"]').trigger('click');
    await host.settle();

    expect(host.received.authorizeRequests).toEqual([AUTHORIZE_URL]);
    expect(wrapper.get('[role="status"]').text()).toContain('Waiting');
    expect(
      wrapper.get('[data-testid="connect-button"]').attributes('disabled'),
    ).toBeDefined();
  });

  it('completes Connect by polling: the first check is after 7 seconds', async () => {
    const { wrapper, host, server } = await setup();
    await wrapper.get('[data-testid="connect-button"]').trigger('click');
    await host.settle();
    server.mode = 'connected';

    await host.advance(7_000);
    await flushPromises();
    await host.settle();

    expect(wrapper.find('[data-testid="connected-view"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="connect-gate"]').exists()).toBe(false);
    expect(host.received.toasts).toEqual([
      { text: 'Connected to Acme CRM', type: 'success' },
    ]);
  });

  it('still completes Connect when Dialpad rejects the toast', async () => {
    const { wrapper, host, server, rightbar } = await setup();
    const toasts = rejectToasts(rightbar);
    await wrapper.get('[data-testid="connect-button"]').trigger('click');
    await host.settle();
    server.mode = 'connected';

    const unhandled = await unhandledRejectionsDuring(async () => {
      await host.advance(7_000);
      await flushPromises();
    });

    expect(toasts.asked).toBe(1);
    expect(unhandled).toBe(0);
    expect(warnings).toHaveBeenCalledWith(
      "Dialpad didn't show the toast",
      expect.any(Error),
    );
    expect(wrapper.find('[data-testid="connected-view"]').exists()).toBe(true);
  });

  it('shows the timeout state with Try again when polling gives up after 2 minutes', async () => {
    const { wrapper, host } = await setup();
    await wrapper.get('[data-testid="connect-button"]').trigger('click');

    await host.advance(120_000);
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toContain(
      "didn't respond in time",
    );
    expect(wrapper.get('[data-testid="connect-button"]').text()).toBe(
      'Try again',
    );
  });

  it.each<[string, 'network' | 'server_error', string]>([
    ['the connection check throws', 'network', "couldn't reach Acme"],
    ['the server answers non-2xx', 'server_error', 'Something went wrong'],
  ])(
    'shows the failed state with Try again when %s',
    async (_when, mode, message) => {
      const { wrapper } = await setup({ mode });

      expect(wrapper.get('[role="alert"]').text()).toContain(message);
      expect(wrapper.get('[data-testid="connect-button"]').text()).toBe(
        'Try again',
      );
    },
  );

  it('keeps polling through a failed check and still completes Connect', async () => {
    const { wrapper, host, server } = await setup();
    await wrapper.get('[data-testid="connect-button"]').trigger('click');
    server.mode = 'network';
    await host.advance(7_000);
    server.mode = 'connected';

    await host.advance(5_000);
    await flushPromises();

    expect(wrapper.find('[data-testid="connected-view"]').exists()).toBe(true);
  });

  it('stops waiting when the user disconnects from the host menu while Connect is polling', async () => {
    const { wrapper, host } = await setup();
    await wrapper.get('[data-testid="connect-button"]').trigger('click');
    expect(wrapper.find('[role="status"]').exists()).toBe(true);

    host.trigger('disconnect');
    await host.settle();
    await flushPromises();

    expect(wrapper.find('[role="status"]').exists()).toBe(false);
    expect(
      wrapper.get('[data-testid="connect-button"]').attributes('disabled'),
    ).toBeUndefined();
  });

  it('restarts Connect when Try again is clicked', async () => {
    const { wrapper, host, server } = await setup();
    await wrapper.get('[data-testid="connect-button"]').trigger('click');
    await host.advance(120_000);
    await flushPromises();
    server.mode = 'connected';

    await wrapper.get('[data-testid="connect-button"]').trigger('click');
    await host.advance(7_000);
    await flushPromises();

    expect(host.received.authorizeRequests).toHaveLength(2);
    expect(wrapper.find('[data-testid="connected-view"]').exists()).toBe(true);
  });
});

describe('Connected view', () => {
  it("shows the user from Dialpad's get/user, not from the page, and the scopes", async () => {
    const { wrapper, host } = await setup({ connected: true });

    expect(host.received.toasts).toEqual([]);
    const card = wrapper.get('[data-testid="user-card"]').text();
    expect(card).toContain('Jane Agent');
    expect(card).toContain('Support Agent');
    expect(card).toContain('jane.agent@example.com · +15555550100');
    expect(card).toContain('user 5432 · company 12345 · office 54321');
    expect(card).toContain('Licenses: agents');
    expect(card).toContain('Available · On duty · Online');
    expect(card).not.toContain('api_key');
    expect(wrapper.get('[data-testid="scopes"]').text()).toContain(
      'contacts.read',
    );
  });

  it('shows admin and do-not-disturb flags only when they are set', async () => {
    const { wrapper } = await setup({
      connected: true,
      user: makeUser({ isAdmin: true, doNotDisturb: true, isAvailable: false }),
    });

    const card = wrapper.get('[data-testid="user-card"]').text();
    expect(card).toContain('Admin');
    expect(card).toContain('Do not disturb');
    expect(card).not.toContain('Available');
  });

  it('copes with Dialpad sending no user', async () => {
    const { wrapper } = await setup({ connected: true, user: null });

    expect(wrapper.get('[data-testid="user-card"]').text()).toContain(
      "didn't send your user details",
    );
    expect(wrapper.find('[data-testid="connected-view"]').exists()).toBe(true);
  });

  it("asks the server for the CRM view of the contact Dialpad sends, shows every field Acme'd, omitting empty ones, and links its record", async () => {
    const { wrapper, host, contactApi } = await setup({ connected: true });
    const sent = makeContact({
      id: '1',
      displayName: 'Pat Customer',
      primaryPhone: '+1 555 0199',
      phones: ['+1 555 0199'],
      emails: ['pat@example.com'],
      jobTitle: null,
    });

    host.sendContact(sent);
    await host.settle();
    await flushPromises();

    expect(contactApi.requests).toEqual([
      {
        method: 'POST',
        path: '/api/contact',
        body: { contact: JSON.parse(JSON.stringify(sent)) as unknown },
      },
    ]);
    const contact = wrapper.get('[data-testid="acme-contact"]').text();
    expect(contact).toContain('displayName');
    expect(contact).toContain('Acme Pat Customer');
    expect(contact).toContain('Acme +1 555 0199');
    expect(contact).toContain('Acme pat@example.com');
    expect(contact).not.toContain('jobTitle');
    expect(host.received.linkedRecord).toEqual(recordOf('1'));
  });

  it("shows the user the server fetched from Dialpad's API with the api key", async () => {
    const { wrapper } = await setup({
      connected: true,
      app: {
        dialpadApi: {
          status: 'ok',
          user: {
            id: 5432,
            displayName: 'Jane From Api',
            email: 'jane.api@example.com',
            state: 'active',
          },
        },
      },
    });

    const card = wrapper.get('[data-testid="dialpad-api-card"]').text();
    expect(card).toContain("From Dialpad's API");
    expect(card).toContain('Jane From Api');
    expect(card).toContain('jane.api@example.com');
    expect(card).toContain('user 5432 · active');
    expect(card).toContain('demo only');
  });

  it.each([
    ['unavailable', 'Dialpad API unavailable'],
    ['skipped', 'Skipped in local mode'],
  ])(
    "explains a %s call to Dialpad's API, and the iframe panel still works",
    async (status, message) => {
      const { wrapper } = await setup({
        connected: true,
        app: { dialpadApi: { status, user: null } },
      });

      expect(wrapper.get('[data-testid="dialpad-api-card"]').text()).toContain(
        message,
      );
      expect(wrapper.find('[data-testid="user-card"]').exists()).toBe(true);
    },
  );

  it.each([
    ['no app data', null],
    ['an unknown status', { dialpadApi: { status: 'weird', user: null } }],
    ['a malformed result', { dialpadApi: 'nope' }],
  ])('shows no API card for %s', async (_name, app) => {
    const { wrapper } = await setup({ connected: true, app });

    expect(wrapper.find('[data-testid="dialpad-api-card"]').exists()).toBe(
      false,
    );
    expect(wrapper.find('[data-testid="connected-view"]').exists()).toBe(true);
  });

  it('shows that the contact is loading until the server answers, then the rows', async () => {
    const { wrapper, host, contactApi } = await setup({ connected: true });
    contactApi.mode = 'hold';

    host.sendContact(makeContact({ displayName: 'Pat Customer' }));
    await host.settle();
    await flushPromises();
    const loading = wrapper.get('[data-testid="acme-contact"]').text();
    contactApi.held[0]?.respond();
    await flushPromises();

    expect(loading).toContain('Loading the contact');
    expect(loading).not.toContain('Acme Pat Customer');
    expect(wrapper.get('[data-testid="acme-contact"]').text()).toContain(
      'Acme Pat Customer',
    );
  });

  it.each<
    [string, 'error' | 'empty', string, { text: string; type: string }[]]
  >([
    [
      'cannot answer',
      'error',
      "Couldn't load the contact",
      [{ text: "Couldn't load the contact from Acme CRM", type: 'error' }],
    ],
    [
      'answers with no rows',
      'empty',
      'There are no details for this contact',
      [],
    ],
  ])(
    'says so when the server %s for the contact, and the rest of the panel works',
    async (_when, mode, message, toasts) => {
      const { wrapper, host, contactApi } = await setup({ connected: true });
      contactApi.mode = mode;

      host.sendContact(makeContact({ displayName: 'Pat Customer' }));
      await host.settle();
      await flushPromises();

      expect(wrapper.get('[data-testid="acme-contact"]').text()).toContain(
        message,
      );
      expect(wrapper.find('[data-testid="user-card"]').exists()).toBe(true);
      expect(host.received.toasts).toEqual(toasts);
    },
  );

  it('still shows the failed lookup when Dialpad rejects the error toast', async () => {
    const { wrapper, host, contactApi, rightbar } = await setup({
      connected: true,
    });
    const toasts = rejectToasts(rightbar);
    contactApi.mode = 'error';

    const unhandled = await unhandledRejectionsDuring(async () => {
      host.sendContact(makeContact({ displayName: 'Pat Customer' }));
      await host.settle();
      await flushPromises();
    });

    expect(toasts.asked).toBe(1);
    expect(unhandled).toBe(0);
    expect(warnings).toHaveBeenCalledWith(
      'The contact lookup failed',
      expect.any(Error),
    );
    expect(warnings).toHaveBeenCalledWith(
      "Dialpad didn't show the toast",
      expect.any(Error),
    );
    expect(wrapper.get('[data-testid="acme-contact"]').text()).toContain(
      "Couldn't load the contact",
    );
  });

  it('still shows the contact when Dialpad rejects the link', async () => {
    const { wrapper, host, rightbar } = await setup({ connected: true });
    const links = rejectLinks(rightbar);

    const unhandled = await unhandledRejectionsDuring(async () => {
      host.sendContact(makeContact({ id: '1', displayName: 'Pat Customer' }));
      await host.settle();
      await flushPromises();
    });

    expect(links.asked).toBe(1);
    expect(unhandled).toBe(0);
    expect(warnings).toHaveBeenCalledWith(
      "Dialpad didn't link the record",
      expect.any(Error),
    );
    expect(wrapper.get('[data-testid="acme-contact"]').text()).toContain(
      'Acme Pat Customer',
    );
  });

  it('opens a new contact without disconnecting, and ignores a late answer for the earlier one', async () => {
    const { wrapper, host, contactApi } = await setup({ connected: true });
    contactApi.mode = 'hold';

    host.sendContact(makeContact({ id: '1', displayName: 'Pat Customer' }));
    await host.settle();
    host.sendContact(makeContact({ id: '2', displayName: 'Sam Prospect' }));
    await host.settle();
    await flushPromises();
    const linkedWhilePending = host.received.linkedRecord;
    contactApi.held[1]?.respond();
    await flushPromises();
    contactApi.held[0]?.respond();
    await host.settle();
    await flushPromises();

    const shown = wrapper.get('[data-testid="acme-contact"]').text();
    expect(shown).toContain('Acme Sam Prospect');
    expect(shown).not.toContain('Acme Pat Customer');
    expect(wrapper.find('[data-testid="connected-view"]').exists()).toBe(true);
    expect(linkedWhilePending).toBeNull();
    expect(host.received.linkedRecord).toEqual(recordOf('2'));
  });

  it('unlinks the record when the lookup for the next contact fails', async () => {
    const { host, contactApi } = await setup({ connected: true });
    host.sendContact(makeContact({ id: '1', displayName: 'Pat Customer' }));
    await host.settle();
    await flushPromises();
    const linked = host.received.linkedRecord;

    contactApi.mode = 'error';
    host.sendContact(makeContact({ id: '2', displayName: 'Sam Prospect' }));
    await host.settle();
    await flushPromises();

    expect(linked).toEqual(recordOf('1'));
    expect(host.received.linkedRecord).toBeNull();
  });

  it('shows no active call until Dialpad sends one, then follows it from ringing to connected to ended', async () => {
    const { wrapper, host } = await setup({ connected: true });
    expect(wrapper.get('[data-testid="call-card"]').text()).toContain(
      'No active call',
    );

    host.sendCall(
      makeCall({
        state: 'ringing',
        direction: 'inbound',
        externalNumber: '+15555550199',
      }),
    );
    await host.settle();
    await flushPromises();
    const ringing = wrapper.get('[data-testid="call-card"]').text();
    expect(ringing).toContain('Ringing');
    expect(ringing).toContain('inbound · +15555550199');

    host.sendCall(makeCall({ state: 'connected' }));
    await host.settle();
    await flushPromises();
    expect(wrapper.get('[data-testid="call-card"]').text()).toContain(
      'Connected',
    );

    host.sendCall(makeCall({ state: 'hangup' }));
    await host.settle();
    await flushPromises();
    expect(wrapper.get('[data-testid="call-card"]').text()).toContain('Ended');
  });

  it.each([
    [
      "the iframe panel's contact",
      makeContact({ id: '1', displayName: 'Pat Customer' }),
    ],
    ['no contact', null],
  ])(
    'shows no separate call contact section when the call has %s',
    async (_what, callContact) => {
      const { wrapper, host } = await setup({ connected: true });
      const pat = makeContact({ id: '1', displayName: 'Pat Customer' });

      host.sendContact(pat);
      host.sendCall(makeCall({ state: 'ringing', contact: callContact }));
      await host.settle();
      await flushPromises();

      expect(wrapper.find('[data-testid="call-contact"]').exists()).toBe(false);
      expect(wrapper.get('[data-testid="acme-contact"]').text()).toContain(
        'Acme Pat Customer',
      );
    },
  );

  it("shows the call's contact as well when it is a different contact, but links only the panel's", async () => {
    const { wrapper, host, contactApi } = await setup({ connected: true });
    contactApi.mode = 'hold';

    host.sendContact(makeContact({ id: '1', displayName: 'Pat Customer' }));
    host.sendCall(
      makeCall({
        state: 'ringing',
        contact: makeContact({ id: '2', displayName: 'Sam Prospect' }),
      }),
    );
    await host.settle();
    await flushPromises();
    // Answer the call contact's lookup last, so a link from it would be the one left.
    const sam = contactApi.held.find((held) => held.contact.id === '2');
    contactApi.held.find((held) => held.contact.id === '1')?.respond();
    await flushPromises();
    sam?.respond();
    await host.settle();
    await flushPromises();

    expect(sam).toBeDefined();
    expect(wrapper.get('[data-testid="call-contact"]').text()).toContain(
      'Acme Sam Prospect',
    );
    expect(wrapper.get('[data-testid="acme-contact"]').text()).toContain(
      'Acme Pat Customer',
    );
    expect(host.received.linkedRecord).toEqual(recordOf('1'));
  });

  it('asks for inline confirmation before disconnecting, and Cancel backs out', async () => {
    const { wrapper, server } = await setup({ connected: true });

    await wrapper.get('[data-testid="disconnect-button"]').trigger('click');
    expect(wrapper.text()).toContain('Disconnect Acme?');
    expect(server.calls.some((c) => c.path.endsWith('/ext-disconnect'))).toBe(
      false,
    );

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Cancel')
      ?.trigger('click');

    expect(wrapper.text()).not.toContain('Disconnect Acme?');
    expect(wrapper.find('[data-testid="disconnect-button"]').exists()).toBe(
      true,
    );
  });

  it('disconnects after confirmation and shows the Connect gate again', async () => {
    const { wrapper, host, server } = await setup({ connected: true });
    server.mode = 'connected';

    await wrapper.get('[data-testid="disconnect-button"]').trigger('click');
    await wrapper.get('[data-testid="disconnect-confirm"]').trigger('click');
    await host.settle();
    await flushPromises();
    await flushPromises();

    expect(server.calls).toContainEqual({
      method: 'POST',
      path: '/dialpad/ext-disconnect',
    });
    // The SDK then asks for fresh authorize URLs.
    const afterDisconnect = server.calls.slice(
      server.calls.findIndex((c) => c.path.endsWith('/ext-disconnect')) + 1,
    );
    expect(afterDisconnect).toContainEqual({
      method: 'GET',
      path: '/dialpad/ext-connection',
    });
    expect(wrapper.find('[data-testid="connect-gate"]').exists()).toBe(true);
    expect(host.received.toasts).toEqual([
      { text: 'Disconnected from Acme CRM', type: 'info' },
    ]);
  });

  it("shows the same toast and unlinks the record when the user disconnects from Dialpad's menu", async () => {
    const { wrapper, host, server } = await setup({ connected: true });
    server.mode = 'connected';
    host.sendContact(makeContact({ id: '1', displayName: 'Pat Customer' }));
    await host.settle();
    await flushPromises();
    const linked = host.received.linkedRecord;

    host.trigger('disconnect');
    await host.settle();
    await flushPromises();
    await host.settle();

    expect(wrapper.find('[data-testid="connect-gate"]').exists()).toBe(true);
    expect(host.received.toasts).toEqual([
      { text: 'Disconnected from Acme CRM', type: 'info' },
    ]);
    expect(linked).toEqual(recordOf('1'));
    expect(host.received.linkedRecord).toBeNull();
  });

  it('tells the user when Disconnect fails and stays connected', async () => {
    const { wrapper, host, server } = await setup({ connected: true });
    server.mode = 'server_error';

    await wrapper.get('[data-testid="disconnect-button"]').trigger('click');
    await wrapper.get('[data-testid="disconnect-confirm"]').trigger('click');
    await host.settle();
    await flushPromises();
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toContain(
      "couldn't disconnect",
    );
    expect(wrapper.find('[data-testid="connected-view"]').exists()).toBe(true);
    expect(host.received.toasts).toEqual([]);
  });
});

describe('Requests', () => {
  it('shows "reload the panel" when the server rejects the access token', async () => {
    const response = new Response('{}', { status: 401 });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(response);

    await api('/dialpad/connection');

    const { wrapper } = await setup();
    expect(wrapper.text()).toContain('Reload the panel');
  });
});

describe('Bootstrap errors', () => {
  /**
   * Run the real `bootstrap` into a fresh element, with the mock host standing in for Dialpad.
   *
   * `pageData` is whatever the (pretend) page embedded, valid or not, so tests can exercise how
   * the SDK reacts to bad page data. Returns the element so tests can read what was mounted.
   */
  async function bootstrapWith(
    host: ReturnType<typeof createMockHost>,
    pageData: unknown,
  ) {
    const root = document.createElement('div');
    document.body.append(root);
    await bootstrap(root, (options: RightbarOptions) =>
      host.createRightbar({ ...options, pageData: pageData as never }),
    );
    return root;
  }

  it('tells the user to open the iframe panel from Dialpad on bad_page_data', async () => {
    const host = createMockHost();

    const root = await bootstrapWith(host, { not: 'page data' });

    expect(root.textContent).toContain('Open this panel from Dialpad');
    expect(warnings).toHaveBeenCalledWith(
      'The panel could not start',
      'bad_page_data',
      expect.any(String),
    );
  });

  it('tells the user to open the iframe panel from Dialpad on init_timeout', async () => {
    const host = createMockHost({ init: 'never' });
    const root = document.createElement('div');
    document.body.append(root);

    const started = bootstrap(root, (options) =>
      host.createRightbar({ ...options, pageData: makePageData() }),
    );
    await host.advance(10_000);
    await started;

    expect(root.textContent).toContain('Open this panel from Dialpad');
    expect(warnings).toHaveBeenCalledWith(
      'The panel could not start',
      'init_timeout',
      expect.any(String),
    );
  });

  it("mounts the iframe panel and applies the host's theme at start and on change", async () => {
    vi.mocked(initDialtoneTheme).mockClear();
    vi.mocked(setMode).mockClear();
    const host = createMockHost({ theme: { mode: 'dark' } });

    const root = await bootstrapWith(host, makePageData());

    expect(root.textContent).toContain('Acme for Dialpad (demo)');
    expect(initDialtoneTheme).toHaveBeenCalledWith(expect.anything(), 'dark');

    host.setTheme({ mode: 'light' });
    await host.settle();

    expect(setMode).toHaveBeenLastCalledWith('light');
  });
});

describe("Dialpad's panel menu", () => {
  /**
   * Run the real `bootstrap`, with the mock host standing in for Dialpad and `server` for Acme.
   *
   * `connected` is what the page data says at load. Returns the SDK instance `bootstrap` created,
   * so a test can check the connection again.
   */
  async function start(
    host: ReturnType<typeof createMockHost>,
    server: ReturnType<typeof fakeServer>,
    connected: boolean,
    patch: (rightbar: Rightbar) => void = () => undefined,
  ): Promise<Rightbar> {
    const root = document.createElement('div');
    document.body.append(root);
    let created: Rightbar | undefined;
    await bootstrap(root, async (options) => {
      created = await host.createRightbar({
        ...options,
        fetch: server.fetch,
        pageData: makePageData({
          externalConnection: {
            connected,
            name: 'acme-for-dialpad',
            scopes: connected ? ['contacts.read'] : [],
            authorizationUrls: { 'acme-for-dialpad': AUTHORIZE_URL },
          },
        }),
      });
      patch(created);
      return created;
    });
    await host.settle();
    if (!created) {
      throw new Error('bootstrap never created the SDK');
    }
    return created;
  }

  it('is empty from the start while the user is not connected, then Disconnect once connected', async () => {
    const host = createMockHost();
    const server = fakeServer();

    const rightbar = await start(host, server, false);
    expect(host.received.menu).toEqual([]);

    server.mode = 'connected';
    await rightbar.refresh();
    await host.settle();
    expect(host.received.menu).toEqual(['disconnect']);
  });

  it('is Disconnect from the start when the panel opens connected, then empty after a disconnect', async () => {
    const host = createMockHost();
    const server = fakeServer();
    server.mode = 'connected';

    await start(host, server, true);
    expect(host.received.menu).toEqual(['disconnect']);

    host.trigger('disconnect');
    await host.settle();
    await flushPromises();
    await host.settle();
    expect(host.received.menu).toEqual([]);
  });

  it('logs a menu Dialpad rejects, without an unhandled rejection', async () => {
    const host = createMockHost();
    const server = fakeServer();

    const unhandled = await unhandledRejectionsDuring(async () => {
      await start(host, server, false, (rightbar) => {
        Object.assign(rightbar, {
          setMenu: () => Promise.reject(new Error('Dialpad did not answer')),
        });
      });
    });

    expect(unhandled).toBe(0);
    expect(warnings).toHaveBeenCalledWith(
      "Dialpad didn't set the panel menu",
      expect.any(Error),
    );
  });
});
