"""Decoding idtokens (acme_crm/idtoken.py), against tokens from Dialpad's own encoder (python-jose).

``tests/vectors/dialpad_idtokens.json`` holds tokens built with python-jose the way Dialpad builds
them, so decoding them proves the app reads what Dialpad really sends.
"""

import base64
import json
from pathlib import Path
from typing import Any

import pytest
from jose import jwe as jose_jwe
from jose import jwt as jose_jwt

from acme_crm.idtoken import TEST_CLIENT_SECRET
from acme_crm.idtoken import IdTokenError
from acme_crm.idtoken import decode_idtoken
from acme_crm.idtoken import encode_mock_idtoken

VECTORS = json.loads((Path(__file__).parent / 'vectors' / 'dialpad_idtokens.json').read_text())
DIALPAD_SECRET = str(VECTORS['client_secret'])
# The identity a mock token carries unless a claim is overridden.
DEFAULT_IDENTITY = {
    'user_id': 5432,
    'company_id': 12345,
    'office_id': 54321,
    'name': 'Jane Agent',
    'email': 'jane.agent@example.com',
    'phone_number': '+15555550100',
    'image_url': 'https://example.com/avatars/jane-agent.png',
}


def _dialpad_token(
    payload: dict[str, Any],
    *,
    algorithm: str = 'dir',
    encryption: str = 'A192CBC-HS384',
    key: str | bytes = DIALPAD_SECRET[:48],
    jwt_algorithm: str = 'HS256',
) -> str:
  """Build a token the way Dialpad builds one, with optional variations."""
  jwt_token = jose_jwt.encode(payload, DIALPAD_SECRET, algorithm=jwt_algorithm)
  encrypted = jose_jwe.encrypt(jwt_token, key, algorithm=algorithm, encryption=encryption)
  assert isinstance(encrypted, bytes)
  return encrypted.decode('utf-8')


# Round trips


@pytest.mark.parametrize('case', VECTORS['cases'], ids=[case['name'] for case in VECTORS['cases']])
def test_dialpad_vectors_decode_without_csr(case: dict[str, Any]) -> None:
  claims = decode_idtoken(case['idtoken'], DIALPAD_SECRET)

  expected = case['expected_claims']
  assert claims.api_key.get_secret_value() == expected['api_key']
  assert claims.model_dump(exclude={'api_key'}) == {
      key: value for key, value in expected.items() if key != 'api_key'
  }
  assert 'csr' not in claims.model_dump()
  assert not hasattr(claims, 'csr')


def test_mock_tokens_match_dialpads_format_and_decode_with_python_jose() -> None:
  token = encode_mock_idtoken(
      TEST_CLIENT_SECRET,
      api_key='real-key',
      name='Ada',
      csr={'csr_has_access': False},
  )

  header_segment, encrypted_key = token.split('.')[:2]
  header = json.loads(base64.urlsafe_b64decode(header_segment + '=' * (-len(header_segment) % 4)))
  assert header == {'alg': 'dir', 'enc': 'A192CBC-HS384'}
  assert encrypted_key == '' # direct encryption carries no encrypted key
  inner = jose_jwe.decrypt(token, TEST_CLIENT_SECRET[:48])
  assert inner is not None
  payload = jose_jwt.decode(inner.decode(), TEST_CLIENT_SECRET, algorithms=['HS256'])
  assert payload == {
      **DEFAULT_IDENTITY,
      'name': 'Ada',
      'api_key': 'real-key',
      'csr': {
          'csr_has_access': False
      },
  }


def test_a_mock_token_decodes_to_the_default_identity() -> None:
  claims = decode_idtoken(encode_mock_idtoken(TEST_CLIENT_SECRET), TEST_CLIENT_SECRET)

  assert claims.model_dump(exclude={'api_key'}) == DEFAULT_IDENTITY
  assert claims.api_key.get_secret_value() == 'mock-api-key'


def test_a_mock_token_needs_a_secret_long_enough_for_the_jwe_key() -> None:
  with pytest.raises(ValueError, match='48 characters'):
    encode_mock_idtoken('short')


# Rejections

_PAYLOAD = VECTORS['cases'][0]['expected_claims']


def _unsigned(payload: dict[str, Any]) -> str:
  header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b'=')
  body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=')
  unsigned_jwt = (header + b'.' + body + b'.').decode()
  encrypted = jose_jwe.encrypt(unsigned_jwt, DIALPAD_SECRET[:48], encryption='A192CBC-HS384')
  assert isinstance(encrypted, bytes)
  return encrypted.decode()


def _tampered(token: str) -> str:
  header, key, iv, ciphertext, tag = token.split('.')
  flipped = 'A' if ciphertext[5] != 'A' else 'B'
  return '.'.join([header, key, iv, ciphertext[:5] + flipped + ciphertext[6:], tag])


@pytest.mark.parametrize(
    ('description', 'token', 'secret'),
    [
        ('wrong secret', VECTORS['cases'][0]['idtoken'], 'x' * 50),
        ('tampered ciphertext', _tampered(VECTORS['cases'][0]['idtoken']), DIALPAD_SECRET),
        ('other content encryption',
         _dialpad_token(_PAYLOAD, encryption='A256GCM', key=DIALPAD_SECRET[:32]), DIALPAD_SECRET),
        ('other key management',
         _dialpad_token(_PAYLOAD, algorithm='A192KW',
                        key=DIALPAD_SECRET[:24].encode()), DIALPAD_SECRET),
        ('other JWT algorithm', _dialpad_token(_PAYLOAD, jwt_algorithm='HS512'), DIALPAD_SECRET),
        ('not a JWE', 'not-a-token', DIALPAD_SECRET),
        ('a bare JWT', jose_jwt.encode(_PAYLOAD, DIALPAD_SECRET), DIALPAD_SECRET),
        ('an unsigned inner JWT', _unsigned(_PAYLOAD), DIALPAD_SECRET),
        ('empty', '', DIALPAD_SECRET),
        ('missing', None, DIALPAD_SECRET),
    ],
)
def test_bad_tokens_raise_the_typed_error(description: str, token: str | None, secret: str) -> None:
  with pytest.raises(IdTokenError) as raised:
    decode_idtoken(token, secret)

  assert DIALPAD_SECRET not in str(raised.value), description


@pytest.mark.parametrize('missing', ['user_id', 'company_id', 'office_id', 'api_key'])
def test_missing_required_claims_raise_the_typed_error(missing: str) -> None:
  payload = {key: value for key, value in _PAYLOAD.items() if key != missing}

  with pytest.raises(IdTokenError):
    decode_idtoken(_dialpad_token(payload), DIALPAD_SECRET)


def test_a_short_client_secret_is_a_configuration_error() -> None:
  with pytest.raises(ValueError, match='48 characters'):
    decode_idtoken(VECTORS['cases'][0]['idtoken'], 'short')
