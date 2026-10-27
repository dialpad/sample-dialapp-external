"""Decoding the idtoken Dialpad appends to the iframe panel's page URL, and minting mock ones.

The idtoken is a compact JWE (``dir``, ``A192CBC-HS384``) keyed with the first 48 characters of the
app's client secret, wrapping an HS256 JWT signed with the full secret. Only those algorithms are
allowed. ``decode_idtoken`` is called once per page load, before anything is rendered: the claims
say which Dialpad user, company and office opened the iframe panel, and carry that user's API key.
"""

import json
from typing import Any

from joserfc import jwe
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import OctKey
from pydantic import ValidationError

from acme_dialpad_rightbar.dialpad.contract import IdTokenClaims

JWE_ALGORITHM = 'dir'
JWE_ENCRYPTION = 'A192CBC-HS384'
JWT_ALGORITHM = 'HS256'

# Length of the JWE key taken from the client secret. Dialpad generates every client secret at 50
# characters, so the 48-character key always exists.
JWE_KEY_LENGTH = 48

# A fixed 50-character client secret, the length Dialpad generates, for tests and local mode. Never
# use it for a real app.
TEST_CLIENT_SECRET = 'test-client-secret-0123456789-abcdefghijklmnopqrst' # noqa: S105


class IdTokenError(Exception):
  """The idtoken is missing, malformed, not verifiable with this secret, or lacks required claims.

  Raised by ``decode_idtoken``. The page route answers ``401`` with it and renders no page data. The
  message never contains the token or the secret, so it is safe to log.
  """


def _jwe_key(client_secret: str) -> OctKey:
  """Return the JWE key: the first 48 characters of the client secret."""
  if len(client_secret) < JWE_KEY_LENGTH:
    msg = f'client secret must be at least {JWE_KEY_LENGTH} characters'
    raise ValueError(msg)
  return OctKey.import_key(client_secret[:JWE_KEY_LENGTH].encode())


def decode_idtoken(idtoken: str | None, client_secret: str) -> IdTokenClaims:
  """Decrypt and verify a Dialpad idtoken, returning its claims without ``csr``.

  Called by the page route with the ``idtoken`` query parameter and the app's client secret. The
  returned claims identify the Dialpad user, company and office, and carry the user's API key, which
  stays on the server: no claim goes into the page data. Nothing is cached or stored; each call
  decodes from scratch.

  Raises ``IdTokenError`` for any token that doesn't decode and verify, and ``ValueError`` when the
  client secret itself is shorter than 48 characters (a configuration error, not a bad token).
  """
  jwe_key = _jwe_key(client_secret)
  if idtoken is None or idtoken == '':
    msg = 'idtoken is missing'
    raise IdTokenError(msg)

  try:
    encrypted = jwe.decrypt_compact(
        idtoken,
        jwe_key,
        algorithms=[JWE_ALGORITHM, JWE_ENCRYPTION],
    )
    if encrypted.plaintext is None:
      msg = 'idtoken has no payload'
      raise IdTokenError(msg)
    token = jwt.decode(
        encrypted.plaintext,
        OctKey.import_key(client_secret.encode()),
        algorithms=[JWT_ALGORITHM],
    )
  except (JoseError, ValueError, TypeError, json.JSONDecodeError) as error:
    msg = 'idtoken could not be decrypted and verified'
    raise IdTokenError(msg) from error

  claims: dict[str, Any] = dict(token.claims)
  claims.pop('csr', None)
  try:
    return IdTokenClaims.model_validate(claims)
  except ValidationError as error:
    msg = 'idtoken is missing required claims'
    raise IdTokenError(msg) from error


def encode_mock_idtoken(secret: str, *, api_key: str = 'mock-api-key', **claims: object) -> str:
  """Return a token in Dialpad's exact format, signed with ``secret`` (never the environment).

  Used where Dialpad isn't there to mint one: ``/dev/frame-url`` in local mode and the tests, to
  produce the ``idtoken`` query parameter for a page request. ``decode_idtoken`` with the same
  secret returns its claims. Every claim has a default (user 5432, company 12345, office 54321, Jane
  Agent) and can be overridden; extra keyword arguments become extra claims, so a test can add a
  ``csr`` claim or one Dialpad might add later.

  Raises ``ValueError`` when ``secret`` is shorter than 48 characters.
  """
  if len(secret) < JWE_KEY_LENGTH:
    msg = f'secret must be at least {JWE_KEY_LENGTH} characters'
    raise ValueError(msg)
  payload = {
      'user_id': 5432,
      'company_id': 12345,
      'office_id': 54321,
      'name': 'Jane Agent',
      'email': 'jane.agent@example.com',
      'phone_number': '+15555550100',
      'image_url': 'https://example.com/avatars/jane-agent.png',
      'api_key': api_key,
      **claims,
  }
  inner = jwt.encode({'alg': JWT_ALGORITHM}, payload, OctKey.import_key(secret.encode()))
  return jwe.encrypt_compact(
      {
          'alg': JWE_ALGORITHM,
          'enc': JWE_ENCRYPTION
      },
      inner,
      OctKey.import_key(secret[:JWE_KEY_LENGTH].encode()),
      algorithms=[JWE_ALGORITHM, JWE_ENCRYPTION],
  )
