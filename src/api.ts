// The app's one HTTP module. It adds the access token to every request and applies the app's own
// policy for a rejected token. It is passed to `createRightbar({ fetch })`, so the SDK's own calls
// (/connection, /disconnect, polling) go through it too. Partner feature calls use it the same way.
import { ref } from 'vue';

/** The access token is held in server memory, so a backend restart makes it unknown (`401`). */
export const sessionExpired = ref(false);

let authHeaders: () => Record<string, string> = () => ({});

/** Called once, after `createRightbar()` resolves, with the SDK's `authHeaders`. */
export function useAuthHeaders(source: () => Record<string, string>): void {
  authHeaders = source;
}

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
