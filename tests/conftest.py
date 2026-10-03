"""Fixtures: an app with a movable clock, plus helpers to load the page and read its page data."""

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

APP_SECRET = 'test-app-secret'
DIALPAD_ORIGIN = 'https://dialpadbeta.com'
BASE_URL = 'https://acme.example.com'
PAGE_DATA = re.compile(
    r'<script type="application/json" id="dialpad-page-data"[^>]*>(.*?)</script>',
    re.DOTALL,
)

Sanic.test_mode = True
_app_names = count()


class Clock:
  """A settable clock; the app and its stores read the time from here."""
  def __init__(self) -> None:
    self.now = 1_000_000.0

  def __call__(self) -> float:
    return self.now

  def advance(self, seconds: float) -> None:
    self.now += seconds


@dataclass
class Env:
  """An app under test with its clock."""

  app: App
  clock: Clock
  settings: Settings

  async def get(self, path: str, **kwargs: object) -> Response:
    _request, response = await self.app.asgi_client.get(path, **kwargs)
    return cast('Response', response)

  async def post(self, path: str, **kwargs: object) -> Response:
    _request, response = await self.app.asgi_client.post(path, **kwargs)
    return cast('Response', response)

  async def load_page(self, idtoken: str | None = None, cookie: str | None = None) -> Response:
    """Load the page as Dialpad does: ``GET /?idtoken=…``."""
    token = idtoken if idtoken is not None else encode_mock_idtoken(TEST_CLIENT_SECRET)
    headers = {'Cookie': cookie} if cookie else {}
    return await self.get('/', params={'idtoken': token}, headers=headers)

  async def page_data(self,
                      idtoken: str | None = None,
                      cookie: str | None = None) -> dict[str, Any]:
    """Load the page and return the embedded page data."""
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
  return {'Authorization': f'Bearer {token}'}


def cookie_header(response: Response) -> str:
  """Return the ``Cookie`` header a browser would send back after this Set-Cookie."""
  jar = SimpleCookie()
  jar.load(response.headers['set-cookie'])
  morsel = jar[COOKIE_HEADER_NAME]
  return f'{COOKIE_HEADER_NAME}={morsel.value}'


def make_env(tmp_path: Path, *, local_mode: bool) -> Env:
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
  return make_env(tmp_path, local_mode=False)


@pytest.fixture
def local_env(tmp_path: Path) -> Env:
  return make_env(tmp_path, local_mode=True)
