"""In-memory stores.

SHORTCUT: both live in one process's memory. A real partner keeps access tokens durably, so a
restart or a second instance doesn't log users out, and keeps OAuth results in a shared store.
Upgrade trigger: the app runs on more than one instance or must survive a restart.
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
  """Short-lived "this user finished connecting" results, each consumed once.

  The OAuth callback runs in a popup, a separate browser context from the panel's iframe, so it
  can't set the iframe's cookie. It records a result here instead, and the SDK's next connection
  check (a poll, the reply to Connect, or the next iframe's start-up check) collects it.
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
