"""The Acme CRM backend: bare Sanic, built on the toolkit's contract.

Routes, in the order a user meets them:

* ``GET /``: the panel page. Dialpad loads it in an iframe with the idtoken in the query string.
* ``GET /dialpad/ext-connection`` and ``POST /dialpad/ext-disconnect``: the contract endpoints the
  SDK calls with the app's own access token to check, and to end, the connection.
* ``GET /oauth/fake-authorize`` and ``GET /oauth/callback``: a stand-in for the partner CRM's OAuth
  round trip. A real partner replaces these two with their CRM's authorize URL and callback.
* ``GET /dev/frame-url`` (local mode only) and ``GET /healthz``: development helpers.

Identity comes from the idtoken on the page request only. Every later API call carries the app's own
per-user access token as a bearer token, and the connection itself is remembered in a signed cookie.
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
from dialpad_dialapp_toolkit import ErrorResponse
from dialpad_dialapp_toolkit import ExternalConnection
from dialpad_dialapp_toolkit import IdTokenError
from dialpad_dialapp_toolkit import PageData
from dialpad_dialapp_toolkit import PageOptions
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
from sanic.response import empty
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

# The name the panel shows and the page title.
ACCOUNT_NAME = 'Acme CRM (demo)'
# The OAuth client's name and scopes, in the DialApp framework's `external_connection` shape.
CLIENT_NAME = 'acme-crm'
CONNECTED_SCOPES = ['contacts.read']
# The fixed authorization code the fake OAuth round trip hands back; a real CRM issues a one-time
# code that the callback exchanges for tokens.
FAKE_CODE = 'fake-code'
# The connection cookie, sent by browsers as `__Host-acme_session`.
COOKIE_NAME = 'acme_session'
# Sanic prefixes the name with `__Host-` when host_prefix is set, and reports it that way back.
COOKIE_HEADER_NAME = f'__Host-{COOKIE_NAME}'
# The prefix of the access token in the `Authorization` header.
BEARER = 'Bearer '


class QuietErrorHandler(ErrorHandler):
  """Error handler that never logs a request's query string.

  Sanic's default handler logs the full URL of a failing request. The page URL carries the idtoken,
  which never expires, so a failure there would write a long-lived credential into the logs.
  """
  @staticmethod
  @override
  def log(request: Request, exception: Exception) -> None:
    """Log an unhandled error as ``METHOD /path failed: ExceptionType``.

    Sanic calls this for every exception a handler raises; the response (a 500 page) is built
    separately and carries no detail.
    """
    logger.error('%s %s failed: %s', request.method, request.path, type(exception).__name__)


@dataclass
class Backend:
  """Everything the route handlers share: configuration, stores, assets and the clock.

  One instance is created per app by ``create_app`` and captured by the handlers. ``clock`` is
  injectable so tests can move time (the OAuth ``state`` expires after 10 minutes, a stored OAuth
  result after 5, the cookie after 30 days).
  """

  settings: Settings
  assets: PageAssets
  tokens: AccessTokens
  results: OAuthResults
  clock: Callable[[], float]

  def authorize_url(self, key: UserKey) -> str:
    """Build the URL the Connect button sends this user to, with a fresh signed ``state``.

    Called every time a connection status is built (page render and each ``ext-connection``
    answer), so a URL is never reused. The ``state`` binds the OAuth round trip to this user for 10
    minutes: the callback records a result only for the user it names.
    """
    state = signing.issue_state(key.user_id, key.company_id, self.settings.app_secret, self.clock())
    return f'{self.settings.authorize_url}?{urlencode({"state": state})}'

  def cookie_is_valid(self, request: Request, key: UserKey) -> bool:
    """Whether the request carries a valid connection cookie for exactly this user.

    False when the cookie is missing, forged, too old, or issued to another user or company (one
    browser profile can switch Dialpad users). Reads the cookie only; never sets it.
    """
    return signing.cookie_is_valid(
        request.cookies.get(COOKIE_HEADER_NAME),
        key.user_id,
        key.company_id,
        self.settings.app_secret,
        self.clock(),
    )

  def external_connection(self, key: UserKey, *, connected: bool) -> ExternalConnection:
    """Build the connection status in the DialApp framework's ``external_connection`` shape.

    Used for the page data and every ``ext-connection`` answer. It always carries one authorize URL
    (even when connected, so the SDK has a fresh one ready after a disconnect); the scopes are the
    client's when connected and empty otherwise.
    """
    return ExternalConnection(
        connected=connected,
        authorization_urls={CLIENT_NAME: self.authorize_url(key)},
        name=CLIENT_NAME,
        scopes=CONNECTED_SCOPES if connected else [],
    )

  def user_for(self, request: Request) -> UserKey | None:
    """Authenticate an API call by its ``Authorization: Bearer`` access token.

    Returns the user the token was issued to at page load, or ``None`` when the header is missing,
    malformed or unknown (for example after a backend restart, which forgets every token).
    """
    header = request.headers.get('Authorization', '')
    if not header.startswith(BEARER):
      return None
    return self.tokens.lookup(header.removeprefix(BEARER))


def _rendered(page: RenderedPage) -> HTTPResponse:
  """Turn a page the toolkit rendered into a response, with the toolkit's status and headers."""
  return html(page.html, status=page.status, headers=page.headers)


def _connection_response(connection: ExternalConnection) -> HTTPResponse:
  """Answer ``200`` with the connection as JSON, the body ``ext-connection`` returns."""
  return json(connection.model_dump(mode='json'))


def _unauthorized() -> HTTPResponse:
  """Answer ``401`` for a missing or unknown access token.

  This is the app's own token being rejected; the panel reacts by asking the user to reload.
  """
  error = ErrorResponse(code='invalid_access_token', message='Reload the panel.')
  return json(error.model_dump(mode='json'), status=401)


def _set_cookie(reply: HTTPResponse, value: str, max_age: int) -> None:
  """Set the connection cookie on ``reply``, or clear it with ``max_age=0``.

  The attributes are the same either way (a browser only clears a cookie that matches them):
  ``Secure``, ``HttpOnly``, ``SameSite=None`` and ``Partitioned``, because the panel runs in a
  third-party iframe, and the ``__Host-`` prefix, which pins it to this host and path ``/``.
  """
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
  """Register ``GET /``, the panel page."""
  settings = backend.settings

  @app.get('/')
  async def page(request: Request) -> HTTPResponse:
    """Render the panel page for the user in the ``idtoken`` query parameter.

    Invoked when Dialpad (or the dev page) loads the iframe. A token that doesn't decode gets a
    ``401`` HTML page. Otherwise the user's access token is created on first use (and reused
    after), and the page embeds it with the connection as the cookie says it is: connected for
    a valid cookie, not connected (with an authorize URL) otherwise. Nothing is stored beyond the
    token, and no cookie is set here: only ``ext-connection`` sets it.
    """
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
        external_connection=backend.external_connection(
            key,
            connected=backend.cookie_is_valid(request, key),
        ),
    )
    options = PageOptions(
        title=ACCOUNT_NAME,
        extra_connect_src=(settings.vite_websocket_origin,) if settings.local_mode else (),
    )
    return _rendered(
        render_page(page_data, nonce=generate_nonce(), assets=backend.assets, options=options),)


def _register_contract(app: App, backend: Backend) -> None:
  """Register the two contract endpoints the SDK calls with the access token."""
  settings = backend.settings

  @app.get(f'{DEFAULT_API_PREFIX}/ext-connection')
  async def ext_connection(request: Request) -> HTTPResponse:
    """Answer whether the calling user is connected to Acme.

    The SDK calls this on start when the page said "not connected", after Dialpad replies to
    Connect, on every poll while the OAuth popup is open, and after a disconnect for a fresh
    authorize URL. If the OAuth callback has recorded a result for this user, it is consumed here:
    the answer is "connected" and the connection cookie is set (the only place it is set), so the
    next page load starts connected. Otherwise the cookie alone decides.
    """
    key = backend.user_for(request)
    if key is None:
      return _unauthorized()
    if backend.results.consume(key):
      reply = _connection_response(backend.external_connection(key, connected=True))
      cookie = signing.issue_cookie(
          key.user_id,
          key.company_id,
          settings.app_secret,
          backend.clock(),
      )
      _set_cookie(reply, cookie, signing.COOKIE_MAX_AGE_SECONDS)
      return reply
    connected = backend.cookie_is_valid(request, key)
    return _connection_response(backend.external_connection(key, connected=connected))

  @app.post(f'{DEFAULT_API_PREFIX}/ext-disconnect')
  async def ext_disconnect(request: Request) -> HTTPResponse:
    """End the connection: clear the cookie and answer ``204`` with no body.

    Invoked from the panel's Disconnect button or the host's panel menu. After it the user is not
    connected; the SDK marks the panel disconnected and calls ``ext-connection`` once more for a
    fresh authorize URL. A real partner would also delete the user's CRM tokens here.
    """
    key = backend.user_for(request)
    if key is None:
      return _unauthorized()
    reply = empty(status=204)
    _set_cookie(reply, '', 0)
    return reply


def _register_fake_oauth(app: App, backend: Backend) -> None:
  """Register the demo-only OAuth round trip that stands in for a real CRM."""
  settings = backend.settings

  @app.get('/oauth/fake-authorize')
  async def fake_authorize(request: Request) -> HTTPResponse:
    """Stand in for the CRM's authorize page by redirecting straight to the callback.

    Invoked when the user clicks Connect and Dialpad opens the authorize URL in a popup (the web)
    or its own login window (the desktop app). A real CRM would show a login and consent screen
    here; this one skips both and sends the ``state`` back with a fixed ``code``. No cookie is set.
    """
    state = request.args.get('state')
    if not state:
      return text('state is required', status=400)
    return redirect(f'{settings.callback_url}?{urlencode({"state": state, "code": FAKE_CODE})}')

  @app.get('/oauth/callback')
  async def callback(request: Request) -> HTTPResponse:
    """Finish the OAuth round trip: record that this user connected and close the popup.

    Invoked inside the popup after the (fake) authorization. A real partner would exchange the
    ``code`` for CRM tokens and store them here. This version only verifies the signed ``state``
    and remembers "connected" for that user for 5 minutes; the SDK's next ``ext-connection`` check
    consumes it. An expired, forged or mismatched ``state`` renders an error page and records
    nothing. The reply is the toolkit's close-popup page, which tells Dialpad and closes the
    window. No cookie is set: the popup is a separate window from the panel's iframe.
    """
    state = str(request.args.get('state', ''))
    claims = signing.verify_state(state, settings.app_secret, backend.clock())
    if claims is None or request.args.get('code') != FAKE_CODE:
      error = ErrorResponse(code='invalid_state', message='This connection link has expired.')
      return _rendered(render_error_page(error, status=400,
                                         dialpad_origin=settings.dialpad_origin),)
    backend.results.record(UserKey(company_id=claims.company_id, user_id=claims.user_id))
    return _rendered(render_close_popup(settings.dialpad_origin, nonce=generate_nonce()))


def _register_dev(app: App, backend: Backend) -> None:
  """Register ``GET /dev/frame-url``, which only exists in local mode.

  The route is registered only when the settings say local mode; no request can switch it on.
  """
  settings = backend.settings

  @app.get('/dev/frame-url')
  async def frame_url(_request: Request) -> HTTPResponse:
    """Hand the dev page the URL to frame: this app's page with a fresh mock idtoken.

    The dev page stands in for Dialpad, which would fetch a real idtoken and append it itself. CORS
    allows only the dev page's origin.
    """
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
  """Build the Sanic app: its stores, its routes, and the page's assets.

  Called once at startup by ``python -m backend`` and once per test. Access tokens and OAuth
  results start empty and live in this app's memory. ``clock`` returns the time in seconds, so
  tests can move time; ``name`` must be unique per app in one process. Outside local mode this
  also needs the built frontend (``pnpm build``) and serves it under ``/assets``.
  """
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
    """Answer ``ok`` once the app is up; the Playwright setup polls this before starting tests."""
    return text('ok')

  _register_page(app, backend)
  _register_contract(app, backend)
  _register_fake_oauth(app, backend)
  if settings.local_mode:
    _register_dev(app, backend)
  else:
    app.static('/assets', Path(settings.dist_dir) / 'assets')
  return app
