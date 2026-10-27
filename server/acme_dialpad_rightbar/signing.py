"""Signed values, and the OAuth ``state`` signed with them.

A signed value is ``<base64url JSON>.<base64url HMAC-SHA256>``, signed with the app secret. It
carries a ``kind`` so a value signed for one purpose is never accepted for another.

The ``state`` rides through the OAuth round trip (authorize URL, then callback) and says which user
the round trip is for, so the callback can't be tricked into connecting someone else. It isn't
encrypted: anyone can read the ids in it, but nobody without the app secret can forge or alter one.
A real app can keep it this way, or keep the ``state`` in a store with a short expiry instead.

The demo's storage cookie is signed the same way, under its own ``kind``
(``acme_dialpad_rightbar.demo.fake_storage``).
"""

import base64
import binascii
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass

# How long an authorize URL's ``state`` stays valid: the user has this long to finish signing in.
STATE_TTL_SECONDS = 10 * 60

_STATE = 'state'


@dataclass(frozen=True)
class StateClaims:
  """Who a verified ``state`` was issued to, as the idtoken's user and company ids."""

  user_id: int
  company_id: int


def _b64(data: bytes) -> str:
  """Encode bytes as unpadded URL-safe base64."""
  return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _unb64(text: str) -> bytes:
  """Decode unpadded URL-safe base64, restoring the padding first."""
  return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


def _mac(body: str, secret: str) -> str:
  """Return the HMAC-SHA256 of an encoded payload, itself base64url encoded."""
  return _b64(hmac.new(secret.encode(), body.encode('ascii'), hashlib.sha256).digest())


def sign(payload: dict[str, object], secret: str) -> str:
  """Return ``payload`` as ``<body>.<signature>``, readable but tamper-evident."""
  body = _b64(json.dumps(payload, separators=(',', ':'), sort_keys=True).encode())
  return f'{body}.{_mac(body, secret)}'


def verify(value: str, secret: str) -> dict[str, object] | None:
  """Return the payload of a value ``sign`` produced with this secret, else ``None``.

  The signature is compared in constant time. Any malformed input (no dot, bad base64, not a JSON
  object) is also ``None``: callers treat all of it as "not a valid value".
  """
  body, _, signature = value.partition('.')
  if not body or not hmac.compare_digest(signature, _mac(body, secret)):
    return None
  try:
    payload = json.loads(_unb64(body))
  except (ValueError, binascii.Error):
    return None
  if not isinstance(payload, dict):
    return None
  return {str(name): item for name, item in payload.items()}


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


def new_access_token() -> str:
  """Return a fresh random access token: what the iframe panel sends as a bearer token."""
  return secrets.token_urlsafe(32)
