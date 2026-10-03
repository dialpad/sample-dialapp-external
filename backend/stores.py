"""In-memory stores.

SHORTCUT: both live in one process's memory. A real partner keeps access tokens durably, so a
restart or a second instance doesn't log users out, and keeps OAuth results in a shared store.
Upgrade trigger: the app runs on more than one instance or must survive a restart.
"""

import secrets
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
  from collections.abc import Callable

OAUTH_RESULT_TTL_SECONDS = 5 * 60


class UserKey(NamedTuple):
  """A Dialpad user, as the company and user ids the idtoken carries."""

  company_id: int
  user_id: int


class AccessTokens:
  """One random access token per Dialpad user, issued on first page load and reused after."""
  def __init__(self) -> None:
    """Start empty."""
    self._by_user: dict[UserKey, str] = {}
    self._by_token: dict[str, UserKey] = {}

  def issue(self, key: UserKey) -> str:
    """Return this user's access token, creating it the first time."""
    token = self._by_user.get(key)
    if token is None:
      token = secrets.token_urlsafe(32)
      self._by_user[key] = token
      self._by_token[token] = key
    return token

  def lookup(self, token: str) -> UserKey | None:
    """Return the user a token was issued to, or ``None`` for an unknown token."""
    return self._by_token.get(token)


class OAuthResults:
  """Short-lived "this user finished connecting" results, each consumed once."""
  def __init__(self, clock: Callable[[], float]) -> None:
    """Start empty; ``clock`` returns the current time in seconds."""
    self._clock = clock
    self._expires: dict[UserKey, float] = {}

  def record(self, key: UserKey) -> None:
    """Remember that this user's OAuth round trip finished, for five minutes."""
    self._expires[key] = self._clock() + OAUTH_RESULT_TTL_SECONDS

  def consume(self, key: UserKey) -> bool:
    """Return whether an unexpired result existed for this user, removing it."""
    expires = self._expires.pop(key, None)
    return expires is not None and expires > self._clock()
