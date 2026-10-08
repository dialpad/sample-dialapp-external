"""The demo call to Dialpad's API with the idtoken's api key (acme_crm/dialpad_api.py).

Each test runs the real Dialpad client against ``FakeDialpad``, a real HTTP server on a local port,
so the request that is checked is the one the client really sends. The page must render whatever
Dialpad's API does.
"""

import logging
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any

from acme_crm.idtoken import TEST_CLIENT_SECRET
from acme_crm.idtoken import encode_mock_idtoken
from tests.conftest import Env
from tests.conftest import page_data_of

if TYPE_CHECKING:
  import pytest

API_KEY = 'real-looking-api-key-0123456789'


def demo_of(data: dict[str, Any]) -> dict[str, Any]:
  """Return the demo result the page data's ``app`` field carries."""
  return data['app']['dialpadApi']


async def load_with_key(env: Env, api_key: str = API_KEY) -> dict[str, Any]:
  """Load the page with an idtoken carrying ``api_key`` and return the embedded page data."""
  token = encode_mock_idtoken(TEST_CLIENT_SECRET, api_key=api_key)
  response = await env.load_page(token)
  assert response.status_code == HTTPStatus.OK
  return page_data_of(response)


async def test_the_page_asks_dialpad_who_the_key_belongs_to_and_embeds_a_few_fields(
    env: Env) -> None:
  data = await load_with_key(env)

  assert env.dialpad.requests == [('/api/v2/users/me', f'Bearer {API_KEY}')]
  assert demo_of(data) == {
      'status': 'ok',
      'user': {
          'id': 5432,
          'displayName': 'Jane Agent',
          'email': 'jane.agent@example.com',
          'state': 'active',
      },
  }


async def test_a_user_without_an_email_still_gives_an_ok_result(env: Env) -> None:
  env.dialpad.user = {'id': 1, 'display_name': 'No Email', 'emails': []}

  data = await load_with_key(env)

  assert demo_of(data)['status'] == 'ok'
  assert demo_of(data)['user']['email'] is None


async def test_a_refused_key_still_renders_the_page_as_unavailable(env: Env) -> None:
  env.dialpad.status = HTTPStatus.UNAUTHORIZED

  data = await load_with_key(env)

  assert demo_of(data) == {'status': 'unavailable', 'user': None}
  assert data['access_token']


async def test_an_unreachable_dialpad_still_renders_the_page_as_unavailable(env: Env) -> None:
  env.dialpad.close()

  data = await load_with_key(env)

  assert demo_of(data) == {'status': 'unavailable', 'user': None}


async def test_a_dialpad_slower_than_the_timeout_still_renders_the_page_as_unavailable(
    env: Env) -> None:
  env.dialpad.delay = 3.0

  data = await load_with_key(env)

  assert demo_of(data) == {'status': 'unavailable', 'user': None}
  assert len(env.dialpad.requests) == 1


async def test_an_unreadable_answer_is_unavailable_too(env: Env) -> None:
  env.dialpad.raw = b'not json'

  data = await load_with_key(env)

  assert demo_of(data)['status'] == 'unavailable'


async def test_an_answer_that_is_not_a_json_object_is_unavailable_too(env: Env) -> None:
  env.dialpad.raw = b'[]'

  data = await load_with_key(env)

  assert demo_of(data) == {'status': 'unavailable', 'user': None}


async def test_local_mode_makes_no_call_and_says_so(local_env: Env) -> None:
  data = await local_env.page_data()

  assert demo_of(data) == {'status': 'skipped', 'user': None}
  assert local_env.dialpad.requests == []


async def test_the_api_key_never_reaches_the_page_or_the_logs(
    env: Env,
    caplog: pytest.LogCaptureFixture,
) -> None:
  caplog.set_level(logging.DEBUG)
  outcomes = []
  for status in (HTTPStatus.OK, HTTPStatus.UNAUTHORIZED, HTTPStatus.INTERNAL_SERVER_ERROR):
    env.dialpad.status = status
    token = encode_mock_idtoken(TEST_CLIENT_SECRET, api_key=API_KEY)
    response = await env.load_page(token)
    outcomes.append((response.text, response.headers))

  for text, headers in outcomes:
    assert API_KEY not in text
    assert API_KEY not in str(dict(headers))
  assert API_KEY not in caplog.text
