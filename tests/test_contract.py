"""The contract models (backend/contract.py): the shapes the SDK reads and the rules on them."""

import pytest
from pydantic import ValidationError

from backend.contract import DEFAULT_API_PREFIX
from backend.contract import ErrorResponse
from backend.contract import ExternalConnection
from backend.contract import IdTokenClaims
from backend.contract import PageData

IDENTITY = {
    'user_id': 5432,
    'company_id': 12345,
    'office_id': 54321,
    'name': 'Jane Agent',
    'email': 'jane.agent@example.com',
}


def a_page_data() -> PageData:
  """Return valid page data: not connected, with one authorization URL."""
  return PageData(
      dialpad_origin='https://dialpad.com',
      access_token='an-access-token',
      external_connection=ExternalConnection(
          connected=False,
          authorization_urls={'acme-crm': 'https://acme.example.com/oauth'},
          name='acme-crm',
      ),
  )


def test_claims_ignore_unknown_claims_and_hide_the_api_key() -> None:
  claims = IdTokenClaims.model_validate({**IDENTITY, 'api_key': 'secret-key-value', 'new_claim': 1})

  assert 'new_claim' not in claims.model_dump()
  assert 'secret-key-value' not in repr(claims)
  assert claims.api_key.get_secret_value() == 'secret-key-value'


def test_claims_do_not_expose_the_csr_claim() -> None:
  claims = IdTokenClaims.model_validate({**IDENTITY, 'api_key': 'k', 'csr': {'csr_has_access': 1}})

  assert 'csr' not in claims.model_dump()
  assert not hasattr(claims, 'csr')


def test_page_data_has_no_place_for_the_api_key_or_a_user() -> None:
  page_data = a_page_data().model_dump()

  for extra in ({'api_key': 'k'}, {'user': IDENTITY}):
    with pytest.raises(ValidationError):
      PageData.model_validate({**page_data, **extra})


def test_page_data_json_never_contains_an_api_key() -> None:
  as_json = a_page_data().model_dump_json()

  assert 'api_key' not in as_json
  assert a_page_data().api_prefix == DEFAULT_API_PREFIX == '/dialpad'


def test_not_connected_requires_an_authorization_url() -> None:
  with pytest.raises(ValidationError, match='authorization_urls'):
    ExternalConnection(connected=False, name='acme-crm')

  connected = ExternalConnection(connected=True, name='acme-crm')
  assert connected.authorization_urls == {}
  assert connected.scopes == []


def test_external_connection_has_the_contracts_shape() -> None:
  connection = ExternalConnection(
      connected=True,
      authorization_urls={
          'acme-crm': 'https://a.example/oauth',
          'acme-sandbox': 'https://b.example/oauth',
      },
      name='acme-crm',
      scopes=['read', 'write_contacts'],
  )

  assert connection.model_dump(mode='json') == {
      'connected': True,
      'authorization_urls': {
          'acme-crm': 'https://a.example/oauth',
          'acme-sandbox': 'https://b.example/oauth',
      },
      'name': 'acme-crm',
      'scopes': ['read', 'write_contacts'],
  }
  with pytest.raises(ValidationError):
    ExternalConnection.model_validate({**connection.model_dump(), 'account_name': 'Acme'})


def test_error_response_is_a_code_and_a_message_only() -> None:
  error = ErrorResponse(code='invalid_idtoken', message='Open this panel from Dialpad.')

  assert error.model_dump(mode='json') == {
      'code': 'invalid_idtoken',
      'message': 'Open this panel from Dialpad.',
  }
  with pytest.raises(ValidationError):
    ErrorResponse.model_validate({'code': 'x', 'message': 'y', 'detail': 'z'})
