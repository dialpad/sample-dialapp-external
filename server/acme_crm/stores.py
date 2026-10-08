"""In-memory stores, for the demo only.

SHORTCUT: both live in one process's memory. A real partner keeps access tokens durably, so a
restart or a second instance doesn't log users out. It also has no use for ``OAuthResults`` at all:
see that class for why this demo needs it and what replaces it. Upgrade trigger: the app runs on
more than one instance, must survive a restart, or connects to a real CRM.
"""

import secrets
from typing import TYPE_CHECKING
from typing import NamedTuple

if TYPE_CHECKING:
  from collections.abc import Callable

# How long a finished OAuth round trip waits to be collected by the SDK's next connection check.
# Covers a user who signs in slowly, or a desktop-app Connect where polling already gave up.
OAUTH_RESULT_TTL_SECONDS = 5 * 60


class UserKey(NamedTuple):
  """A Dialpad user, identified by the company and user ids the idtoken carries.

  It is the key of both stores below, and is hashable so it can index a dict.
  """

  company_id: int
  user_id: int


class AccessTokens:
  """One random access token per Dialpad user, issued on first page load and reused after.

  The token is what the SDK sends as ``Authorization: Bearer`` on every API call. It is the
  user's session with this server, separate from the idtoken (which only authenticates the page
  request). Everything is lost when the process restarts, after which open panels get ``401``.
  """
  def __init__(self) -> None:
    """Start empty."""
    self._by_user: dict[UserKey, str] = {}
    self._by_token: dict[str, UserKey] = {}

  def issue(self, key: UserKey) -> str:
    """Return this user's access token, creating it the first time the user's page loads.

    Later page loads (a new contact, a new day) get the same token back, so open panels stay valid.
    """
    token = self._by_user.get(key)
    if token is None:
      token = secrets.token_urlsafe(32)
      self._by_user[key] = token
      self._by_token[token] = key
    return token

  def lookup(self, token: str) -> UserKey | None:
    """Authenticate a token: return the user it was issued to, or ``None`` if unknown."""
    return self._by_token.get(token)


class OAuthResults:
  """Short-lived "this user finished connecting" results, each consumed once. DEMO ONLY.

  **The whole Connect flow, and where this fits**

  1. The panel loads in Dialpad's iframe. The page data says "not connected" and carries an
     authorize URL whose signed ``state`` is bound to this Dialpad user.
  2. The user clicks Connect. The SDK asks Dialpad to open that URL in a popup (on the web) or in
     its own login window (the desktop app), and starts polling ``ext-connection`` with the
     panel's access token: first after 7 seconds, then every 5, giving up after 2 minutes.
  3. The user signs in and approves access at the CRM. Here that is a page labelled fake with an
     Authorize button. The CRM then sends the popup to this app's ``/oauth/callback`` with the
     ``state`` and a ``code``.
  4. The callback verifies the ``state`` (which tells it which Dialpad user this is) and closes
     the popup. **This is where a real partner exchanges the ``code`` for the CRM's tokens and
     stores them durably, keyed by the Dialpad user. This demo has no CRM and so no tokens; the
     only fact it has is "this user pressed Authorize", and it records that here.**
  5. The panel's next ``ext-connection`` check collects the record (``consume``), answers
     "connected", and sets the connection cookie. Later page loads see the cookie and start
     connected.

  **Why the result is kept in memory**

  The callback and the panel are in different places. The callback runs in the popup, a separate
  window with its own cookies, while the connection cookie is ``Partitioned`` and belongs to the
  panel's iframe, so a cookie set by the callback would never reach the iframe. The two only share
  one thing, the Dialpad user, which the callback learns from the ``state`` and the panel's check
  learns from its access token. So the callback leaves a note for that user, and the panel's check
  picks it up. Without somewhere to leave the note, the panel could not tell that the popup
  finished.

  **Why that is only for the demo**

  In a real app the note is the CRM tokens themselves. The callback stores them, and
  ``ext-connection`` answers "connected" when tokens exist for the user, from the database, on any
  instance, after any restart. There is no handoff, so no five-minute expiry, no consume-once rule
  and no need for the cookie. This class exists only because the demo has nothing durable to
  check. It is lost on restart (an in-flight Connect then just times out and can be retried) and is
  not shared between instances.

  A record lives for five minutes (``OAUTH_RESULT_TTL_SECONDS``): longer than the SDK's 2-minute
  polling window plus a slow sign-in, short enough that abandoned records don't pile up.
  """
  def __init__(self, clock: Callable[[], float]) -> None:
    """Start empty; ``clock`` returns the current time in seconds."""
    self._clock = clock
    self._expires: dict[UserKey, float] = {}

  def record(self, key: UserKey) -> None:
    """Remember that this user's OAuth round trip finished, for five minutes.

    Called by the OAuth callback after it verified the ``state``. Recording again before the
    first result is collected just restarts the five minutes.
    """
    self._expires[key] = self._clock() + OAUTH_RESULT_TTL_SECONDS

  def consume(self, key: UserKey) -> bool:
    """Collect this user's result: return whether an unexpired one existed, removing it either way.

    Called by ``ext-connection``. A ``True`` means "the user just finished OAuth": the caller
    answers "connected" and sets the cookie. Only one caller can ever get ``True`` per result.
    """
    expires = self._expires.pop(key, None)
    return expires is not None and expires > self._clock()
