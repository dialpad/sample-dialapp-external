"""The Sanic app (backend/app.py): page, access tokens, connection, fake OAuth, disconnect, logs."""

import logging
from typing import TYPE_CHECKING
from urllib.parse import parse_qs
from urllib.parse import urlsplit

import pytest
from dialpad_dialapp_toolkit.testing import TEST_CLIENT_SECRET
from dialpad_dialapp_toolkit.testing import encode_mock_idtoken

from backend import signing
from backend.app import ACCOUNT_NAME
from backend.app import FAKE_CODE
from tests.conftest import APP_SECRET
from tests.conftest import DIALPAD_ORIGIN
from tests.conftest import Env
from tests.conftest import bearer
from tests.conftest import cookie_header
from tests.conftest import idtoken_for
from tests.conftest import json_of
from tests.conftest import page_data_of

if TYPE_CHECKING:
  from httpx import Response

# The test client logs every URL it requests; those are not the app's logs.
HTTP_CLIENT_LOGGERS = ('httpx', 'httpcore')
JANE = {'user_id': 5432, 'company_id': 12345}
PAT = {'user_id': 777, 'company_id': 12345}


def state_from(authorize_url: str) -> str:
  return parse_qs(urlsplit(authorize_url).query)['state'][0]


async def finish_oauth(env: Env, authorize_url: str) -> None:
  """Follow the fake authorize redirect and the callback, as the popup does."""
  authorize = await env.get(authorize_url, follow_redirects=False)
  assert authorize.status_code == 302
  callback = await env.get(authorize.headers['location'])
  assert callback.status_code == 200


async def connect(env: Env, token: str, authorize_url: str) -> Response:
  """Complete OAuth for a user and return the connection response that sets the cookie."""
  await finish_oauth(env, authorize_url)
  return await env.get('/dialpad/connection', headers=bearer(token))


# --- token decoding with mock tokens ---------------------------------------------------------


async def test_a_valid_idtoken_renders_the_page_with_the_users_claims(env: Env) -> None:
  token = encode_mock_idtoken(TEST_CLIENT_SECRET, user_id=42, company_id=7, name='Ada Lovelace')

  data = await env.page_data(token)

  assert data['user']['user_id'] == 42
  assert data['user']['company_id'] == 7
  assert data['user']['name'] == 'Ada Lovelace'


@pytest.mark.parametrize('bad', ['', 'not-a-token', 'a.b.c.d.e'])
async def test_a_bad_idtoken_gets_a_401_html_page(env: Env, bad: str) -> None:
  response = await env.get('/', params={'idtoken': bad})

  assert response.status_code == 401
  assert response.headers['content-type'].startswith('text/html')


async def test_a_missing_idtoken_gets_a_401_html_page(env: Env) -> None:
  response = await env.get('/')

  assert response.status_code == 401
  assert response.headers['content-type'].startswith('text/html')


async def test_an_idtoken_signed_with_another_secret_gets_a_401(env: Env) -> None:
  token = encode_mock_idtoken('another-secret-that-is-at-least-forty-eight-chars-long')

  assert (await env.load_page(token)).status_code == 401


# --- the page's data and headers ---------------------------------------------------------------


async def test_the_page_embeds_page_data_and_never_the_api_key_or_csr(env: Env) -> None:
  token = encode_mock_idtoken(
      TEST_CLIENT_SECRET,
      api_key='real-looking-api-key',
      csr={'internal': 'only-for-dialpad-support'},
  )

  response = await env.load_page(token)
  data = page_data_of(response)

  assert data['version'] == 1
  assert data['dialpad_origin'] == DIALPAD_ORIGIN
  assert data['api_prefix'] == '/dialpad'
  assert data['connection']['connected'] is False
  assert data['connection']['authorize_url'].startswith(f'{env.settings.base_url}/oauth/')
  assert 'real-looking-api-key' not in response.text
  assert 'only-for-dialpad-support' not in response.text
  assert 'api_key' not in response.text
  assert 'csr' not in response.text


async def test_the_api_responses_never_contain_the_api_key_or_csr(env: Env) -> None:
  token = encode_mock_idtoken(
      TEST_CLIENT_SECRET,
      api_key='real-looking-api-key',
      csr={'internal': 'only-for-dialpad-support'},
  )
  data = await env.page_data(token)
  access_token = data['access_token']
  connected = await connect(env, access_token, data['connection']['authorize_url'])
  not_connected = await env.get('/dialpad/connection', headers=bearer(access_token))
  disconnected = await env.post('/dialpad/disconnect', headers=bearer(access_token))

  for response in (connected, not_connected, disconnected):
    assert 'real-looking-api-key' not in response.text
    assert 'only-for-dialpad-support' not in response.text
    assert 'api_key' not in response.text
    assert 'csr' not in response.text


async def test_the_page_carries_the_security_headers_and_a_matching_nonce(env: Env) -> None:
  response = await env.load_page()

  csp = response.headers['content-security-policy']
  nonce = csp.split("'nonce-")[1].split("'")[0]
  assert f'frame-ancestors {DIALPAD_ORIGIN}' in csp
  assert "script-src 'self'" in csp
  assert 'unsafe-eval' not in csp
  assert f'nonce="{nonce}"' in response.text
  assert response.headers['referrer-policy'] == 'no-referrer'
  assert response.headers['cache-control'] == 'no-store'
  assert '/assets/main-abc.js' in response.text


async def test_local_mode_changes_the_csp_in_three_places_only(env: Env, local_env: Env) -> None:
  production = (await env.load_page()).headers['content-security-policy']
  local = (await local_env.load_page()).headers['content-security-policy']

  def directives(csp: str) -> dict[str, list[str]]:
    parts = [part.strip().split() for part in csp.split(';')]
    return {part[0]: part[1:] for part in parts}

  prod, dev = directives(production), directives(local)
  assert dev['frame-ancestors'] == ['http://localhost:5173']
  assert 'http://localhost:5173' in dev['script-src']
  assert dev['connect-src'] == ["'self'", 'ws://localhost:5173']
  assert 'connect-src' not in prod
  assert dev['script-src'][:2] == [*prod['script-src'][:1], dev['script-src'][1]]
  assert {
      k: v for k, v in dev.items() if k not in {'frame-ancestors', 'script-src', 'connect-src'}
  } == {
      k: v for k, v in prod.items() if k not in {'frame-ancestors', 'script-src', 'connect-src'}
  }


async def test_the_dev_route_exists_only_in_local_mode(env: Env, local_env: Env) -> None:
  assert (await env.get('/dev/frame-url')).status_code == 404

  response = await local_env.get('/dev/frame-url')

  assert response.status_code == 200
  assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'
  framed = await local_env.get(json_of(response)['url'].removeprefix('http://localhost:8000'))
  assert framed.status_code == 200


# --- the per-user access token -------------------------------------------------------------------


async def test_a_user_gets_the_same_access_token_on_every_page_load(env: Env) -> None:
  first = (await env.page_data())['access_token']
  second = (await env.page_data())['access_token']

  assert first == second


async def test_different_users_get_different_access_tokens(env: Env) -> None:
  jane = await env.page_data(idtoken_for(**JANE))
  pat = await env.page_data(idtoken_for(**PAT))

  assert jane['access_token'] != pat['access_token']


# --- the connection endpoint: every branch -----------------------------------------------------


async def test_no_cookie_means_not_connected_with_a_fresh_authorize_url(env: Env) -> None:
  token = (await env.page_data())['access_token']

  response = await env.get('/dialpad/connection', headers=bearer(token))

  assert response.status_code == 200
  body = json_of(response)
  assert body['connected'] is False
  assert body['account_name'] == ACCOUNT_NAME
  assert 'authorize_url' in body
  assert 'set-cookie' not in response.headers


async def test_an_unknown_or_missing_access_token_gets_a_401(env: Env) -> None:
  assert (await env.get('/dialpad/connection', headers=bearer('never-issued'))).status_code == 401
  assert (await env.get('/dialpad/connection')).status_code == 401
  assert (await env.post('/dialpad/disconnect', headers=bearer('never-issued'))).status_code == 401


async def test_a_stored_result_is_consumed_and_sets_the_connection_cookie(env: Env) -> None:
  data = await env.page_data()
  token = data['access_token']

  response = await connect(env, token, data['connection']['authorize_url'])

  assert json_of(response) == {'connected': True, 'account_name': ACCOUNT_NAME}
  cookie = response.headers['set-cookie']
  assert cookie.startswith('__Host-acme_session=')
  for attribute in ('Path=/', 'Secure', 'HttpOnly', 'SameSite=None', 'Partitioned',
                    'Max-Age=2592000'):
    assert attribute in cookie
  # Consumed once: the next check without the cookie is not connected.
  again = await env.get('/dialpad/connection', headers=bearer(token))
  assert json_of(again)['connected'] is False


async def test_a_valid_cookie_means_connected_on_the_connection_endpoint_and_on_the_page(
    env: Env,) -> None:
  data = await env.page_data()
  token = data['access_token']
  cookie = cookie_header(await connect(env, token, data['connection']['authorize_url']))

  response = await env.get('/dialpad/connection', headers=bearer(token) | {'Cookie': cookie})
  page = await env.page_data(cookie=cookie)

  assert json_of(response)['connected'] is True
  assert 'set-cookie' not in response.headers
  assert page['connection']['connected'] is True
  assert page['connection']['account_name'] == ACCOUNT_NAME


async def test_a_result_recorded_for_another_user_is_not_consumed(env: Env) -> None:
  jane = await env.page_data(idtoken_for(**JANE))
  pat = await env.page_data(idtoken_for(**PAT))
  await finish_oauth(env, jane['connection']['authorize_url'])

  pat_check = await env.get('/dialpad/connection', headers=bearer(pat['access_token']))
  jane_check = await env.get('/dialpad/connection', headers=bearer(jane['access_token']))

  assert json_of(pat_check)['connected'] is False
  assert 'set-cookie' not in pat_check.headers
  assert json_of(jane_check)['connected'] is True


async def test_a_cookie_for_another_user_counts_as_not_connected(env: Env) -> None:
  jane = await env.page_data(idtoken_for(**JANE))
  pat = await env.page_data(idtoken_for(**PAT))
  jane_cookie = cookie_header(
      await connect(env, jane['access_token'], jane['connection']['authorize_url']),)

  api = await env.get(
      '/dialpad/connection',
      headers=bearer(pat['access_token']) | {'Cookie': jane_cookie},
  )
  page = await env.page_data(idtoken_for(**PAT), cookie=jane_cookie)

  assert json_of(api)['connected'] is False
  assert page['connection']['connected'] is False


async def test_a_forged_cookie_counts_as_not_connected(env: Env) -> None:
  data = await env.page_data()
  forged = signing.issue_cookie(5432, 12345, 'not-the-app-secret', env.clock())

  page = await env.page_data(cookie=f'__Host-acme_session={forged}')

  assert page['connection']['connected'] is False
  assert data['connection']['connected'] is False


# --- the fake OAuth round trip -----------------------------------------------------------------


async def test_fake_authorize_redirects_to_the_callback_with_the_state_and_a_fixed_code(
    env: Env,) -> None:
  data = await env.page_data()
  authorize_url = data['connection']['authorize_url']

  response = await env.get(authorize_url, follow_redirects=False)

  location = urlsplit(response.headers['location'])
  assert response.status_code == 302
  target = f'{location.scheme}://{location.netloc}{location.path}'
  assert target == f'{env.settings.base_url}/oauth/callback'
  assert parse_qs(location.query) == {'state': [state_from(authorize_url)], 'code': [FAKE_CODE]}
  assert 'set-cookie' not in response.headers


async def test_the_callback_returns_the_close_popup_page_for_the_dialpad_origin(env: Env) -> None:
  data = await env.page_data()
  authorize = await env.get(data['connection']['authorize_url'], follow_redirects=False)

  response = await env.get(authorize.headers['location'])

  assert response.status_code == 200
  assert DIALPAD_ORIGIN in response.text
  assert 'close_popup' in response.text
  assert 'set-cookie' not in response.headers


async def test_an_expired_state_at_the_callback_records_nothing(env: Env) -> None:
  data = await env.page_data()
  token = data['access_token']
  authorize = await env.get(data['connection']['authorize_url'], follow_redirects=False)
  env.clock.advance(signing.STATE_TTL_SECONDS + 1)

  callback = await env.get(authorize.headers['location'])
  check = await env.get('/dialpad/connection', headers=bearer(token))

  assert callback.status_code == 400
  assert json_of(check)['connected'] is False


async def test_a_forged_state_at_the_callback_records_nothing(env: Env) -> None:
  token = (await env.page_data())['access_token']
  forged = signing.issue_state(5432, 12345, 'not-the-app-secret', env.clock())

  callback = await env.get('/oauth/callback', params={'state': forged, 'code': FAKE_CODE})
  check = await env.get('/dialpad/connection', headers=bearer(token))

  assert callback.status_code == 400
  assert json_of(check)['connected'] is False


async def test_the_callback_rejects_a_wrong_code_and_authorize_requires_a_state(env: Env) -> None:
  state = signing.issue_state(5432, 12345, APP_SECRET, env.clock())

  wrong_code = await env.get('/oauth/callback', params={'state': state, 'code': 'other'})
  no_state = await env.get('/oauth/fake-authorize', follow_redirects=False)

  assert wrong_code.status_code == 400
  assert no_state.status_code == 400


async def test_a_result_expires_after_five_minutes(env: Env) -> None:
  data = await env.page_data()
  token = data['access_token']
  await finish_oauth(env, data['connection']['authorize_url'])
  env.clock.advance(5 * 60)

  check = await env.get('/dialpad/connection', headers=bearer(token))

  assert json_of(check)['connected'] is False


# --- disconnect --------------------------------------------------------------------------------


async def test_disconnect_clears_the_cookie_and_answers_not_connected(env: Env) -> None:
  data = await env.page_data()
  token = data['access_token']
  cookie = cookie_header(await connect(env, token, data['connection']['authorize_url']))

  response = await env.post('/dialpad/disconnect', headers=bearer(token) | {'Cookie': cookie})

  body = json_of(response)
  assert response.status_code == 200
  assert body['connected'] is False
  assert 'authorize_url' in body
  cleared = response.headers['set-cookie']
  assert cleared.startswith('__Host-acme_session=')
  for attribute in ('Max-Age=0', 'Secure', 'HttpOnly', 'SameSite=None', 'Partitioned', 'Path=/'):
    assert attribute in cleared


# --- secrets and logs --------------------------------------------------------------------------


async def test_neither_the_idtoken_nor_the_access_token_is_logged(
    env: Env,
    caplog: pytest.LogCaptureFixture,
) -> None:
  caplog.set_level(logging.DEBUG)
  idtoken = encode_mock_idtoken(TEST_CLIENT_SECRET)

  data = await env.page_data(idtoken)
  token = data['access_token']
  await connect(env, token, data['connection']['authorize_url'])
  await env.post('/dialpad/disconnect', headers=bearer(token))
  await env.get('/', params={'idtoken': 'bad' + idtoken})
  await env.get('/dialpad/connection', headers=bearer('wrong-' + token))

  logged = '\n'.join(
      record.getMessage() for record in caplog.records if record.name not in HTTP_CLIENT_LOGGERS)
  assert idtoken not in logged
  assert token not in logged
  assert env.app.config.ACCESS_LOG is False


async def test_an_unexpected_error_is_logged_without_the_query_string(
    env: Env,
    caplog: pytest.LogCaptureFixture,
) -> None:
  @env.app.get('/boom')
  async def boom(_request: object) -> None:
    message = 'boom'
    raise RuntimeError(message)

  response = await env.get('/boom', params={'idtoken': 'secret-token-value'})

  assert response.status_code == 500
  assert 'secret-token-value' not in '\n'.join(r.getMessage() for r in caplog.records)
  assert any('/boom' in r.getMessage() for r in caplog.records)
