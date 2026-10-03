"""Signed values: the OAuth ``state`` and the connection cookie.

Both are ``<base64url JSON>.<base64url HMAC-SHA256>``, signed with the app secret. Each carries a
``kind`` so a value signed for one purpose is never accepted for the other.
"""

import base64
import binascii
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass

STATE_TTL_SECONDS = 10 * 60
COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60

_STATE = 'state'
_COOKIE = 'cookie'


@dataclass(frozen=True)
class StateClaims:
  """What a verified ``state`` value says: whose OAuth round trip this is."""

  user_id: int
  company_id: int


def _b64(data: bytes) -> str:
  return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _unb64(text: str) -> bytes:
  return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


def _mac(body: str, secret: str) -> str:
  return _b64(hmac.new(secret.encode(), body.encode('ascii'), hashlib.sha256).digest())


def sign(payload: dict[str, object], secret: str) -> str:
  """Return ``payload`` as a tamper-evident string."""
  body = _b64(json.dumps(payload, separators=(',', ':'), sort_keys=True).encode())
  return f'{body}.{_mac(body, secret)}'


def verify(value: str, secret: str) -> dict[str, object] | None:
  """Return the payload when the signature is valid, otherwise ``None``."""
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
  """Sign a ``state`` for this user, valid for ten minutes."""
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
  """Return the user a valid, unexpired ``state`` was issued for."""
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


def issue_cookie(user_id: int, company_id: int, secret: str, now: float) -> str:
  """Sign the connection cookie value for this user."""
  return sign(
      {
          'kind': _COOKIE,
          'user_id': user_id,
          'company_id': company_id,
          'iat': now
      },
      secret,
  )


def cookie_is_valid(
    value: str | None,
    user_id: int,
    company_id: int,
    secret: str,
    now: float,
) -> bool:
  """Whether the cookie is genuine, recent, and belongs to this user and company.

  One browser profile can switch Dialpad users, so a cookie for another user means "not connected".
  """
  if not value:
    return False
  payload = verify(value, secret)
  if payload is None or payload.get('kind') != _COOKIE:
    return False
  issued = payload.get('iat')
  if not isinstance(issued, int | float) or now - issued > COOKIE_MAX_AGE_SECONDS:
    return False
  return payload.get('user_id') == user_id and payload.get('company_id') == company_id
