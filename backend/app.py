"""The Acme CRM backend: bare Sanic, built on the toolkit's contract.

Endpoints: the page, ``/dialpad/connection``, ``/dialpad/disconnect``, and the demo-only fake OAuth
pair. Identity comes from the idtoken on the page request only; every API call carries the app's own
per-user access token as a bearer token.
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from typing import override
from urllib.parse import urlencode

from dialpad_dialapp_toolkit import DEFAULT_API_PREFIX
from dialpad_dialapp_toolkit import ConnectionStatus
from dialpad_dialapp_toolkit import ErrorResponse
from dialpad_dialapp_toolkit import IdTokenError
from dialpad_dialapp_toolkit import PageData
from dialpad_dialapp_toolkit import PageOptions
from dialpad_dialapp_toolkit import PageUser
from dialpad_dialapp_toolkit import RenderedPage
from dialpad_dialapp_toolkit import decode_idtoken
from dialpad_dialapp_toolkit import generate_nonce
from dialpad_dialapp_toolkit import render_close_popup
from dialpad_dialapp_toolkit import render_error_page
from dialpad_dialapp_toolkit import render_page
from dialpad_dialapp_toolkit.testing import encode_mock_idtoken
from sanic import HTTPResponse
from sanic import Request
from sanic import Sanic
from sanic.config import Config
from sanic.handlers import ErrorHandler
from sanic.response import html
from sanic.response import json
from sanic.response import redirect
from sanic.response import text

from backend import signing
from backend.assets import build_assets
from backend.stores import AccessTokens
from backend.stores import OAuthResults
from backend.stores import UserKey

if TYPE_CHECKING:
  from collections.abc import Callable

  from dialpad_dialapp_toolkit import PageAssets

  from backend.settings import Settings

logger = logging.getLogger('acme_crm')

App = Sanic[Config, SimpleNamespace]

ACCOUNT_NAME = 'Acme CRM (demo)'
FAKE_CODE = 'fake-code'
COOKIE_NAME = 'acme_session'
# Sanic prefixes the name with `__Host-` when host_prefix is set, and reports it that way back.
COOKIE_HEADER_NAME = f'__Host-{COOKIE_NAME}'
BEARER = 'Bearer '


class QuietErrorHandler(ErrorHandler):
  """Sanic's default handler logs the full URL, which would put the idtoken in the logs."""
  @staticmethod
  @override
  def log(request: Request, exception: Exception) -> None:
    """Log the method, path (never the query string) and exception type."""
    logger.error('%s %s failed: %s', request.method, request.path, type(exception).__name__)


@dataclass
class Backend:
  """The settings, stores and clock the handlers share."""

  settings: Settings
  assets: PageAssets
  tokens: AccessTokens
  results: OAuthResults
  clock: Callable[[], float]

  def authorize_url(self, key: UserKey) -> str:
    """Build the fake authorize URL with a fresh ``state`` for this user."""
    state = signing.issue_state(key.user_id, key.company_id, self.settings.app_secret, self.clock())
    return f'{self.settings.authorize_url}?{urlencode({"state": state})}'

  def cookie_is_valid(self, request: Request, key: UserKey) -> bool:
    """Whether the request carries a connection cookie for exactly this user."""
    return signing.cookie_is_valid(
        request.cookies.get(COOKIE_HEADER_NAME),
        key.user_id,
        key.company_id,
        self.settings.app_secret,
        self.clock(),
    )

  def status(self, key: UserKey, *, connected: bool) -> ConnectionStatus:
    """Build the status: connected, or not connected with a fresh authorize URL."""
    if connected:
      return ConnectionStatus(connected=True, account_name=ACCOUNT_NAME)
    return ConnectionStatus(
        connected=False,
        account_name=ACCOUNT_NAME,
        authorize_url=self.authorize_url(key),
    )

  def user_for(self, request: Request) -> UserKey | None:
    """Look up the user a bearer access token was issued to; ``None`` if missing or unknown."""
    header = request.headers.get('Authorization', '')
    if not header.startswith(BEARER):
      return None
    return self.tokens.lookup(header.removeprefix(BEARER))


def _rendered(page: RenderedPage) -> HTTPResponse:
  return html(page.html, status=page.status, headers=page.headers)


def _status_response(status: ConnectionStatus) -> HTTPResponse:
  return json(status.model_dump(mode='json', exclude_none=True))


def _unauthorized() -> HTTPResponse:
  error = ErrorResponse(code='invalid_access_token', message='Reload the panel.')
  return json(error.model_dump(mode='json'), status=401)


def _set_cookie(reply: HTTPResponse, value: str, max_age: int) -> None:
  """Set (or, with ``max_age=0``, clear) the connection cookie, always with the same attributes."""
  reply.add_cookie(
      COOKIE_NAME,
      value,
      path='/',
      secure=True,
      httponly=True,
      samesite='None',
      partitioned=True,
      host_prefix=True,
      max_age=max_age,
  )


def _register_page(app: App, backend: Backend) -> None:
  settings = backend.settings

  @app.get('/')
  async def page(request: Request) -> HTTPResponse:
    try:
      claims = decode_idtoken(request.args.get('idtoken'), settings.client_secret)
    except IdTokenError:
      error = ErrorResponse(code='invalid_idtoken', message='Open this panel from Dialpad.')
      return _rendered(render_error_page(error, status=401,
                                         dialpad_origin=settings.dialpad_origin),)
    key = UserKey(company_id=claims.company_id, user_id=claims.user_id)
    page_data = PageData(
        dialpad_origin=settings.dialpad_origin,
        api_prefix=DEFAULT_API_PREFIX,
        access_token=backend.tokens.issue(key),
        user=PageUser.from_claims(claims),
        connection=backend.status(key, connected=backend.cookie_is_valid(request, key)),
    )
    options = PageOptions(
        title=ACCOUNT_NAME,
        extra_connect_src=(settings.vite_websocket_origin,) if settings.local_mode else (),
    )
    return _rendered(
        render_page(page_data, nonce=generate_nonce(), assets=backend.assets, options=options),)


def _register_contract(app: App, backend: Backend) -> None:
  settings = backend.settings

  @app.get(f'{DEFAULT_API_PREFIX}/connection')
  async def connection(request: Request) -> HTTPResponse:
    key = backend.user_for(request)
    if key is None:
      return _unauthorized()
    if backend.results.consume(key):
      reply = _status_response(backend.status(key, connected=True))
      cookie = signing.issue_cookie(
          key.user_id,
          key.company_id,
          settings.app_secret,
          backend.clock(),
      )
      _set_cookie(reply, cookie, signing.COOKIE_MAX_AGE_SECONDS)
      return reply
    return _status_response(backend.status(key, connected=backend.cookie_is_valid(request, key)))

  @app.post(f'{DEFAULT_API_PREFIX}/disconnect')
  async def disconnect(request: Request) -> HTTPResponse:
    key = backend.user_for(request)
    if key is None:
      return _unauthorized()
    reply = _status_response(backend.status(key, connected=False))
    _set_cookie(reply, '', 0)
    return reply


def _register_fake_oauth(app: App, backend: Backend) -> None:
  settings = backend.settings

  @app.get('/oauth/fake-authorize')
  async def fake_authorize(request: Request) -> HTTPResponse:
    state = request.args.get('state')
    if not state:
      return text('state is required', status=400)
    return redirect(f'{settings.callback_url}?{urlencode({"state": state, "code": FAKE_CODE})}')

  @app.get('/oauth/callback')
  async def callback(request: Request) -> HTTPResponse:
    state = str(request.args.get('state', ''))
    claims = signing.verify_state(state, settings.app_secret, backend.clock())
    if claims is None or request.args.get('code') != FAKE_CODE:
      error = ErrorResponse(code='invalid_state', message='This connection link has expired.')
      return _rendered(render_error_page(error, status=400,
                                         dialpad_origin=settings.dialpad_origin),)
    backend.results.record(UserKey(company_id=claims.company_id, user_id=claims.user_id))
    return _rendered(render_close_popup(settings.dialpad_origin, nonce=generate_nonce()))


def _register_dev(app: App, backend: Backend) -> None:
  """Local mode only: hand the dev page a page URL carrying a mock idtoken.

  The route exists only when the settings say local mode; no request can switch it on.
  """
  settings = backend.settings

  @app.get('/dev/frame-url')
  async def frame_url(_request: Request) -> HTTPResponse:
    token = encode_mock_idtoken(settings.client_secret)
    return json(
        {'url': f'{settings.base_url}/?{urlencode({"idtoken": token})}'},
        headers={'Access-Control-Allow-Origin': settings.vite_origin},
    )


def create_app(
    settings: Settings,
    *,
    clock: Callable[[], float] = time.time,
    name: str = 'acme_crm',
) -> App:
  """Build the app. ``clock`` returns the time in seconds, so tests can move it."""
  app = Sanic(name, error_handler=QuietErrorHandler(), configure_logging=False)
  # The access log would print each page URL, idtoken included.
  app.config.ACCESS_LOG = False
  backend = Backend(
      settings=settings,
      assets=build_assets(settings),
      tokens=AccessTokens(),
      results=OAuthResults(clock),
      clock=clock,
  )

  @app.get('/healthz')
  async def healthz(_request: Request) -> HTTPResponse:
    return text('ok')

  _register_page(app, backend)
  _register_contract(app, backend)
  _register_fake_oauth(app, backend)
  if settings.local_mode:
    _register_dev(app, backend)
  else:
    app.static('/assets', Path(settings.dist_dir) / 'assets')
  return app
