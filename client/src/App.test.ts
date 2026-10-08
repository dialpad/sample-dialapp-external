// Every state of the iframe panel, against the SDK's mock host and its clock: Dialpad is `createMockHost()`,
// the server is a fetch function, and time moves with `host.advance()`.
import {
  type FetchLike,
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

/** The server's `external_connection`, in the wire format: one OAuth client, `acme-crm`. */
function externalConnection(connected: boolean) {
  return {
    connected,
    authorization_urls: { 'acme-crm': AUTHORIZE_URL },
    name: 'acme-crm',
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

/**
 * A fake of the server's `POST /api/contact`, standing in for the global `fetch` the panel's own
 * requests (the ones made through `api()`) use, and recording every request it gets.
 *
 * `mode` decides how it answers: `ok` (the Acme'd rows at once), `empty` (no rows), `error` (a 500),
 * or `hold` (each answer waits in `held` until a test calls its `respond`, to answer out of order).
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
        name: 'acme-crm',
        scopes: connected ? ['contacts.read'] : [],
        authorizationUrls: { 'acme-crm': AUTHORIZE_URL },
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

    expect(wrapper.find('[data-testid="connected-view"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="connect-gate"]').exists()).toBe(false);
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

  it('shows the network state with Try again when the connection check throws', async () => {
    const { wrapper } = await setup({ mode: 'network' });

    expect(wrapper.get('[role="alert"]').text()).toContain(
      "couldn't reach Acme",
    );
    expect(wrapper.get('[data-testid="connect-button"]').text()).toBe(
      'Try again',
    );
  });

  it('shows the request-failed state with Try again on a non-2xx response', async () => {
    const { wrapper } = await setup({ mode: 'server_error' });

    expect(wrapper.get('[role="alert"]').text()).toContain(
      'Something went wrong',
    );
    expect(wrapper.get('[data-testid="connect-button"]').text()).toBe(
      'Try again',
    );
  });

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
  it("shows the user from Dialpad's get/user, not from the page", async () => {
    const { wrapper } = await setup({ connected: true });

    const card = wrapper.get('[data-testid="user-card"]').text();
    expect(card).toContain('Jane Agent');
    expect(card).toContain('Support Agent');
    expect(card).toContain('jane.agent@example.com · +15555550100');
    expect(card).toContain('user 5432 · company 12345 · office 54321');
    expect(card).toContain('Licenses: agents');
    expect(card).toContain('Available · On duty · Online');
    expect(card).not.toContain('api_key');
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

  it('shows the scopes of the connection', async () => {
    const { wrapper } = await setup({ connected: true });

    expect(wrapper.get('[data-testid="scopes"]').text()).toContain(
      'contacts.read',
    );
  });

  it("shows the contact Dialpad sends with every field Acme'd, omitting empty ones", async () => {
    const { wrapper, host } = await setup({ connected: true });

    host.sendContact(
      makeContact({
        displayName: 'Pat Customer',
        primaryPhone: '+1 555 0199',
        phones: ['+1 555 0199'],
        emails: ['pat@example.com'],
        jobTitle: null,
      }),
    );
    await host.settle();
    await flushPromises();

    const contact = wrapper.get('[data-testid="acme-contact"]').text();
    expect(contact).toContain('displayName');
    expect(contact).toContain('Acme Pat Customer');
    expect(contact).toContain('Acme +1 555 0199');
    expect(contact).toContain('Acme pat@example.com');
    expect(contact).not.toContain('jobTitle');
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

  it("says so when the server could not reach Dialpad's API, and the iframe panel still works", async () => {
    const { wrapper } = await setup({
      connected: true,
      app: { dialpadApi: { status: 'unavailable', user: null } },
    });

    expect(wrapper.get('[data-testid="dialpad-api-card"]').text()).toContain(
      'Dialpad API unavailable',
    );
    expect(wrapper.find('[data-testid="user-card"]').exists()).toBe(true);
  });

  it("explains that local mode doesn't call Dialpad's API", async () => {
    const { wrapper } = await setup({
      connected: true,
      app: { dialpadApi: { status: 'skipped', user: null } },
    });

    expect(wrapper.get('[data-testid="dialpad-api-card"]').text()).toContain(
      'Skipped in local mode',
    );
  });

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

  it('asks the server for the CRM view of the contact, with the contact as the body', async () => {
    const { host, contactApi } = await setup({ connected: true });
    const pat = makeContact({ id: '1', displayName: 'Pat Customer' });

    host.sendContact(pat);
    await host.settle();
    await flushPromises();

    expect(contactApi.requests).toEqual([
      {
        method: 'POST',
        path: '/api/contact',
        body: { contact: JSON.parse(JSON.stringify(pat)) as unknown },
      },
    ]);
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

  it('says so when the server cannot answer for the contact, and the rest of the panel works', async () => {
    const { wrapper, host, contactApi } = await setup({ connected: true });
    contactApi.mode = 'error';

    host.sendContact(makeContact({ displayName: 'Pat Customer' }));
    await host.settle();
    await flushPromises();

    expect(wrapper.get('[data-testid="acme-contact"]').text()).toContain(
      "Couldn't load the contact",
    );
    expect(wrapper.find('[data-testid="user-card"]').exists()).toBe(true);
  });

  it('ignores a late answer for an earlier contact once a newer contact is open', async () => {
    const { wrapper, host, contactApi } = await setup({ connected: true });
    contactApi.mode = 'hold';

    host.sendContact(makeContact({ id: '1', displayName: 'Pat Customer' }));
    await host.settle();
    host.sendContact(makeContact({ id: '2', displayName: 'Sam Prospect' }));
    await host.settle();
    await flushPromises();
    contactApi.held[1]?.respond();
    await flushPromises();
    contactApi.held[0]?.respond();
    await flushPromises();

    const shown = wrapper.get('[data-testid="acme-contact"]').text();
    expect(shown).toContain('Acme Sam Prospect');
    expect(shown).not.toContain('Acme Pat Customer');
  });

  it('says there are no details when the server answers with no rows', async () => {
    const { wrapper, host, contactApi } = await setup({ connected: true });
    contactApi.mode = 'empty';

    host.sendContact(makeContact({ displayName: 'Pat Customer' }));
    await host.settle();
    await flushPromises();

    expect(wrapper.get('[data-testid="acme-contact"]').text()).toContain(
      'There are no details for this contact',
    );
  });

  it('shows no active call until Dialpad sends one', async () => {
    const { wrapper } = await setup({ connected: true });

    expect(wrapper.get('[data-testid="call-card"]').text()).toContain(
      'No active call',
    );
  });

  it('follows a call from ringing to connected to ended', async () => {
    const { wrapper, host } = await setup({ connected: true });

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

  it("shows one contact section when the call's contact is the iframe panel's contact", async () => {
    const { wrapper, host } = await setup({ connected: true });
    const pat = makeContact({ id: '1', displayName: 'Pat Customer' });

    host.sendContact(pat);
    host.sendCall(makeCall({ state: 'ringing', contact: pat }));
    await host.settle();
    await flushPromises();

    expect(wrapper.find('[data-testid="call-contact"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="acme-contact"]').text()).toContain(
      'Acme Pat Customer',
    );
  });

  it("shows the call's contact as well when it is a different contact", async () => {
    const { wrapper, host } = await setup({ connected: true });

    host.sendContact(makeContact({ id: '1', displayName: 'Pat Customer' }));
    host.sendCall(
      makeCall({
        state: 'ringing',
        contact: makeContact({ id: '2', displayName: 'Sam Prospect' }),
      }),
    );
    await host.settle();
    await flushPromises();

    expect(wrapper.get('[data-testid="call-contact"]').text()).toContain(
      'Acme Sam Prospect',
    );
    expect(wrapper.get('[data-testid="acme-contact"]').text()).toContain(
      'Acme Pat Customer',
    );
  });

  it('shows no call contact section when the call has no contact', async () => {
    const { wrapper, host } = await setup({ connected: true });

    host.sendCall(makeCall({ state: 'ringing', contact: null }));
    await host.settle();
    await flushPromises();

    expect(wrapper.find('[data-testid="call-contact"]').exists()).toBe(false);
  });

  it('opens a new contact without disconnecting', async () => {
    const { wrapper, host } = await setup({ connected: true });

    host.sendContact(makeContact({ displayName: 'Pat Customer' }));
    await host.settle();
    await flushPromises();
    host.sendContact(makeContact({ displayName: 'Sam Prospect' }));
    await host.settle();
    await flushPromises();

    expect(wrapper.get('[data-testid="acme-contact"]').text()).toContain(
      'Acme Sam Prospect',
    );
    expect(wrapper.find('[data-testid="connected-view"]').exists()).toBe(true);
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
  });

  it("applies the host's theme at start and follows its changes", async () => {
    vi.mocked(initDialtoneTheme).mockClear();
    vi.mocked(setMode).mockClear();
    const host = createMockHost({ theme: { mode: 'dark' } });
    await bootstrapWith(host, makePageData());

    expect(initDialtoneTheme).toHaveBeenCalledWith(expect.anything(), 'dark');

    host.setTheme({ mode: 'light' });
    await host.settle();

    expect(setMode).toHaveBeenLastCalledWith('light');
  });

  it('mounts the iframe panel when the SDK starts', async () => {
    const host = createMockHost();

    const root = await bootstrapWith(host, makePageData());

    expect(root.textContent).toContain('Acme CRM (demo)');
  });
});
