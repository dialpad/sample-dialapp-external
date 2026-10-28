// The CRM record in the iframe panel: the contact lookup, the record linked in Dialpad, and
// Rematch. An app that doesn't show a CRM record deletes this file with the rest of `crm/`.
import { type Rightbar } from '@dialpad/dialapp-external-sdk';
import {
  createMockHost,
  makeCall,
  makeContact,
} from '@dialpad/dialapp-external-sdk/testing';
import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

import {
  fakeServer,
  installPanelHarness,
  json,
  rejectToasts,
  setupPanel,
  start,
  unhandledRejectionsDuring,
  warnings,
} from '../testing';

// Dialtone's theme functions write to the document; `bootstrap` calls them on every start.
vi.mock('@dialpad/dialtone/themes/config', () => ({
  initDialtoneTheme: vi.fn(),
  setMode: vi.fn(),
}));

installPanelHarness();

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

/** Start the iframe panel as `setupPanel` does, with the fake `POST /api/contact` answering. */
async function setup(options: Parameters<typeof setupPanel>[0] = {}) {
  const contactApi = fakeContactApi();
  const panel = await setupPanel({ ...options, panelFetch: contactApi.fetch });
  return { ...panel, contactApi };
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

describe('The CRM record', () => {
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

  it("looks the open contact up again on each press of Dialpad's refresh button, the first after a contact change included, and once when Dialpad refreshes a changed record", async () => {
    const { wrapper, host, contactApi } = await setup({ connected: true });
    /** Press the refresh button, and return the ids of the contacts looked up because of it. */
    const refresh = async () => {
      contactApi.requests.length = 0;
      host.trigger('refresh_contact');
      await host.settle();
      await flushPromises();
      return contactApi.requests.map(
        (request) => (request.body as { contact: { id: string } }).contact.id,
      );
    };
    host.sendContact(makeContact({ id: '1', displayName: 'Pat Customer' }));
    await host.settle();
    await flushPromises();

    const first = await refresh();
    host.sendContact(makeContact({ id: '2', displayName: 'Sam Prospect' }));
    await host.settle();
    await flushPromises();
    const afterChange = await refresh();
    // The contact's record changed in Dialpad: Dialpad's own silent refresh brings a new object,
    // which the watch looks up; the refresh handler must not look it up a second time.
    contactApi.requests.length = 0;
    host.updateContact(
      makeContact({ id: '2', displayName: 'Sam Prospect', jobTitle: 'CTO' }),
    );
    await host.settle();
    await flushPromises();
    const afterUpdate = contactApi.requests.length;
    // A press while that contact's lookup is still running starts no second lookup.
    contactApi.mode = 'hold';
    host.updateContact(
      makeContact({ id: '2', displayName: 'Sam Prospect', jobTitle: 'CTO' }),
    );
    await host.settle();
    await flushPromises();
    const whileRunning = await refresh();
    contactApi.held[0]?.respond();
    await flushPromises();

    expect(first).toEqual(['1']);
    expect(afterChange).toEqual(['2']);
    expect(afterUpdate).toBe(1);
    expect(whileRunning).toEqual([]);
    expect(wrapper.get('[data-testid="acme-contact"]').text()).toContain(
      'Acme CTO',
    );
    expect(host.received.linkedRecord).toEqual(recordOf('2'));
  });

  it('links the record in a browser without URL.canParse, such as Chrome before 120', async () => {
    const canParse = Object.getOwnPropertyDescriptor(URL, 'canParse');
    Object.defineProperty(URL, 'canParse', {
      value: undefined,
      configurable: true,
    });
    try {
      const { wrapper, host } = await setup({ connected: true });

      host.sendContact(makeContact({ id: '1', displayName: 'Pat Customer' }));
      await host.settle();
      await flushPromises();

      expect(wrapper.get('[data-testid="acme-contact"]').text()).toContain(
        'Acme Pat Customer',
      );
      expect(host.received.linkedRecord).toEqual(recordOf('1'));
    } finally {
      if (canParse) {
        Object.defineProperty(URL, 'canParse', canParse);
      }
    }
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

  it('opens a new contact without reloading or disconnecting, and ignores a late answer for the earlier one', async () => {
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
    // Dialpad kept the panel: it sent `init` once, so Dialpad didn't reload it.
    expect(
      host.received.messages.filter((message) => message.path === 'init'),
    ).toHaveLength(1);
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

  it("doesn't link the record when the lookup answers after the user disconnected", async () => {
    const { wrapper, host, server, contactApi } = await setup({
      connected: true,
    });
    server.mode = 'connected';
    contactApi.mode = 'hold';
    host.sendContact(makeContact({ id: '1', displayName: 'Pat Customer' }));
    await host.settle();
    await flushPromises();

    await wrapper.get('[data-testid="disconnect-button"]').trigger('click');
    await wrapper.get('[data-testid="disconnect-confirm"]').trigger('click');
    await host.settle();
    await flushPromises();
    const gateBeforeAnswer = wrapper
      .find('[data-testid="connect-gate"]')
      .exists();
    contactApi.held[0]?.respond();
    await host.settle();
    await flushPromises();

    expect(contactApi.held).toHaveLength(1);
    expect(gateBeforeAnswer).toBe(true);
    expect(host.received.linkedRecord).toBeNull();
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

  it("shows the call's contact as well when it is a different contact, but links and refreshes only the panel's", async () => {
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
    // Dialpad's refresh button refreshes the panel's contact, not the call's other one.
    contactApi.mode = 'ok';
    contactApi.requests.length = 0;
    host.trigger('refresh_contact');
    await host.settle();
    await flushPromises();
    const refreshed = contactApi.requests.map(
      (request) => (request.body as { contact: { id: string } }).contact.id,
    );

    expect(sam).toBeDefined();
    expect(refreshed).toEqual(['1']);
    expect(wrapper.get('[data-testid="call-contact"]').text()).toContain(
      'Acme Sam Prospect',
    );
    expect(wrapper.get('[data-testid="acme-contact"]').text()).toContain(
      'Acme Pat Customer',
    );
    expect(host.received.linkedRecord).toEqual(recordOf('1'));
  });
});

describe("The CRM record in Dialpad's panel menu", () => {
  /** The menu once connected, as Dialpad keeps it: the panel's own ids and English labels, in order. */
  const CONNECTED_MENU = [
    { id: 'rematch', label: 'Rematch' },
    { id: 'create-task', label: 'Create Task' },
    { id: 'disconnect', label: 'Disconnect' },
  ];

  it('unlinks the record when the user picks Disconnect', async () => {
    const host = createMockHost();
    const server = fakeServer();
    const contactApi = fakeContactApi();
    vi.stubGlobal('fetch', contactApi.fetch);
    server.mode = 'connected';
    await start(host, server, true);
    host.sendContact(makeContact({ id: '1', displayName: 'Pat Customer' }));
    await host.settle();
    await flushPromises();
    const linked = host.received.linkedRecord;

    host.selectMenuItem('disconnect');
    await host.settle();
    await flushPromises();
    await host.settle();

    expect(linked).toEqual(recordOf('1'));
    expect(host.received.linkedRecord).toBeNull();
  });

  it.each([
    ['rematch', "Rematch isn't implemented in this sample app"],
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
});
