// The iframe panel's test harness, shared by the test files: Dialpad is `createMockHost()`, the
// server is a fetch function, and time moves with `host.advance()`. Each test file calls
// `installPanelHarness()` once.
import {
  type FetchLike,
  type Rightbar,
  type User,
} from '@dialpad/dialapp-external-sdk';
import { rightbarPlugin } from '@dialpad/dialapp-external-sdk/vue';
import {
  createMockHost,
  makePageData,
} from '@dialpad/dialapp-external-sdk/testing';
import { mount } from '@vue/test-utils';
import { afterEach, beforeEach, vi, type MockInstance } from 'vitest';

import { accessTokenRejected } from './api';
import App from './App.vue';
import { bootstrap } from './bootstrap';

export const AUTHORIZE_URL =
  'https://acme.example.com/oauth/fake-authorize?state=s';

/** A JSON response, as the Acme server would send one. */
export function json(body: unknown, status = 200): Response {
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
export function fakeServer() {
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

/**
 * The global `fetch` the panel's own requests (the ones made through `api()`) use, unless a test
 * passes its own: every route answers 404.
 */
function noPanelRoutes(): Promise<Response> {
  return Promise.resolve(json({ code: 'not_found', message: 'none' }, 404));
}

/** Every component mounted by `setupPanel`, so `afterEach` can unmount them. */
const mounted: { unmount(): void }[] = [];

/** `console.warn`, spied on for each test. Vue reports bad props as warnings. */
export let warnings: MockInstance<typeof console.warn>;

/**
 * Register the harness's `beforeEach` and `afterEach` in the calling test file: spy on
 * `console.warn`, then fail the test on any Vue warning, restore the mocks, and unmount the panel.
 */
export function installPanelHarness(): void {
  beforeEach(() => {
    warnings = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
  });

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
    accessTokenRejected.value = false;
    document.body.innerHTML = '';
  });
}

/**
 * Start the iframe panel against a mock Dialpad and a fake Acme server, like a user opening it.
 *
 * `connected` is what the page data says at load (a connected user's cookie, or not); `mode` is how
 * the fake server answers connection checks from then on; `user` is what Dialpad's `get/user`
 * answers; `panelFetch` answers the panel's own requests. Returns the host (to send contacts and
 * move the clock), the server (to change its mode and see its calls) and the mounted wrapper.
 */
export async function setupPanel({
  connected = false,
  mode = 'not_connected',
  user,
  app = null,
  panelFetch = noPanelRoutes,
}: {
  connected?: boolean;
  mode?: ReturnType<typeof fakeServer>['mode'];
  /** What Dialpad's `get/user` answers: the default user, a user, or `null` for none. */
  user?: User | null;
  /** What the server put in the page data's `app` field, for example the demo API call's result. */
  app?: Record<string, unknown> | null;
  /** The global `fetch` for the panel's own requests. */
  panelFetch?: (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => Promise<Response>;
} = {}) {
  const host = createMockHost(user === undefined ? {} : { user });
  const server = fakeServer();
  vi.stubGlobal('fetch', panelFetch);
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
  return { host, server, wrapper, rightbar };
}

/**
 * Run the real `bootstrap`, with the mock host standing in for Dialpad and `server` for Acme.
 *
 * `connected` is what the page data says at load. Returns the SDK instance `bootstrap` created,
 * so a test can check the connection again, and the element the panel is mounted in.
 */
export async function start(
  host: ReturnType<typeof createMockHost>,
  server: ReturnType<typeof fakeServer>,
  connected: boolean,
  patch: (rightbar: Rightbar) => void = () => undefined,
): Promise<{ rightbar: Rightbar; root: HTMLElement }> {
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
  return { rightbar: created, root };
}

/**
 * Make Dialpad reject every toast, and return a counter of how many were asked for.
 *
 * A plain function, not a `vi.fn()`: a spy attaches its own handler to the promise it returns, which
 * would hide an unhandled rejection from `unhandledRejectionsDuring`.
 */
export function rejectToasts(rightbar: Rightbar): { asked: number } {
  const counter = { asked: 0 };
  Object.assign(rightbar, {
    showToast: () => {
      counter.asked += 1;
      return Promise.reject(new Error('Dialpad did not answer'));
    },
  });
  return counter;
}

/** Run `action`, then report how many promise rejections nobody handled while it ran. */
export async function unhandledRejectionsDuring(
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
