"""Signed values: the OAuth ``state`` and the session cookie.

Both are ``<base64url JSON>.<base64url HMAC-SHA256>``, signed with the app secret. Each carries a
``kind`` so a value signed for one purpose is never accepted for the other.

* The ``state`` rides through the OAuth round trip (authorize URL, then callback) and says which
  user the round trip is for, so the callback can't be tricked into connecting someone else.
* The session cookie is this demo's persistent storage: the server keeps no database and no
  per-user session table. The cookie holds the user's access token (the value the panel sends as
  ``Authorization: Bearer``), the Dialpad user and company, and whether the user is connected. A
  real partner would keep the CRM tokens in a database instead and look the user up there. The
  route handlers don't touch these functions directly:
  ``acme_crm.state.CookieBackedDatabaseStorage`` wraps them and is the one place the cookie's
  contents are read and written.

How the session cookie is used:

* The page load sets it, keeping the existing token when the browser already has a valid cookie for
  this user, so panels open in the same browser share one token. The token is also embedded in the
  page data for the SDK.
* ``ext-connection`` and ``ext-disconnect`` accept a call only when the ``Authorization: Bearer``
  value equals the token in the cookie (compared in constant time). The cookie is ``SameSite=None``,
  so browsers attach it to cross-site requests too; requiring the header as well, which only code
  holding the page data can send, is what keeps another site from driving these endpoints
  (the "double submit" pattern).
* ``ext-connection`` and ``ext-disconnect`` rewrite it when the connection changes. Disconnect
  keeps the token and only turns ``connected`` off, so the SDK's next call still authenticates.

It lasts 30 days, refreshed by each page load, and survives a server restart or scale-to-zero;
changing ``APP_SECRET`` invalidates every cookie, so every open panel gets ``401`` and must reload.

Neither value is encrypted: anyone who can read the cookie (it is ``HttpOnly``, so page scripts
can't) sees the ids and the token in it, but nobody without the app secret can forge or alter one.

Limits of keeping the session in a cookie, which a real partner's stored tokens don't have: it is
per browser (connecting in one browser doesn't connect another, and Disconnect only changes the
cookie in the browser that asked), a browser that refuses the cookie can't use the panel at all, and
the server cannot revoke one before its 30 days are up other than by changing the secret.
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
# How long the connection cookie is honoured; also its ``Max-Age``.
COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60

_STATE = 'state'
_SESSION = 'session'


@dataclass(frozen=True)
class SessionClaims:
  """What a verified session cookie holds: whose it is, its access token, and the connection."""

  user_id: int
  company_id: int
  token: str
  connected: bool


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

  Called by the OAuth callback with the ``state`` the CRM sent back. A session cookie value is
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
  """Return a fresh random access token, the value the panel sends as ``Authorization: Bearer``."""
  return secrets.token_urlsafe(32)


def issue_session(session: SessionClaims, secret: str, now: float) -> str:
  """Sign the session cookie value: this user's access token and whether they are connected.

  Called on every page load (which refreshes the cookie's 30 days) and whenever the connection
  changes, in ``ext-connection`` when the user just finished OAuth and in ``ext-disconnect``.
  """
  return sign(
      {
          'kind': _SESSION,
          'user_id': session.user_id,
          'company_id': session.company_id,
          'token': session.token,
          'connected': session.connected,
          'iat': now,
      },
      secret,
  )


def read_session(value: str | None, secret: str, now: float) -> SessionClaims | None:
  """Return what a session cookie value says, or ``None`` if it is missing, forged or too old.

  Called on the page request (the caller then checks the cookie belongs to the idtoken's user) and
  to authenticate ``ext-connection`` and ``ext-disconnect`` (the caller compares the token with the
  ``Authorization`` header). A malformed value, one signed for another purpose such as a ``state``,
  and one issued more than 30 days ago are all just "no session", never an error.
  """
  if value is None or value == '':
    return None
  payload = verify(value, secret)
  if payload is None or payload.get('kind') != _SESSION:
    return None
  issued = payload.get('iat')
  if not isinstance(issued, int | float) or now - issued > COOKIE_MAX_AGE_SECONDS:
    return None
  user_id = payload.get('user_id')
  company_id = payload.get('company_id')
  token = payload.get('token')
  connected = payload.get('connected')
  if not (isinstance(user_id, int) and isinstance(company_id, int)):
    return None
  if not (isinstance(token, str) and token != '' and isinstance(connected, bool)):
    return None
  return SessionClaims(user_id=user_id, company_id=company_id, token=token, connected=connected)
