"""Shared test support: an app wired to a movable clock, and helpers to drive it like Dialpad does.

``env`` builds the real Sanic app (``acme_dialpad_rightbar.app.create_app``) in production mode,
``local_env`` in local mode, each with the built frontend faked by a tiny Vite manifest in a temp
folder. Requests go through Sanic's in-process ASGI client, so no server or port is involved.
"""

import json
import re
import time
from dataclasses import dataclass
from html import unescape
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from itertools import count
from threading import Thread
from typing import TYPE_CHECKING
from typing import Any
from typing import cast
from typing import override

import pytest
from sanic import Sanic

from acme_dialpad_rightbar.app import create_app
from acme_dialpad_rightbar.demo.fake_storage import COOKIE_HEADER_NAME
from acme_dialpad_rightbar.dialpad.idtoken import TEST_CLIENT_SECRET
from acme_dialpad_rightbar.dialpad.idtoken import encode_mock_idtoken
from acme_dialpad_rightbar.settings import CLIENT_NAME
from acme_dialpad_rightbar.settings import Settings

if TYPE_CHECKING:
  from collections.abc import Iterator
  from pathlib import Path

  from httpx import Response

  from acme_dialpad_rightbar.context import App

# Fixed values the apps under test are configured with; tests compare against them.
APP_SECRET = 'test-app-secret'
DIALPAD_ORIGIN = 'https://dialpadbeta.com'
BASE_URL = 'https://acme.example.com'
# Finds the JSON the page embeds for the SDK: the SDK reads the same element by its id.
PAGE_DATA = re.compile(
    r'<script type="application/json" id="dialpad-page-data"[^>]*>(.*?)</script>',
    re.DOTALL,
)

# Lets many apps with the same Sanic name coexist in one process; each app below also gets a
# unique name of its own.
Sanic.test_mode = True
_app_names = count()


class Clock:
  """A clock tests can move: the app, its OAuth ``state`` expiry and its stores all read it.

  Calling it returns the current time in seconds, like ``time.time``. It starts at a fixed instant
  and only moves when ``advance`` is called, so expiry tests are exact and never sleep.
  """
  def __init__(self) -> None:
    """Start at a fixed instant."""
    self.now = 1_000_000.0

  def __call__(self) -> float:
    """Return the current time in seconds."""
    return self.now

  def advance(self, seconds: float) -> None:
    """Move time forward, for example past a ``state``'s 10 minutes."""
    self.now += seconds


class FakeDialpad:
  """Dialpad's public API on a local port, so the real Dialpad client makes real HTTP requests.

  Answers every ``GET`` with ``status`` and, for ``200``, the ``user`` JSON, after ``delay``
  seconds. ``requests`` records the path and ``Authorization`` header of each request received.
  ``origin`` is what to put in ``Settings.dialpad_origin``; ``close`` stops listening, after which
  connecting to ``origin`` is refused.
  """
  def __init__(self) -> None:
    """Start listening on a free local port, answering ``200`` with a default user."""
    self.status = 200
    self.delay = 0.0
    self.user: dict[str, object] = {
        'id': 5432,
        'display_name': 'Jane Agent',
        'emails': ['jane.agent@example.com', 'jane@example.org'],
        'state': 'active',
    }
    # When set, sent as the body instead of the JSON, to play an unreadable answer.
    self.raw: bytes | None = None
    self.requests: list[tuple[str, str | None]] = []
    fake = self

    class Handler(BaseHTTPRequestHandler):
      """Answers one request from the fake's current settings."""
      def do_GET(self) -> None:
        """Record the request, wait ``delay`` and answer."""
        fake.requests.append((self.path, self.headers.get('Authorization')))
        time.sleep(fake.delay)
        answer = fake.user if fake.status == HTTPStatus.OK else {'error': 'no'}
        body = json.dumps(answer).encode() if fake.raw is None else fake.raw
        self.send_response(fake.status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

      @override
      def log_message(self, format: str, *args: object) -> None:
        """Stay quiet."""

    class Server(ThreadingHTTPServer):
      """A server that doesn't print the broken pipes of clients that gave up waiting."""
      daemon_threads = True

      @override
      def handle_error(self, request: object, client_address: object) -> None:
        """Ignore the error: a slow answer's client has hung up."""

    self._server = Server(('127.0.0.1', 0), Handler)
    # A short poll interval lets `close` return at once instead of after the default half second.
    Thread(target=self._server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True).start()

  @property
  def origin(self) -> str:
    """Return the bare origin this server listens on, for example ``http://127.0.0.1:50123``."""
    host, port = self._server.server_address[:2]
    return f'http://{host!s}:{port}'

  def close(self) -> None:
    """Stop listening, so the next connection to ``origin`` is refused."""
    self._server.shutdown()
    self._server.server_close()


@dataclass
class Panel:
  """An iframe panel as its browser holds it: the page data and the storage cookie the page set.

  The test client's cookie jar won't resend a ``Secure`` cookie over plain HTTP, so tests keep the
  ``Cookie`` header value here and send it themselves. Replace ``cookie`` with a response's new one
  (``cookie_header``) whenever the response sets one, as a browser would.
  """

  data: dict[str, Any]
  cookie: str

  @property
  def token(self) -> str:
    """The access token the page embedded, which the SDK sends as ``Authorization: Bearer``."""
    return str(self.data['access_token'])

  @property
  def headers(self) -> dict[str, str]:
    """The headers of an API call from this iframe panel: the bearer token and the cookie."""
    return bearer(self.token) | {'Cookie': self.cookie}


@dataclass
class Env:
  """An app under test, its clock and its settings, with request helpers that return responses.

  Tests use it as ``env.get(...)``, ``env.post(...)`` and ``env.page_data(...)`` instead of
  touching Sanic's client, whose calls return a ``(request, response)`` pair. ``dialpad`` is the
  fake Dialpad API the production-mode app's ``dialpad_origin`` points at.
  """

  app: App
  clock: Clock
  settings: Settings
  dialpad: FakeDialpad

  async def get(self, path: str, **kwargs: object) -> Response:
    """Send a ``GET`` to the app and return the response. ``kwargs`` go to the HTTP client."""
    _request, response = await self.app.asgi_client.get(path, **kwargs)
    return cast('Response', response)

  async def post(self, path: str, **kwargs: object) -> Response:
    """Send a ``POST`` to the app and return the response. ``kwargs`` go to the HTTP client."""
    _request, response = await self.app.asgi_client.post(path, **kwargs)
    return cast('Response', response)

  async def load_page(self, idtoken: str | None = None, cookie: str | None = None) -> Response:
    """Load the page as Dialpad does: ``GET /?idtoken=...``, optionally with a browser cookie.

    Without ``idtoken`` it uses a mock one for the default user. ``cookie`` is the ``Cookie``
    header value a browser would send, from ``cookie_header``.
    """
    token = idtoken if idtoken is not None else encode_mock_idtoken(TEST_CLIENT_SECRET)
    headers = {'Cookie': cookie} if cookie is not None else {}
    return await self.get('/', params={'idtoken': token}, headers=headers)

  async def open_panel(self, idtoken: str | None = None, cookie: str | None = None) -> Panel:
    """Open the iframe panel as a browser does: load the page and keep the storage cookie it sets.

    ``cookie`` is what the browser already held (for example from an earlier visit); the page may
    keep its access token or replace it.
    """
    response = await self.load_page(idtoken, cookie)
    assert response.status_code == HTTPStatus.OK
    return Panel(data=page_data_of(response), cookie=cookie_header(response))

  def restarted(self, settings: Settings | None = None) -> Env:
    """Return the same app after a server restart: a new app with empty memory.

    It has the same settings unless ``settings`` is given (for example a rotated ``APP_SECRET``).
    The clock and the fake Dialpad API stay, since they are outside the server. Browsers keep
    their cookies, so a ``Panel`` from before the restart is still usable.
    """
    settings = settings or self.settings
    app = create_app(
        settings,
        clock=self.clock,
        name=f'acme_test_{next(_app_names)}',
        api_timeout=0.5,
    )
    return Env(app=app, clock=self.clock, settings=settings, dialpad=self.dialpad)

  async def page_data(self,
                      idtoken: str | None = None,
                      cookie: str | None = None) -> dict[str, Any]:
    """Load the page and return the page data embedded in it, as a dict."""
    return page_data_of(await self.load_page(idtoken, cookie))


def page_data_of(response: Response) -> dict[str, Any]:
  """Return the JSON in the page's ``dialpad-page-data`` element."""
  match = PAGE_DATA.search(response.text)
  assert match, response.text
  return json.loads(match.group(1))


def json_of(response: Response) -> dict[str, Any]:
  """Parse a JSON response body."""
  return json.loads(response.text)


def idtoken_for(user_id: int, company_id: int) -> str:
  """Return a mock idtoken for this user, signed with the test client secret."""
  return encode_mock_idtoken(TEST_CLIENT_SECRET, user_id=user_id, company_id=company_id)


def bearer(token: str) -> dict[str, str]:
  """Return the headers an API call carries: the access token as ``Authorization: Bearer``."""
  return {'Authorization': f'Bearer {token}'}


def cookie_header(response: Response) -> str:
  """Return the ``Cookie`` header a browser would send back after this response's ``Set-Cookie``.

  The test client's cookie jar won't resend a ``Secure`` cookie over plain HTTP, so tests pass
  this value explicitly instead.
  """
  jar = SimpleCookie()
  jar.load(response.headers['set-cookie'])
  morsel = jar[COOKIE_HEADER_NAME]
  return f'{COOKIE_HEADER_NAME}={morsel.value}'


def authorize_url_of(page_data: dict[str, Any]) -> str:
  """Return the authorize URL from page data, as the Connect button would use it."""
  return str(page_data['external_connection']['authorization_urls'][CLIENT_NAME])


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
  iframe panel's access token and cookie. That response is "connected" and rewrites the storage
  cookie; like a browser, this stores the new cookie in ``panel``.
  """
  await finish_oauth(env, authorize_url_of(panel.data))
  response = await env.get('/dialpad/ext-connection', headers=panel.headers)
  if 'set-cookie' in response.headers:
    panel.cookie = cookie_header(response)
  return response


def make_env(tmp_path: Path, dialpad: FakeDialpad, *, local_mode: bool) -> Env:
  """Build an app for a test, in local mode or production mode, with its own clock.

  Production mode needs a built frontend, so a minimal Vite manifest and an empty ``assets/``
  folder are written under ``tmp_path``, and its Dialpad origin is the fake Dialpad API's, so the
  page's demo call never reaches the real Dialpad. The page waits at most half a second for it.
  Each app gets a unique Sanic name.
  """
  dist = tmp_path / ('local' if local_mode else 'prod') / 'dist'
  (dist / '.vite').mkdir(parents=True)
  (dist / 'assets').mkdir()
  manifest = {
      'src/main.ts': {
          'file': 'assets/main-abc.js',
          'css': ['assets/main-abc.css'],
          'isEntry': True
      },
  }
  (dist / '.vite' / 'manifest.json').write_text(json.dumps(manifest))
  settings = Settings(
      client_secret=TEST_CLIENT_SECRET,
      app_secret=APP_SECRET,
      dialpad_origin='http://localhost:5173' if local_mode else dialpad.origin,
      base_url='http://localhost:8000' if local_mode else BASE_URL,
      local_mode=local_mode,
      dist_dir=str(dist),
  )
  clock = Clock()
  app = create_app(
      settings,
      clock=clock,
      name=f'acme_test_{next(_app_names)}',
      api_timeout=0.5,
  )
  return Env(app=app, clock=clock, settings=settings, dialpad=dialpad)


@pytest.fixture
def fake_dialpad() -> Iterator[FakeDialpad]:
  """Provide a fake Dialpad API for one test, and stop it afterwards."""
  dialpad = FakeDialpad()
  yield dialpad
  dialpad.close()


@pytest.fixture
def env(tmp_path: Path, fake_dialpad: FakeDialpad) -> Env:
  """Provide an app in production mode, as it runs against dialpadbeta or dialpad.com."""
  return make_env(tmp_path, fake_dialpad, local_mode=False)


@pytest.fixture
def local_env(tmp_path: Path, fake_dialpad: FakeDialpad) -> Env:
  """Provide an app in local mode, as it runs framed by the dev host on localhost."""
  return make_env(tmp_path, fake_dialpad, local_mode=True)
