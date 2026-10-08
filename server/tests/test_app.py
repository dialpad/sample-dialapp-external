"""The Sanic app (acme_crm/app.py): page, tokens, connection, fake OAuth, disconnect, logs."""

import logging
import re
from dataclasses import replace
from html import unescape
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import parse_qs
from urllib.parse import urlsplit

import pytest

from acme_crm import signing
from acme_crm.app import CLIENT_NAME
from acme_crm.app import CONNECTED_SCOPES
from acme_crm.app import FAKE_CODE
from acme_crm.idtoken import TEST_CLIENT_SECRET
from acme_crm.idtoken import encode_mock_idtoken
from tests.conftest import APP_SECRET
from tests.conftest import Env
from tests.conftest import Panel
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


def authorize_url_of(page_data: dict[str, Any]) -> str:
  """Return the ``acme-crm`` authorize URL from page data, as the Connect button would use it."""
  return str(page_data['external_connection']['authorization_urls'][CLIENT_NAME])


def state_from(authorize_url: str) -> str:
  """Return the signed ``state`` query parameter of an authorize URL."""
  return parse_qs(urlsplit(authorize_url).query)['state'][0]


async def press_authorize(env: Env, authorize_page: Response) -> Response:
  """Click the Authorize button on the fake authorize page and return the callback's response.

  A browser submits the page's GET form: the callback URL from ``action`` with the hidden ``state``
  and ``code`` as query parameters. This reads them from the HTML the same way.
  """
  form = re.search(r'<form method="get" action="([^"]*)">', authorize_page.text)
  assert form
  action = unescape(form[1])
  fields = {
      name: unescape(value) for name, value in re.findall(
          r'<input type="hidden" name="(\w+)" value="([^"]*)">', authorize_page.text)
  }
  return await env.get(action, params=fields)


async def finish_oauth(env: Env, authorize_url: str) -> None:
  """Play the OAuth popup: open the authorize URL, click Authorize, land on the callback.

  Afterwards the callback has recorded "this user connected" in the app's memory, but nothing is
  connected yet: the next ``ext-connection`` call has to collect it.
  """
  authorize = await env.get(authorize_url)
  assert authorize.status_code == 200
  callback = await press_authorize(env, authorize)
  assert callback.status_code == 200


async def connect(env: Env, panel: Panel) -> Response:
  """Connect an iframe panel's user end to end and return the confirming ``ext-connection`` reply.

  Runs the OAuth popup (``finish_oauth``), then makes the SDK's follow-up connection check with the
  iframe panel's access token and cookie. That response is "connected" and rewrites the session
  cookie; like a browser, this stores the new cookie in ``panel``.
  """
  await finish_oauth(env, authorize_url_of(panel.data))
  response = await env.get('/dialpad/ext-connection', headers=panel.headers)
  if 'set-cookie' in response.headers:
    panel.cookie = cookie_header(response)
  return response


# --- token decoding with mock tokens ---------------------------------------------------------


async def test_a_valid_idtoken_renders_the_page_but_the_page_carries_no_user(env: Env) -> None:
  token = encode_mock_idtoken(TEST_CLIENT_SECRET, user_id=42, company_id=7, name='Ada Lovelace')

  response = await env.load_page(token)
  data = page_data_of(response)

  assert response.status_code == 200
  assert data['access_token']
  # The SDK asks Dialpad for the user (get/user); nothing from the idtoken's profile is rendered.
  assert 'user' not in data
  assert 'Ada Lovelace' not in response.text


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
  assert data['dialpad_origin'] == env.settings.dialpad_origin
  assert data['api_prefix'] == '/dialpad'
  connection = data['external_connection']
  assert connection['connected'] is False
  assert connection['name'] == CLIENT_NAME
  assert connection['scopes'] == []
  assert list(connection['authorization_urls']) == [CLIENT_NAME]
  assert authorize_url_of(data).startswith(f'{env.settings.base_url}/oauth/')
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


async def test_the_page_carries_the_security_headers_and_a_matching_nonce(env: Env) -> None:
  response = await env.load_page()

  csp = response.headers['content-security-policy']
  nonce = csp.split("'nonce-")[1].split("'")[0]
  assert f'frame-ancestors {env.settings.dialpad_origin}' in csp
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


# --- the session cookie and the access token ------------------------------------------------------


async def test_the_page_sets_the_session_cookie_that_holds_the_access_token(env: Env) -> None:
  response = await env.load_page()

  cookie = response.headers['set-cookie']
  assert cookie.startswith('__Host-acme_session=')
  for attribute in ('Path=/', 'Secure', 'HttpOnly', 'SameSite=None', 'Partitioned',
                    'Max-Age=2592000'):
    assert attribute in cookie
  session = signing.read_session(
      cookie_header(response).split('=', 1)[1],
      APP_SECRET,
      env.clock(),
  )
  assert session is not None
  assert session.token == page_data_of(response)['access_token']
  assert (session.user_id, session.company_id, session.connected) == (5432, 12345, False)


async def test_a_browser_keeps_its_access_token_on_every_page_load(env: Env) -> None:
  first = await env.open_panel()

  second = await env.open_panel(cookie=first.cookie)

  assert second.token == first.token


async def test_a_browser_without_a_valid_cookie_gets_a_new_access_token(env: Env) -> None:
  first = await env.open_panel()
  forged = signing.issue_session(
      signing.SessionClaims(user_id=5432, company_id=12345, token=first.token, connected=True),
      'not-the-app-secret',
      env.clock(),
  )

  fresh = await env.open_panel()
  after_forged = await env.open_panel(cookie=f'__Host-acme_session={forged}')

  assert fresh.token != first.token
  assert after_forged.token not in {first.token, fresh.token}
  assert after_forged.data['external_connection']['connected'] is False


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


async def test_a_new_session_is_not_connected_and_gets_a_fresh_authorize_url(env: Env) -> None:
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


async def test_a_call_needs_the_bearer_token_and_the_cookie_to_match(env: Env) -> None:
  panel = await env.open_panel()
  other = await env.open_panel()
  ext = '/dialpad/ext-connection'
  cookie = {'Cookie': panel.cookie}

  no_header = await env.get(ext, headers=cookie)
  no_cookie = await env.get(ext, headers=bearer(panel.token))
  wrong_token = await env.get(ext, headers=bearer('never-issued') | cookie)
  another_browsers_token = await env.get(ext, headers=bearer(other.token) | cookie)
  not_bearer = await env.get(ext, headers={'Authorization': f'Basic {panel.token}'} | cookie)
  forged_cookie = await env.get(ext, headers=bearer(panel.token) | {'Cookie': 'x=y'})
  disconnect = await env.post('/dialpad/ext-disconnect', headers=bearer(panel.token))

  for response in (no_header, no_cookie, wrong_token, another_browsers_token, not_bearer,
                   forged_cookie, disconnect):
    assert response.status_code == 401
    assert json_of(response)['code'] == 'invalid_access_token'
  assert (await env.get(ext, headers=panel.headers)).status_code == 200


async def test_a_stored_result_is_consumed_and_rewrites_the_session_cookie(env: Env) -> None:
  panel = await env.open_panel()
  old_cookie = panel.cookie

  response = await connect(env, panel)

  body = json_of(response)
  assert body['connected'] is True
  assert body['name'] == CLIENT_NAME
  assert body['scopes'] == CONNECTED_SCOPES
  # Even when connected there is a fresh authorize URL, which the contract's shape allows.
  assert list(body['authorization_urls']) == [CLIENT_NAME]
  cookie = response.headers['set-cookie']
  assert cookie.startswith('__Host-acme_session=')
  for attribute in ('Path=/', 'Secure', 'HttpOnly', 'SameSite=None', 'Partitioned',
                    'Max-Age=2592000'):
    assert attribute in cookie
  # The same access token, now with the connection on; the old cookie still says not connected.
  session = signing.read_session(panel.cookie.split('=', 1)[1], APP_SECRET, env.clock())
  assert session is not None
  assert (session.token, session.connected) == (panel.token, True)
  # Consumed once: with the cookie from before, the next check is not connected.
  again = await env.get('/dialpad/ext-connection',
                        headers=bearer(panel.token) | {'Cookie': old_cookie})
  assert json_of(again)['connected'] is False


async def test_a_connected_cookie_means_connected_on_the_connection_endpoint_and_the_page(
    env: Env,) -> None:
  panel = await env.open_panel()
  await connect(env, panel)

  response = await env.get('/dialpad/ext-connection', headers=panel.headers)
  page = await env.open_panel(cookie=panel.cookie)

  assert json_of(response)['connected'] is True
  assert 'set-cookie' not in response.headers
  assert page.token == panel.token
  assert page.data['external_connection']['connected'] is True
  assert page.data['external_connection']['scopes'] == CONNECTED_SCOPES


async def test_the_connection_survives_a_server_restart(env: Env) -> None:
  panel = await env.open_panel()
  await connect(env, panel)

  restarted = env.restarted()
  response = await restarted.get('/dialpad/ext-connection', headers=panel.headers)
  page = await restarted.open_panel(cookie=panel.cookie)

  assert response.status_code == 200
  assert json_of(response)['connected'] is True
  assert page.token == panel.token
  assert page.data['external_connection']['connected'] is True


async def test_changing_the_app_secret_signs_every_iframe_panel_out(env: Env) -> None:
  panel = await env.open_panel()
  await connect(env, panel)
  rotated = env.restarted(replace(env.settings, app_secret='a-different-app-secret'))

  response = await rotated.get('/dialpad/ext-connection', headers=panel.headers)
  page = await rotated.open_panel(cookie=panel.cookie)

  assert response.status_code == 401
  assert page.token != panel.token
  assert page.data['external_connection']['connected'] is False


async def test_a_session_older_than_thirty_days_is_signed_out(env: Env) -> None:
  panel = await env.open_panel()
  await connect(env, panel)
  env.clock.advance(signing.COOKIE_MAX_AGE_SECONDS + 1)

  response = await env.get('/dialpad/ext-connection', headers=panel.headers)
  page = await env.open_panel(cookie=panel.cookie)

  assert response.status_code == 401
  assert page.token != panel.token


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


async def test_fake_authorize_shows_a_page_labelled_fake_with_an_authorize_button(
    env: Env,) -> None:
  data = await env.page_data()
  authorize_url = authorize_url_of(data)

  response = await env.get(authorize_url)

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


async def test_the_authorize_page_is_locked_down_and_connects_nothing_until_authorized(
    env: Env,) -> None:
  panel = await env.open_panel()

  response = await env.get(authorize_url_of(panel.data))
  check = await env.get('/dialpad/ext-connection', headers=panel.headers)

  csp = response.headers['content-security-policy']
  nonce = csp.split("style-src 'nonce-")[1].split("'")[0]
  assert "default-src 'none'" in csp
  assert "form-action 'self'" in csp
  assert "frame-ancestors 'none'" in csp
  assert f'<style nonce="{nonce}">' in response.text
  assert response.headers['cache-control'] == 'no-store'
  assert json_of(check)['connected'] is False


async def test_the_authorize_page_escapes_the_state_it_echoes(env: Env) -> None:
  hostile = '"><script>alert(1)</script>'

  response = await env.get('/oauth/fake-authorize', params={'state': hostile})

  assert response.status_code == 200
  assert '<script>alert(1)</script>' not in response.text
  assert '&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;' in response.text


async def test_the_callback_returns_the_close_popup_page_for_the_dialpad_origin(env: Env) -> None:
  data = await env.page_data()
  authorize = await env.get(authorize_url_of(data))

  response = await press_authorize(env, authorize)

  assert response.status_code == 200
  assert env.settings.dialpad_origin in response.text
  assert 'close_popup' in response.text
  assert 'set-cookie' not in response.headers


async def test_an_expired_state_at_the_callback_records_nothing(env: Env) -> None:
  panel = await env.open_panel()
  authorize = await env.get(authorize_url_of(panel.data))
  env.clock.advance(signing.STATE_TTL_SECONDS + 1)

  callback = await press_authorize(env, authorize)
  check = await env.get('/dialpad/ext-connection', headers=panel.headers)

  assert callback.status_code == 400
  assert json_of(check)['connected'] is False


async def test_a_forged_state_at_the_callback_records_nothing(env: Env) -> None:
  panel = await env.open_panel()
  forged = signing.issue_state(5432, 12345, 'not-the-app-secret', env.clock())

  callback = await env.get('/oauth/callback', params={'state': forged, 'code': FAKE_CODE})
  check = await env.get('/dialpad/ext-connection', headers=panel.headers)

  assert callback.status_code == 400
  assert json_of(check)['connected'] is False


async def test_the_callback_rejects_a_wrong_code_and_authorize_requires_a_state(env: Env) -> None:
  state = signing.issue_state(5432, 12345, APP_SECRET, env.clock())

  wrong_code = await env.get('/oauth/callback', params={'state': state, 'code': 'other'})
  no_state = await env.get('/oauth/fake-authorize')

  assert wrong_code.status_code == 400
  assert no_state.status_code == 400


async def test_a_result_expires_after_five_minutes(env: Env) -> None:
  panel = await env.open_panel()
  await finish_oauth(env, authorize_url_of(panel.data))
  env.clock.advance(5 * 60)

  check = await env.get('/dialpad/ext-connection', headers=panel.headers)

  assert json_of(check)['connected'] is False


# --- disconnect --------------------------------------------------------------------------------


async def test_disconnect_answers_204_and_turns_the_connection_off_in_the_cookie(env: Env) -> None:
  panel = await env.open_panel()
  await connect(env, panel)

  response = await env.post('/dialpad/ext-disconnect', headers=panel.headers)

  assert response.status_code == 204
  assert response.text == ''
  cookie = response.headers['set-cookie']
  assert cookie.startswith('__Host-acme_session=')
  for attribute in ('Secure', 'HttpOnly', 'SameSite=None', 'Partitioned', 'Path=/'):
    assert attribute in cookie
  assert 'Max-Age=0' not in cookie
  session = signing.read_session(
      cookie_header(response).split('=', 1)[1],
      APP_SECRET,
      env.clock(),
  )
  assert session is not None
  assert (session.token, session.connected) == (panel.token, False)


async def test_after_disconnect_the_same_token_still_works_and_is_not_connected(env: Env) -> None:
  panel = await env.open_panel()
  await connect(env, panel)
  panel.cookie = cookie_header(await env.post('/dialpad/ext-disconnect', headers=panel.headers))

  # The SDK's follow-up check carries the same token and the cookie the disconnect set.
  response = await env.get('/dialpad/ext-connection', headers=panel.headers)
  page = await env.open_panel(cookie=panel.cookie)

  assert response.status_code == 200
  body = json_of(response)
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
