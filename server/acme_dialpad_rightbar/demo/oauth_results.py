"""The in-memory store of finished OAuth round trips, for the demo only.

SHORTCUT: ``OAuthResults`` lives in one process's memory. A real partner has no use for it at all:
see that class for why this demo needs it and what replaces it. Everything that must last (the
user's access token and whether they are connected) lives in the signed storage cookie, see
``acme_dialpad_rightbar.demo.fake_storage``. Upgrade trigger: the app runs on more than one
instance or connects to a real CRM.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from collections.abc import Callable

  from acme_dialpad_rightbar.context import UserKey

# How long a finished OAuth round trip waits to be collected by the SDK's next connection check.
# Covers a user who signs in slowly, or a desktop-app Connect where polling already gave up.
OAUTH_RESULT_TTL_SECONDS = 5 * 60


class OAuthResults:
  """Short-lived "this user finished connecting" results, each consumed once. DEMO ONLY.

  **The whole Connect flow, and where this fits**

  1. The iframe panel loads in Dialpad's iframe. The page data says "not connected" and carries an
     authorize URL whose signed ``state`` is bound to this Dialpad user.
  2. The user clicks Connect. The SDK asks Dialpad to open that URL in a popup (on the web) or in
     its own login window (the desktop app), and starts polling ``ext-connection`` with the
     iframe panel's access token: first after 7 seconds, then every 5, giving up after 2 minutes.
  3. The user signs in and approves access at the CRM. Here that is a page labelled fake with an
     Authorize button. The CRM then sends the popup to this app's ``/oauth/callback`` with the
     ``state`` and a ``code``.
  4. The callback verifies the ``state`` (which tells it which Dialpad user this is) and closes
     the popup. **This is where a real partner exchanges the ``code`` for the CRM's tokens and
     stores them durably, keyed by the Dialpad user. This demo has no CRM and so no tokens; the
     only fact it has is "this user pressed Authorize", and it records that here.**
  5. The iframe panel's next ``ext-connection`` check collects the record (``consume``), answers
     "connected", and rewrites the storage cookie with the connection on. The cookie, not this
     store, is the demo's persistent record of the connection (see
     ``acme_dialpad_rightbar.demo.fake_storage``): it is signed, lasts 30 days, and later page
     loads see it
     and start connected, even after a server restart.

  **Why the result is kept in memory**

  The callback and the iframe panel are in different places. The callback runs in the popup, a
  separate window with its own cookies, while the storage cookie is ``Partitioned`` and belongs to
  the iframe panel, so a cookie set by the callback would never reach the iframe. The two only share
  one thing, the Dialpad user, which the callback learns from the ``state`` and the iframe panel's
  check learns from its access token. So the callback leaves a note for that user, and the iframe
  panel's check picks it up. Without somewhere to leave the note, the iframe panel could not tell
  that the popup finished.

  **Why that is only for the demo**

  In a real app the note is the CRM tokens themselves. The callback stores them, and
  ``ext-connection`` answers "connected" when tokens exist for the user, from the database, on any
  instance, after any restart. There is then no handoff to make, and the signed storage cookie that
  this demo uses as its persistent storage (the access token and the connection) is not needed
  either.

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
