// The custom data the server puts in the page data's `app` field: whatever bootstrap data this
// application wants its iframe panel to start with. The SDK passes the field through unchecked as
// `rightbar.app`, so it is validated here before use. The demo's only entry is the result of its
// call to Dialpad's API, `app.dialpadApi`.
//
// The server calls `GET /api/v2/users/me` with the idtoken's api key while it renders the page, and
// puts the outcome in `app.dialpadApi`. That call is unnecessary for the app and exists for demo
// purposes only; the iframe panel just shows what came back. The api key itself is never sent to the page.

/** The few non-sensitive fields of Dialpad's user that the server passes on. */
export interface DialpadApiUser {
  id: number | null;
  displayName: string | null;
  email: string | null;
  state: string | null;
}

/** What the demo call came to: `ok` with a user, `unavailable`, or `skipped` (local mode). */
export interface DialpadApiDemo {
  status: 'ok' | 'unavailable' | 'skipped';
  user: DialpadApiUser | null;
}

/** A string field of a JSON object, or null when it is missing or not a string. */
function text(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

/** Whether `value` is a JSON object, which is all `app` and its parts are guaranteed to be. */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Read the page data's `app` field: the demo's Dialpad API result, or null when it holds none.
 *
 * `app` is partner-defined JSON the SDK passes through unchecked, so each part is validated here
 * instead of trusted: an unknown status or a malformed value gives null (the iframe panel shows no card)
 * rather than an error.
 */
export function readPageAppData(
  app: Readonly<Record<string, unknown>> | null,
): DialpadApiDemo | null {
  const demo = app?.dialpadApi;
  if (!isRecord(demo)) {
    return null;
  }
  const { status, user } = demo;
  if (status !== 'ok' && status !== 'unavailable' && status !== 'skipped') {
    return null;
  }
  if (!isRecord(user)) {
    return { status, user: null };
  }
  return {
    status,
    user: {
      id: typeof user.id === 'number' ? user.id : null,
      displayName: text(user.displayName),
      email: text(user.email),
      state: text(user.state),
    },
  };
}
