// Every state of the panel, against the SDK's mock host and its clock: Dialpad is `createMockHost()`,
// the backend is a fetch function, and time moves with `host.advance()`.
import { type FetchLike, type RightbarOptions } from '@dialpad/dialapp-external-sdk';
import { rightbarPlugin } from '@dialpad/dialapp-external-sdk/vue';
import {
  createMockHost,
  makeContact,
  makePageData,
  makeUser,
} from '@dialpad/dialapp-external-sdk/testing';
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { api, sessionExpired } from './api';
import App from './App.vue';
import { bootstrap } from './bootstrap';

const AUTHORIZE_URL = 'https://acme.example.com/oauth/fake-authorize?state=s';

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

/** A fake Acme backend: `mode` decides how the connection endpoint answers. */
function fakeBackend() {
  const backend = {
    mode: 'not_connected' as 'not_connected' | 'connected' | 'network' | 'server_error',
    calls: [] as { method: string; path: string }[],
    fetch: vi.fn<FetchLike>((input, init) => {
      const path = new URL(String(input), 'https://acme.example.com').pathname;
      backend.calls.push({ method: init?.method ?? 'GET', path });
      if (path.endsWith('/disconnect')) {
        backend.mode = 'not_connected';
      }
      switch (backend.mode) {
        case 'network':
          return Promise.reject(new TypeError('Failed to fetch'));
        case 'server_error':
          return Promise.resolve(json({ code: 'oops', message: 'oops' }, 500));
        case 'connected':
          return Promise.resolve(json({ connected: true, account_name: 'Acme CRM (demo)' }));
        default:
          return Promise.resolve(
            json({ connected: false, account_name: 'Acme CRM (demo)', authorize_url: AUTHORIZE_URL }),
          );
      }
    }),
  };
  return backend;
}

const mounted: VueWrapper[] = [];

async function setup({ connected = false } = {}) {
  const host = createMockHost();
  const backend = fakeBackend();
  const root = document.createElement('div');
  document.body.append(root);
  const rightbar = await host.createRightbar({
    heightRoot: root,
    fetch: backend.fetch,
    pageData: makePageData({
      user: makeUser({ name: 'Jane Agent', email: 'jane@example.com', phoneNumber: '+1 555 0100' }),
      connection: connected
        ? { connected: true, accountName: 'Acme CRM (demo)' }
        : { connected: false, authorizeUrl: AUTHORIZE_URL },
    }),
  });
  const wrapper = mount(App, { global: { plugins: [[rightbarPlugin, rightbar]] }, attachTo: root });
  mounted.push(wrapper);
  await host.settle();
  return { host, backend, wrapper, rightbar };
}

afterEach(() => {
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
    expect(wrapper.get('[data-testid="connect-button"]').text()).toBe('Connect');
    expect(wrapper.find('[data-testid="connected-view"]').exists()).toBe(false);
  });

  it('asks Dialpad to open the authorize URL and shows connecting while it polls', async () => {
    const { wrapper, host } = await setup();

    await wrapper.get('[data-testid="connect-button"]').trigger('click');
    await host.settle();

    expect(host.received.authorizeRequests).toEqual([AUTHORIZE_URL]);
    expect(wrapper.get('[role="status"]').text()).toContain('Waiting');
    expect(wrapper.get('[data-testid="connect-button"]').attributes('disabled')).toBeDefined();
  });

  it('completes Connect by polling: the first check is after 7 seconds', async () => {
    const { wrapper, host, backend } = await setup();
    await wrapper.get('[data-testid="connect-button"]').trigger('click');
    await host.settle();
    backend.mode = 'connected';

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

    expect(wrapper.get('[role="alert"]').text()).toContain("didn't respond in time");
    expect(wrapper.get('[data-testid="connect-button"]').text()).toBe('Try again');
  });

  it('shows the network state with Try again when the request throws', async () => {
    const { wrapper, host, backend } = await setup();
    await wrapper.get('[data-testid="connect-button"]').trigger('click');
    backend.mode = 'network';

    await host.advance(7_000);
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toContain("couldn't reach Acme");
    expect(wrapper.get('[data-testid="connect-button"]').text()).toBe('Try again');
  });

  it('shows the request-failed state with Try again on a non-2xx response', async () => {
    const { wrapper, host, backend } = await setup();
    await wrapper.get('[data-testid="connect-button"]').trigger('click');
    backend.mode = 'server_error';

    await host.advance(7_000);
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toContain('Something went wrong');
    expect(wrapper.get('[data-testid="connect-button"]').text()).toBe('Try again');
  });

  it('restarts Connect when Try again is clicked', async () => {
    const { wrapper, host, backend } = await setup();
    await wrapper.get('[data-testid="connect-button"]').trigger('click');
    await host.advance(120_000);
    await flushPromises();
    backend.mode = 'connected';

    await wrapper.get('[data-testid="connect-button"]').trigger('click');
    await host.advance(7_000);
    await flushPromises();

    expect(host.received.authorizeRequests).toHaveLength(2);
    expect(wrapper.find('[data-testid="connected-view"]').exists()).toBe(true);
  });
});

describe('Connected view', () => {
  it("shows the user's claims from the page data", async () => {
    const { wrapper } = await setup({ connected: true });

    const claims = wrapper.get('[data-testid="claims-card"]').text();
    expect(claims).toContain('Jane Agent');
    expect(claims).toContain('jane@example.com · +1 555 0100');
    expect(claims).toContain('user 5432 · company 12345 · office 54321');
    expect(claims).not.toContain('api_key');
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

    const contact = wrapper.get('[data-testid="acme-contact"]').text();
    expect(contact).toContain('displayName');
    expect(contact).toContain('Acme Pat Customer');
    expect(contact).toContain('Acme +1 555 0199');
    expect(contact).toContain('Acme pat@example.com');
    expect(contact).not.toContain('jobTitle');
  });

  it('opens a new contact without disconnecting', async () => {
    const { wrapper, host } = await setup({ connected: true });

    host.sendContact(makeContact({ displayName: 'Pat Customer' }));
    await host.settle();
    host.sendContact(makeContact({ displayName: 'Sam Prospect' }));
    await host.settle();

    expect(wrapper.get('[data-testid="acme-contact"]').text()).toContain('Acme Sam Prospect');
    expect(wrapper.find('[data-testid="connected-view"]').exists()).toBe(true);
  });

  it('asks for inline confirmation before disconnecting, and Cancel backs out', async () => {
    const { wrapper, backend } = await setup({ connected: true });

    await wrapper.get('[data-testid="disconnect-button"]').trigger('click');
    expect(wrapper.text()).toContain('Disconnect Acme?');
    expect(backend.calls.some((c) => c.path.endsWith('/disconnect'))).toBe(false);

    await wrapper.findAll('button').find((b) => b.text() === 'Cancel')?.trigger('click');

    expect(wrapper.text()).not.toContain('Disconnect Acme?');
    expect(wrapper.find('[data-testid="disconnect-button"]').exists()).toBe(true);
  });

  it('disconnects after confirmation and shows the Connect gate again', async () => {
    const { wrapper, host, backend } = await setup({ connected: true });
    backend.mode = 'connected';

    await wrapper.get('[data-testid="disconnect-button"]').trigger('click');
    await wrapper.get('[data-testid="disconnect-confirm"]').trigger('click');
    await host.settle();
    await flushPromises();

    expect(backend.calls).toContainEqual({ method: 'POST', path: '/dialpad/disconnect' });
    expect(wrapper.find('[data-testid="connect-gate"]').exists()).toBe(true);
  });
});

describe('Requests', () => {
  it('shows "reload the panel" when the backend rejects the access token', async () => {
    const response = new Response('{}', { status: 401 });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(response);

    await api('/dialpad/connection');

    const { wrapper } = await setup();
    expect(wrapper.text()).toContain('Reload the panel');
  });
});

describe('Bootstrap errors', () => {
  async function bootstrapWith(host: ReturnType<typeof createMockHost>, pageData: unknown) {
    const root = document.createElement('div');
    document.body.append(root);
    await bootstrap(root, (options: RightbarOptions) =>
      host.createRightbar({ ...options, pageData: pageData as never }),
    );
    return root;
  }

  it('tells the user to open the panel from Dialpad on bad_page_data', async () => {
    const host = createMockHost();

    const root = await bootstrapWith(host, { not: 'page data' });

    expect(root.textContent).toContain('Open this panel from Dialpad');
  });

  it('tells the user to open the panel from Dialpad on init_timeout', async () => {
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

  it('mounts the panel when the SDK starts', async () => {
    const host = createMockHost();

    const root = await bootstrapWith(host, makePageData());

    expect(root.textContent).toContain('Acme CRM (demo)');
  });
});
