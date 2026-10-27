"""The demo call to Dialpad's API with the idtoken's api key (demo/dialpad_api.py).

Each test runs the real Dialpad client against ``FakeDialpad``, a real HTTP server on a local port,
so the request that is checked is the one the client really sends. The page must render whatever
Dialpad's API does.
"""

import logging
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any

import pytest

from acme_dialpad_rightbar.dialpad.idtoken import TEST_CLIENT_SECRET
from acme_dialpad_rightbar.dialpad.idtoken import encode_mock_idtoken
from tests.conftest import Env
from tests.conftest import page_data_of

if TYPE_CHECKING:
  from collections.abc import Callable

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

  # A user without an email still gives an ok result.
  env.dialpad.user = {'id': 1, 'display_name': 'No Email', 'emails': []}
  no_email = await load_with_key(env)
  assert demo_of(no_email)['status'] == 'ok'
  assert demo_of(no_email)['user']['email'] is None


def _refuse_the_key(env: Env) -> None:
  env.dialpad.status = HTTPStatus.UNAUTHORIZED


def _stop_dialpad(env: Env) -> None:
  env.dialpad.close()


def _slow_down_dialpad(env: Env) -> None:
  env.dialpad.delay = 3.0


def _answer_with_text(env: Env) -> None:
  env.dialpad.raw = b'not json'


def _answer_with_a_json_array(env: Env) -> None:
  env.dialpad.raw = b'[]'


@pytest.mark.parametrize(
    'break_dialpad',
    [
        _refuse_the_key, _stop_dialpad, _slow_down_dialpad, _answer_with_text,
        _answer_with_a_json_array
    ],
    ids=['refused key', 'unreachable', 'slower than the timeout', 'not json', 'not a json object'],
)
async def test_any_failure_of_the_call_still_renders_the_page_as_unavailable(
    env: Env, break_dialpad: Callable[[Env], None]) -> None:
  break_dialpad(env)

  data = await load_with_key(env)

  assert demo_of(data) == {'status': 'unavailable', 'user': None}
  assert data['access_token']
  assert len(env.dialpad.requests) <= 1 # no retry


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
