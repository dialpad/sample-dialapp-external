// The app's one HTTP module. It adds the access token to every request and applies the app's own
// policy for a rejected token. It is passed to `createRightbar({ fetch })`, so the SDK's own calls
// (/dialpad/ext-connection, /dialpad/ext-disconnect, polling) go through it too. Partner feature
// calls (contact lookups and so on) would use it the same way.
import { ref } from 'vue';

/**
 * True once the server has answered `401` to a request carrying the access token.
 *
 * The server accepts the token only while it matches the one in the browser's session cookie, so a
 * 401 means the cookie is gone or expired, or now belongs to another session (another Dialpad user
 * opened an iframe panel in this browser, or the server's secret changed). Nothing can fix that from here;
 * `App.vue` shows "reload the panel" while this is set, and a reload gets a new page with a new
 * token and cookie.
 */
export const sessionExpired = ref(false);

/** The source of the `Authorization` header. Empty until the SDK has started and handed it over. */
let authHeaders: () => Record<string, string> = () => ({});

/**
 * Give `api` the SDK's `authHeaders`, which return `Authorization: Bearer <access token>`.
 *
 * Called once by `bootstrap`, right after `createRightbar()` resolves. The SDK's first calls (the
 * start-up connection check) can happen before this runs; the SDK adds the header to its own calls
 * anyway, so those are unaffected.
 */
export function useAuthHeaders(source: () => Record<string, string>): void {
  authHeaders = source;
}

/**
 * `fetch`, plus the access token and the app's 401 policy.
 *
 * Adds the bearer header unless the caller already set one, sends the request, and, if the server
 * answers `401`, sets `sessionExpired` so the iframe panel asks the user to reload. The response is
 * returned untouched either way, so the SDK still sees the status and can report `request_failed`.
 */
export async function api(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const headers = new Headers(init?.headers);
  for (const [name, value] of Object.entries(authHeaders())) {
    if (!headers.has(name)) {
      headers.set(name, value);
    }
  }
  const response = await fetch(input, { ...init, headers });
  if (response.status === 401) {
    sessionExpired.value = true;
  }
  return response;
}
