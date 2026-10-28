"""Signed values, and random access tokens.

A signed value is ``<base64url JSON>.<base64url HMAC-SHA256>``, signed with the app secret. It
carries a ``kind`` so a value signed for one purpose is never accepted for another. The OAuth
``state`` (``acme_dialpad_rightbar.connect.state``) and the demo's storage cookie
(``acme_dialpad_rightbar.demo.fake_storage``) are both signed this way, under different kinds.
"""

import base64
import binascii
import hashlib
import hmac
import json
import secrets


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


def new_access_token() -> str:
  """Return a fresh random access token: what the iframe panel sends as a bearer token."""
  return secrets.token_urlsafe(32)
