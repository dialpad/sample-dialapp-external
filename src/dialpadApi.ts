// The result of the backend's demo call to Dialpad's API, read from the page data's `app` field.
//
// The backend calls `GET /api/v2/users/me` with the idtoken's api key while it renders the page, and
// puts the outcome in `app.dialpadApi`. That call is unnecessary for the app and exists for demo
// purposes only; the panel just shows what came back. The api key itself is never sent to the page.

/** The few non-sensitive fields of Dialpad's user that the backend passes on. */
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
 * Read the demo result from the page data's `app` field, or null when it holds none.
 *
 * `app` is partner-defined JSON the SDK passes through unchecked, so each part is validated here
 * instead of trusted: an unknown status or a malformed value gives null (the panel shows no card)
 * rather than an error.
 */
export function readDialpadApi(
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
