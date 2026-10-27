"""The Sanic app (``acme_dialpad_rightbar``): page, tokens, connection, OAuth, logs.

The CRM record's routes are tested in ``test_crm.py``.
"""

import logging
import re
from dataclasses import replace
from typing import TYPE_CHECKING
from urllib.parse import parse_qs
from urllib.parse import urlsplit

import pytest

from acme_dialpad_rightbar import signing
from acme_dialpad_rightbar.context import CLIENT_NAME
from acme_dialpad_rightbar.context import CONNECTED_SCOPES
from acme_dialpad_rightbar.demo import fake_storage
from acme_dialpad_rightbar.demo.oauth import FAKE_CODE
from acme_dialpad_rightbar.idtoken import TEST_CLIENT_SECRET
from acme_dialpad_rightbar.idtoken import encode_mock_idtoken
from tests.conftest import APP_SECRET
from tests.conftest import Env
from tests.conftest import authorize_url_of
from tests.conftest import bearer
from tests.conftest import connect
from tests.conftest import cookie_header
from tests.conftest import finish_oauth
from tests.conftest import idtoken_for
from tests.conftest import json_of
from tests.conftest import page_data_of
from tests.conftest import press_authorize

if TYPE_CHECKING:
  from collections.abc import Callable

# The test client logs every URL it requests; those are not the app's logs.
HTTP_CLIENT_LOGGERS = ('httpx', 'httpcore')
JANE = {'user_id': 5432, 'company_id': 12345}
PAT = {'user_id': 777, 'company_id': 12345}


def state_from(authorize_url: str) -> str:
  """Return the signed ``state`` query parameter of an authorize URL."""
  return parse_qs(urlsplit(authorize_url).query)['state'][0]


# --- token decoding with mock tokens ---------------------------------------------------------


@pytest.mark.parametrize(
    'idtoken',
    [
        '',
        'not-a-token',
        'a.b.c.d.e',
        None,
        encode_mock_idtoken('another-secret-that-is-at-least-forty-eight-chars-long'),
    ],
    ids=['empty', 'not a token', 'five segments', 'missing', 'signed with another secret'],
)
async def test_an_idtoken_that_does_not_decode_gets_a_401_html_page(env: Env,
                                                                    idtoken: str | None) -> None:
  response = await env.get('/', params={} if idtoken is None else {'idtoken': idtoken})

  assert response.status_code == 401
  assert response.headers['content-type'].startswith('text/html')


# --- the page's data and headers ---------------------------------------------------------------


async def test_the_page_embeds_page_data_and_nothing_from_the_idtoken(env: Env) -> None:
  token = encode_mock_idtoken(
      TEST_CLIENT_SECRET,
      name='Ada Lovelace',
      api_key='real-looking-api-key',
      csr={'internal': 'only-for-dialpad-support'},
  )

  response = await env.load_page(token)
  data = page_data_of(response)

  assert response.status_code == 200
  assert data['version'] == 1
  assert data['dialpad_origin'] == env.settings.dialpad_origin
  assert 'api_prefix' not in data
  assert data['access_token']
  connection = data['external_connection']
  assert connection['connected'] is False
  assert connection['name'] == CLIENT_NAME
  assert connection['scopes'] == []
  assert list(connection['authorization_urls']) == [CLIENT_NAME]
  assert authorize_url_of(data).startswith(f'{env.settings.base_url}/oauth/')
  # The SDK asks Dialpad for the user (get/user); nothing from the idtoken is rendered.
  assert 'user' not in data
  assert 'Ada Lovelace' not in response.text
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
  panel = await env.open_panel(token)
  connected = await connect(env, panel)
  not_connected = await env.get('/dialpad/ext-connection', headers=panel.headers)
  disconnected = await env.post('/dialpad/ext-disconnect', headers=panel.headers)

  for response in (connected, not_connected, disconnected):
    assert 'real-looking-api-key' not in response.text
    assert 'only-for-dialpad-support' not in response.text
    assert 'api_key' not in response.text
    assert 'csr' not in response.text
    assert 'real-looking-api-key' not in response.headers.get('set-cookie', '')


async def test_the_page_puts_the_same_nonce_in_its_policy_and_its_scripts(env: Env) -> None:
  # The policy's other directives and headers are covered by test_pages; this is the wiring.
  response = await env.load_page()

  csp = response.headers['content-security-policy']
  nonce = csp.split("'nonce-")[1].split("'")[0]
  assert f'frame-ancestors {env.settings.dialpad_origin}' in csp
  assert f'nonce="{nonce}"' in response.text
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


# --- the storage cookie and the access token ------------------------------------------------------


async def test_the_page_sets_the_storage_cookie_that_holds_the_access_token(env: Env) -> None:
  response = await env.load_page()

  cookie = response.headers['set-cookie']
  assert cookie.startswith('__Host-acme_session=')
  for attribute in ('Path=/', 'Secure', 'HttpOnly', 'SameSite=None', 'Partitioned',
                    'Max-Age=2592000'):
    assert attribute in cookie
  claims = fake_storage.read_cookie(
      cookie_header(response).split('=', 1)[1],
      APP_SECRET,
      env.clock(),
  )
  assert claims is not None
  assert claims.token == page_data_of(response)['access_token']
  assert (claims.user_id, claims.company_id, claims.connected) == (5432, 12345, False)


async def test_a_cookie_for_another_user_is_replaced_not_reused(env: Env) -> None:
  jane = await env.open_panel(idtoken_for(**JANE))
  await connect(env, jane)

  pat = await env.open_panel(idtoken_for(**PAT), cookie=jane.cookie)

  assert pat.token != jane.token
  assert pat.data['external_connection']['connected'] is False
  # Pat's page replaced the browser's cookie, so Jane's open iframe panel no longer authenticates.
  stale = await env.get('/dialpad/ext-connection',
                        headers=bearer(jane.token) | {'Cookie': pat.cookie})
  assert stale.status_code == 401


# --- the connection endpoint: every branch -----------------------------------------------------


async def test_a_first_page_load_is_not_connected_and_gets_a_fresh_authorize_url(env: Env) -> None:
  panel = await env.open_panel()

  response = await env.get('/dialpad/ext-connection', headers=panel.headers)

  assert response.status_code == 200
  body = json_of(response)
  assert body['connected'] is False
  assert body['name'] == CLIENT_NAME
  assert body['scopes'] == []
  assert list(body['authorization_urls']) == [CLIENT_NAME]
  assert body['authorization_urls'][CLIENT_NAME] != authorize_url_of(panel.data)
  assert 'set-cookie' not in response.headers


# Every route the iframe panel calls: the SDK's two and the app's own.
PANEL_ROUTES = [
    ('GET', '/dialpad/ext-connection'),
    ('POST', '/dialpad/ext-disconnect'),
    ('POST', '/api/contact'), # crm-record
]


async def test_every_panel_route_needs_the_bearer_token_and_the_cookie_to_match(env: Env) -> None:
  panel = await env.open_panel()
  other = await env.open_panel()
  cookie = {'Cookie': panel.cookie}
  rejected = [
      cookie, # no bearer header
      bearer(panel.token), # no cookie
      bearer('never-issued') | cookie,
      bearer(other.token) | cookie, # another browser's token
      {
          'Authorization': f'Basic {panel.token}'
      } | cookie, # not a bearer token
      bearer(panel.token) | {
          'Cookie': 'x=y'
      }, # a cookie that isn't the app's storage cookie
  ]

  for method, path in PANEL_ROUTES:
    for headers in rejected:
      # The token is checked before the body is read, so any JSON body works.
      kwargs = {'json': {}} if method == 'POST' else {}
      response = await (env.get if method == 'GET' else env.post)(path, headers=headers, **kwargs)
      assert response.status_code == 401, (method, path, headers)
      assert json_of(response)['code'] == 'invalid_access_token'
  assert (await env.get('/dialpad/ext-connection', headers=panel.headers)).status_code == 200


async def test_a_stored_result_is_consumed_and_rewrites_the_storage_cookie(env: Env) -> None:
  panel = await env.open_panel()
  old_cookie = panel.cookie

  response = await connect(env, panel)

  body = json_of(response)
  assert body['connected'] is True
  assert body['name'] == CLIENT_NAME
  assert body['scopes'] == CONNECTED_SCOPES
  # Even when connected there is a fresh authorize URL, which the contract's shape allows.
  assert list(body['authorization_urls']) == [CLIENT_NAME]
  # The same access token, now with the connection on; the old cookie still says not connected.
  claims = fake_storage.read_cookie(panel.cookie.split('=', 1)[1], APP_SECRET, env.clock())
  assert claims is not None
  assert (claims.token, claims.connected) == (panel.token, True)
  # Consumed once: with the cookie from before, the next check is not connected.
  again = await env.get('/dialpad/ext-connection',
                        headers=bearer(panel.token) | {'Cookie': old_cookie})
  assert json_of(again)['connected'] is False


async def test_the_connection_lives_in_the_cookie_so_it_survives_a_server_restart(env: Env) -> None:
  panel = await env.open_panel()
  await connect(env, panel)

  restarted = env.restarted()
  response = await restarted.get('/dialpad/ext-connection', headers=panel.headers)
  page = await restarted.open_panel(cookie=panel.cookie)

  assert response.status_code == 200
  assert json_of(response)['connected'] is True
  assert 'set-cookie' not in response.headers
  assert page.token == panel.token
  assert page.data['external_connection']['connected'] is True
  assert page.data['external_connection']['scopes'] == CONNECTED_SCOPES


def _rotate_the_app_secret(env: Env) -> Env:
  return env.restarted(replace(env.settings, app_secret='a-different-app-secret'))


def _age_past_thirty_days(env: Env) -> Env:
  env.clock.advance(fake_storage.COOKIE_MAX_AGE_SECONDS + 1)
  return env


@pytest.mark.parametrize(
    'invalidate',
    [_rotate_the_app_secret, _age_past_thirty_days],
    ids=['rotated app secret', 'older than thirty days'],
)
async def test_a_cookie_that_no_longer_verifies_signs_the_iframe_panel_out(
    env: Env, invalidate: Callable[[Env], Env]) -> None:
  panel = await env.open_panel()
  await connect(env, panel)
  later = invalidate(env)

  response = await later.get('/dialpad/ext-connection', headers=panel.headers)
  page = await later.open_panel(cookie=panel.cookie)

  assert response.status_code == 401
  assert page.token != panel.token
  assert page.data['external_connection']['connected'] is False


async def test_a_result_recorded_for_another_user_is_not_consumed(env: Env) -> None:
  jane = await env.open_panel(idtoken_for(**JANE))
  pat = await env.open_panel(idtoken_for(**PAT))
  await finish_oauth(env, authorize_url_of(jane.data))

  pat_check = await env.get('/dialpad/ext-connection', headers=pat.headers)
  jane_check = await env.get('/dialpad/ext-connection', headers=jane.headers)

  assert json_of(pat_check)['connected'] is False
  assert 'set-cookie' not in pat_check.headers
  assert json_of(jane_check)['connected'] is True


# --- the fake OAuth round trip -----------------------------------------------------------------


async def test_the_authorize_page_is_labelled_fake_locked_down_and_connects_nothing_by_itself(
    env: Env,) -> None:
  panel = await env.open_panel()
  authorize_url = authorize_url_of(panel.data)

  response = await env.get(authorize_url)
  check = await env.get('/dialpad/ext-connection', headers=panel.headers)

  assert response.status_code == 200
  assert response.headers['content-type'].startswith('text/html')
  assert 'fake OAuth page' in response.text
  assert '<button type="submit">Authorize</button>' in response.text
  # The button sends the same state, and the fixed code, to the callback.
  action = re.search(r'<form method="get" action="([^"]*)">', response.text)
  assert action
  assert action[1] == f'{env.settings.base_url}/oauth/callback'
  assert f'name="state" value="{state_from(authorize_url)}"' in response.text
  assert f'name="code" value="{FAKE_CODE}"' in response.text
  assert 'set-cookie' not in response.headers
  csp = response.headers['content-security-policy']
  nonce = csp.split("style-src 'nonce-")[1].split("'")[0]
  assert "default-src 'none'" in csp
  assert "form-action 'self'" in csp
  assert "frame-ancestors 'none'" in csp
  assert f'<style nonce="{nonce}">' in response.text
  assert response.headers['cache-control'] == 'no-store'
  assert json_of(check)['connected'] is False


async def test_the_authorize_page_needs_a_state_and_escapes_the_one_it_echoes(env: Env) -> None:
  hostile = '"><script>alert(1)</script>'

  response = await env.get('/oauth/fake-authorize', params={'state': hostile})
  no_state = await env.get('/oauth/fake-authorize')

  assert response.status_code == 200
  assert '<script>alert(1)</script>' not in response.text
  assert '&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;' in response.text
  assert no_state.status_code == 400


async def test_the_callback_returns_the_close_popup_page_for_the_dialpad_origin(env: Env) -> None:
  data = await env.page_data()
  authorize = await env.get(authorize_url_of(data))

  response = await press_authorize(env, authorize)

  assert response.status_code == 200
  assert env.settings.dialpad_origin in response.text
  assert 'close_popup' in response.text
  assert 'set-cookie' not in response.headers


@pytest.mark.parametrize(
    ('state_secret', 'code', 'wait_seconds'),
    [
        (APP_SECRET, FAKE_CODE, signing.STATE_TTL_SECONDS + 1),
        ('not-the-app-secret', FAKE_CODE, 0),
        (APP_SECRET, 'other', 0),
    ],
    ids=['expired state', 'forged state', 'wrong code'],
)
async def test_a_callback_with_a_bad_state_or_code_records_nothing(env: Env, state_secret: str,
                                                                   code: str,
                                                                   wait_seconds: int) -> None:
  panel = await env.open_panel()
  state = signing.issue_state(5432, 12345, state_secret, env.clock())
  env.clock.advance(wait_seconds)

  callback = await env.get('/oauth/callback', params={'state': state, 'code': code})
  check = await env.get('/dialpad/ext-connection', headers=panel.headers)

  assert callback.status_code == 400
  assert json_of(check)['connected'] is False


# --- disconnect --------------------------------------------------------------------------------


async def test_disconnect_turns_the_connection_off_but_the_same_token_still_works(env: Env) -> None:
  panel = await env.open_panel()
  await connect(env, panel)

  response = await env.post('/dialpad/ext-disconnect', headers=panel.headers)

  assert response.status_code == 204
  assert response.text == ''
  assert 'Max-Age=0' not in response.headers['set-cookie']
  claims = fake_storage.read_cookie(
      cookie_header(response).split('=', 1)[1],
      APP_SECRET,
      env.clock(),
  )
  assert claims is not None
  assert (claims.token, claims.connected) == (panel.token, False)
  # The SDK's follow-up check carries the same token and the cookie the disconnect set.
  panel.cookie = cookie_header(response)
  check = await env.get('/dialpad/ext-connection', headers=panel.headers)
  page = await env.open_panel(cookie=panel.cookie)
  assert check.status_code == 200
  body = json_of(check)
  assert body['connected'] is False
  assert body['scopes'] == []
  assert body['authorization_urls'][CLIENT_NAME] != authorize_url_of(panel.data)
  assert page.token == panel.token
  assert page.data['external_connection']['connected'] is False


# --- secrets and logs --------------------------------------------------------------------------


async def test_neither_the_idtoken_nor_the_access_token_is_logged(
    env: Env,
    caplog: pytest.LogCaptureFixture,
) -> None:
  caplog.set_level(logging.DEBUG)
  idtoken = encode_mock_idtoken(TEST_CLIENT_SECRET)

  panel = await env.open_panel(idtoken)
  token = panel.token
  await connect(env, panel)
  await env.post('/dialpad/ext-disconnect', headers=panel.headers)
  await env.get('/', params={'idtoken': 'bad' + idtoken})
  await env.get('/dialpad/ext-connection',
                headers=bearer('wrong-' + token) | {'Cookie': panel.cookie})

  logged = '\n'.join(
      record.getMessage() for record in caplog.records if record.name not in HTTP_CLIENT_LOGGERS)
  assert idtoken not in logged
  assert token not in logged
  assert panel.cookie not in logged
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
