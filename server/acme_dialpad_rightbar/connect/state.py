"""The OAuth ``state``: which user an OAuth round trip is for, signed so it can't be forged.

The ``state`` rides through the OAuth round trip (authorize URL, then callback) and says which user
the round trip is for, so the callback can't be tricked into connecting someone else. It's a signed
value (``acme_dialpad_rightbar.signing``) under its own ``kind``. It isn't encrypted: anyone can
read the ids in it, but nobody without the app secret can forge or alter one. A real app can keep it
this way, or keep the ``state`` in a store with a short expiry instead.
"""

import secrets
from dataclasses import dataclass

from acme_dialpad_rightbar.signing import sign
from acme_dialpad_rightbar.signing import verify

# How long an authorize URL's ``state`` stays valid: the user has this long to finish signing in.
STATE_TTL_SECONDS = 10 * 60

_STATE = 'state'


@dataclass(frozen=True)
class StateClaims:
  """Who a verified ``state`` was issued to, as the idtoken's user and company ids."""

  user_id: int
  company_id: int


def issue_state(user_id: int, company_id: int, secret: str, now: float) -> str:
  """Sign a ``state`` for this user, valid for ten minutes from ``now``.

  Called each time an authorize URL is built. The random nonce makes every ``state`` unique, so
  two Connect clicks never share one.
  """
  return sign(
      {
          'kind': _STATE,
          'user_id': user_id,
          'company_id': company_id,
          'nonce': secrets.token_urlsafe(16),
          'exp': now + STATE_TTL_SECONDS,
      },
      secret,
  )


def verify_state(value: str, secret: str, now: float) -> StateClaims | None:
  """Return the user a ``state`` was issued to, or ``None`` if it is forged, expired or misused.

  Called by the OAuth callback with the ``state`` the CRM sent back. A storage cookie value is
  rejected here even though it is signed with the same secret, because its ``kind`` differs.
  """
  payload = verify(value, secret)
  if payload is None or payload.get('kind') != _STATE:
    return None
  user_id = payload.get('user_id')
  company_id = payload.get('company_id')
  expires = payload.get('exp')
  if not (isinstance(user_id, int) and isinstance(company_id, int)):
    return None
  if not isinstance(expires, int | float) or expires <= now:
    return None
  return StateClaims(user_id=user_id, company_id=company_id)
