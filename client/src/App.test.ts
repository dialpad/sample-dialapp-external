// Every state of the iframe panel, against the SDK's mock host and its clock: Dialpad is `createMockHost()`,
// the server is a fetch function, and time moves with `host.advance()`. The harness is in
// `testing.ts`; the CRM record's tests are in `crm/CrmRecord.test.ts`.
import { type RightbarOptions } from '@dialpad/dialapp-external-sdk';
import {
  createMockHost,
  makeCall,
  makePageData,
  makeUser,
} from '@dialpad/dialapp-external-sdk/testing';
import { flushPromises } from '@vue/test-utils';
import { initDialtoneTheme, setMode } from '@dialpad/dialtone/themes/config';
import { describe, expect, it, vi } from 'vitest';

import { api } from './api';
import { bootstrap } from './bootstrap';
import {
  AUTHORIZE_URL,
  fakeServer,
  installPanelHarness,
  rejectToasts,
  setupPanel as setup,
  start,
  unhandledRejectionsDuring,
  warnings,
} from './testing';

// Dialtone's theme functions write to the document; here only the calls matter.
vi.mock('@dialpad/dialtone/themes/config', () => ({
  initDialtoneTheme: vi.fn(),
  setMode: vi.fn(),
}));

installPanelHarness();

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
  /** The menu once connected, as Dialpad keeps it: the panel's own ids and English labels, in order. */
  const CONNECTED_MENU = [
    { id: 'rematch', label: 'Rematch' }, // crm-record
    { id: 'create-task', label: 'Create Task' },
    { id: 'disconnect', label: 'Disconnect' },
  ];

  it('is empty from the start while the user is not connected, then Rematch, Create Task and Disconnect once connected', async () => {
    const host = createMockHost();
    const server = fakeServer();

    const { rightbar } = await start(host, server, false);
    expect(host.received.menu).toEqual([]);

    server.mode = 'connected';
    await rightbar.refresh();
    await host.settle();
    expect(host.received.menu).toEqual(CONNECTED_MENU);
    expect(host.received.refreshButtonShown).toBe(true);
  });

  it('is set again when the panel reloads, since Dialpad forgets it', async () => {
    const host = createMockHost();
    const server = fakeServer();
    server.mode = 'connected';
    await start(host, server, true);

    await start(host, server, true);

    expect(host.received.menu).toEqual(CONNECTED_MENU);
  });

  it('disconnects when the user picks Disconnect: the Connect gate, the toast, and an empty menu', async () => {
    const host = createMockHost();
    const server = fakeServer();
    server.mode = 'connected';
    const { root } = await start(host, server, true);
    expect(host.received.menu).toEqual(CONNECTED_MENU);
    expect(host.received.refreshButtonShown).toBe(true);

    host.selectMenuItem('disconnect');
    await host.settle();
    await flushPromises();
    await host.settle();

    expect(server.calls.some((c) => c.path.endsWith('/ext-disconnect'))).toBe(
      true,
    );
    expect(root.querySelector('[data-testid="connect-gate"]')).not.toBeNull();
    expect(host.received.toasts).toEqual([
      { text: 'Disconnected from Acme CRM', type: 'info' },
    ]);
    expect(host.received.menu).toEqual([]);
    expect(host.received.refreshButtonShown).toBe(false);
  });

  it.each([
    ['create-task', "Create Task isn't implemented in this sample app"],
  ] as const)(
    'says %s is not implemented when the user picks it, and stays connected',
    async (id, text) => {
      const host = createMockHost();
      const server = fakeServer();
      server.mode = 'connected';
      const { rightbar } = await start(host, server, true);

      host.selectMenuItem(id);
      await host.settle();

      expect(host.received.toasts).toEqual([{ text, type: 'info' }]);
      expect(rightbar.state.connection.connected).toBe(true);
      expect(server.calls.some((c) => c.path.endsWith('/ext-disconnect'))).toBe(
        false,
      );
      expect(host.received.menu).toEqual(CONNECTED_MENU);
    },
  );

  it('logs a toast Dialpad rejects for a menu item, without an unhandled rejection', async () => {
    const host = createMockHost();
    const server = fakeServer();
    server.mode = 'connected';

    const unhandled = await unhandledRejectionsDuring(async () => {
      const { rightbar } = await start(host, server, true);
      rejectToasts(rightbar);
      host.selectMenuItem('create-task');
      await host.settle();
    });

    expect(unhandled).toBe(0);
    expect(warnings).toHaveBeenCalledWith(
      "Dialpad didn't show the toast",
      expect.any(Error),
    );
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

  it('logs a refresh button Dialpad rejects, without an unhandled rejection', async () => {
    const host = createMockHost();
    const server = fakeServer();

    const unhandled = await unhandledRejectionsDuring(async () => {
      await start(host, server, false, (rightbar) => {
        Object.assign(rightbar, {
          showRefreshButton: () =>
            Promise.reject(new Error('Dialpad did not answer')),
        });
      });
    });

    expect(unhandled).toBe(0);
    expect(warnings).toHaveBeenCalledWith(
      "Dialpad didn't show the refresh button",
      expect.any(Error),
    );
  });
});
