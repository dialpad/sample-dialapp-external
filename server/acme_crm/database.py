"""The per-user state this demo keeps for good, held in the browser's session cookie.

A real partner keeps a row per Dialpad user in a database: the user's access token for this app and
whether they are connected to the CRM (the CRM tokens the OAuth callback stored). This demo has no
database and no CRM, so ``CookieBackedDatabaseStorage`` plays that row, and the signed session
cookie (``acme_crm.signing``) plays the database. The route handlers read it only through the
getters, ``get_access_token`` and ``is_external_connected``, and change it only by building a new
state, so swapping in a real database later touches this class and not the handlers.

The state is immutable. ``from_cookie`` reads one from a request, ``new`` starts one, and
``to_cookie`` serialises it for the response; nothing is kept on the server.
"""

import secrets
from typing import Self

from acme_crm import signing
from acme_crm.stores import UserKey


class CookieBackedDatabaseStorage:
  """One Dialpad user's access token and connection, read from and written to a cookie value.

  It is bound to the user and company it was created for: a browser that switches Dialpad users
  must not reuse the previous user's state (see ``belongs_to``).
  """
  def __init__(self, session: signing.SessionClaims) -> None:
    """Wrap an already verified session; use ``new`` or ``from_cookie`` instead of calling this."""
    self._session = session

  @classmethod
  def new(cls, key: UserKey) -> Self:
    """Start a state for this user: a fresh random access token, and not connected."""
    session = signing.SessionClaims(
        user_id=key.user_id,
        company_id=key.company_id,
        token=signing.new_access_token(),
        connected=False,
    )
    return cls(session)

  @classmethod
  def from_cookie(cls, value: str | None, secret: str, now: float) -> Self | None:
    """Read the state from a session cookie value, or ``None`` if it is missing, forged or old.

    The signature, the purpose and the 30-day age are checked by ``signing.read_session``.
    """
    session = signing.read_session(value, secret, now)
    return None if session is None else cls(session)

  def to_cookie(self, secret: str, now: float) -> str:
    """Sign this state as a session cookie value, stamped with the time of issue ``now``."""
    return signing.issue_session(self._session, secret, now)

  def user_key(self) -> UserKey:
    """Return the Dialpad user (company and user ids) this state belongs to."""
    return UserKey(company_id=self._session.company_id, user_id=self._session.user_id)

  def belongs_to(self, key: UserKey) -> bool:
    """Whether this state was created for exactly this user and company."""
    return self.user_key() == key

  def get_access_token(self) -> str:
    """Return the user's access token: what the iframe panel sends as ``Authorization: Bearer``."""
    return self._session.token

  def has_access_token(self, candidate: str) -> bool:
    """Whether ``candidate`` is this state's access token, compared in constant time."""
    return secrets.compare_digest(candidate, self._session.token)

  def is_external_connected(self) -> bool:
    """Whether the user is connected to the partner system (Acme CRM) in this state."""
    return self._session.connected

  def with_external_connected(self, *, connected: bool) -> Self:
    """Return a copy of this state with the connection turned on or off, keeping the token.

    The access token is kept because the iframe panel keeps sending it: after a disconnect its next
    ``ext-connection`` call must still authenticate.
    """
    return type(self)(signing.SessionClaims(
        user_id=self._session.user_id,
        company_id=self._session.company_id,
        token=self._session.token,
        connected=connected,
    ))
