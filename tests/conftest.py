"""Shared test support: an app wired to a movable clock, and helpers to drive it like Dialpad does.

``env`` builds the real Sanic app (``backend.app.create_app``) in production mode, ``local_env`` in
local mode, each with the built frontend faked by a tiny Vite manifest in a temp folder. Requests
go through Sanic's in-process ASGI client, so no server or port is involved.
"""

import json
import re
from dataclasses import dataclass
from http.cookies import SimpleCookie
from itertools import count
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import pytest
from dialpad_dialapp_toolkit.testing import TEST_CLIENT_SECRET
from dialpad_dialapp_toolkit.testing import encode_mock_idtoken
from sanic import Sanic

from backend.app import COOKIE_HEADER_NAME
from backend.app import App
from backend.app import create_app
from backend.settings import Settings

if TYPE_CHECKING:
  from pathlib import Path

  from httpx import Response

# Fixed values the apps under test are configured with; tests compare against them.
APP_SECRET = 'test-app-secret'
DIALPAD_ORIGIN = 'https://dialpadbeta.com'
BASE_URL = 'https://acme.example.com'
# Finds the JSON the toolkit embeds in the page: the SDK reads the same element by its id.
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


@dataclass
class Env:
  """An app under test, its clock and its settings, with request helpers that return responses.

  Tests use it as ``env.get(...)``, ``env.post(...)`` and ``env.page_data(...)`` instead of
  touching Sanic's client, whose calls return a ``(request, response)`` pair.
  """

  app: App
  clock: Clock
  settings: Settings

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
    headers = {'Cookie': cookie} if cookie else {}
    return await self.get('/', params={'idtoken': token}, headers=headers)

  async def page_data(self,
                      idtoken: str | None = None,
                      cookie: str | None = None) -> dict[str, Any]:
    """Load the page and return the page data the toolkit embedded in it, as a dict."""
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


def make_env(tmp_path: Path, *, local_mode: bool) -> Env:
  """Build an app for a test, in local mode or production mode, with its own clock.

  Production mode needs a built frontend, so a minimal Vite manifest and an empty ``assets/``
  folder are written under ``tmp_path``. Each app gets a unique Sanic name.
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
      dialpad_origin='http://localhost:5173' if local_mode else DIALPAD_ORIGIN,
      base_url='http://localhost:8000' if local_mode else BASE_URL,
      local_mode=local_mode,
      dist_dir=str(dist),
  )
  clock = Clock()
  app = create_app(settings, clock=clock, name=f'acme_test_{next(_app_names)}')
  return Env(app=app, clock=clock, settings=settings)


@pytest.fixture
def env(tmp_path: Path) -> Env:
  """Provide an app in production mode, as it runs against dialpadbeta or dialpad.com."""
  return make_env(tmp_path, local_mode=False)


@pytest.fixture
def local_env(tmp_path: Path) -> Env:
  """Provide an app in local mode, as it runs framed by the dev page on localhost."""
  return make_env(tmp_path, local_mode=True)
