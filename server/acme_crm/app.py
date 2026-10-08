"""The Acme CRM server: bare Sanic, built on its own copy of the DialApp contract.

Routes, in the order a user meets them:

* ``GET /``: the panel page. Dialpad loads it in an iframe with the idtoken in the query string.
* ``GET /dialpad/ext-connection`` and ``POST /dialpad/ext-disconnect``: the contract endpoints the
  SDK calls with the app's own access token to check, and to end, the connection.
* ``GET /oauth/fake-authorize`` and ``GET /oauth/callback``: a stand-in for the partner CRM's OAuth
  round trip, with a clearly fake Authorize page in between. A real partner replaces these two with
  their CRM's authorize URL and callback.
* ``GET /dev/frame-url`` (local mode only) and ``GET /healthz``: development helpers.

Identity comes from the idtoken on the page request only. Every later API call carries the app's own
per-user access token as a bearer token, which must match the one in the session cookie.

What this demo has to remember for good, the user's access token and whether they are connected,
it keeps in the browser: one signed session cookie (HMAC-SHA256 with ``APP_SECRET``, bound to the
Dialpad user and company, valid for 30 days) is the app's persistent storage. The server keeps no
database. The page load sets the cookie and embeds the same token in the page data; the contract
endpoints accept a call only when its ``Authorization: Bearer`` value equals the token in the
cookie. The handlers read and change that state only through ``CookieBackedDatabaseStorage``
(``acme_crm.state``), whose getters are ``get_access_token`` and ``is_external_connected``: it plays
the per-user database row a real partner would keep. A real partner stores the CRM tokens it gets
from the OAuth callback instead, and answers from those; see ``acme_crm.stores.OAuthResults`` and
``acme_crm.signing``.
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from typing import override
from urllib.parse import urlencode

from sanic import HTTPResponse
from sanic import Request
from sanic import Sanic
from sanic.config import Config
from sanic.handlers import ErrorHandler
from sanic.response import empty
from sanic.response import html
from sanic.response import json
from sanic.response import text

from acme_crm import signing
from acme_crm.assets import build_assets
from acme_crm.contract import DEFAULT_API_PREFIX
from acme_crm.contract import ErrorResponse
from acme_crm.contract import ExternalConnection
from acme_crm.contract import PageData
from acme_crm.dialpad_api import DEFAULT_TIMEOUT_SECONDS
from acme_crm.dialpad_api import fetch_dialpad_user
from acme_crm.dialpad_api import skipped
from acme_crm.fake_oauth import render_fake_authorize_page
from acme_crm.idtoken import IdTokenError
from acme_crm.idtoken import decode_idtoken
from acme_crm.idtoken import encode_mock_idtoken
from acme_crm.pages import PageOptions
from acme_crm.pages import RenderedPage
from acme_crm.pages import generate_nonce
from acme_crm.pages import render_close_popup
from acme_crm.pages import render_error_page
from acme_crm.pages import render_page
from acme_crm.state import CookieBackedDatabaseStorage
from acme_crm.stores import OAuthResults
from acme_crm.stores import UserKey

if TYPE_CHECKING:
  from collections.abc import Callable

  from acme_crm.assets import PageAssets
  from acme_crm.settings import Settings

logger = logging.getLogger('acme_crm')

App = Sanic[Config, SimpleNamespace]

# The name the panel shows and the page title.
ACCOUNT_NAME = 'Acme CRM (demo)'
# The OAuth client's name and scopes, as the contract's `ExternalConnection` carries them.
CLIENT_NAME = 'acme-crm'
CONNECTED_SCOPES = ['contacts.read']
# The fixed authorization code the fake OAuth round trip hands back; a real CRM issues a one-time
# code that the callback exchanges for tokens.
FAKE_CODE = 'fake-code'
# The session cookie (access token and connection state), sent by browsers as `__Host-acme_session`.
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
class AppContext:
  """Everything the route handlers share: configuration, the OAuth store, assets and the clock.

  One instance is created per app by ``create_app`` and captured by the handlers. ``clock`` is
  injectable so tests can move time: the OAuth ``state`` expires after 10 minutes, a stored OAuth
  result after 5 minutes, and the session cookie after 30 days.
  """

  settings: Settings
  assets: PageAssets
  results: OAuthResults
  clock: Callable[[], float]
  # Seconds the page request waits for the demo call to Dialpad's API (see `dialpad_api`).
  api_timeout: float

  def authorize_url(self, key: UserKey) -> str:
    """Build the URL the Connect button sends this user to, with a fresh signed ``state``.

    Called every time a connection status is built (page render and each ``ext-connection``
    answer), so a URL is never reused. The ``state`` binds the OAuth round trip to this user for 10
    minutes: the callback records a result only for the user it names.
    """
    state = signing.issue_state(key.user_id, key.company_id, self.settings.app_secret, self.clock())
    return f'{self.settings.authorize_url}?{urlencode({"state": state})}'

  def state_from_cookie(self, request: Request) -> CookieBackedDatabaseStorage | None:
    """Read this browser's state from the request's session cookie, if it has a valid one.

    The cookie is this app's persistent storage (see ``acme_crm.state``): reading it is how a page
    load, or an API call, learns the access token and whether the user is connected, with no
    server-side record. ``None`` when it is missing, forged or too old. Reads the cookie only;
    never sets it.
    """
    return CookieBackedDatabaseStorage.from_cookie(
        request.cookies.get(COOKIE_HEADER_NAME),
        self.settings.app_secret,
        self.clock(),
    )

  def save_state(self, reply: HTTPResponse, state: CookieBackedDatabaseStorage) -> None:
    """Write ``state`` to ``reply`` as the session cookie, which lasts 30 days from now."""
    _set_session_cookie(reply, state.to_cookie(self.settings.app_secret, self.clock()))

  def external_connection(self, key: UserKey, *, connected: bool) -> ExternalConnection:
    """Build the connection status as the contract's ``ExternalConnection``.

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

  def state_for(self, request: Request) -> CookieBackedDatabaseStorage | None:
    """Authenticate an API call: its ``Authorization: Bearer`` token must be the cookie's token.

    Returns the state in the cookie when the header's token matches the state's access token,
    else ``None``: no header, no cookie, a forged or expired cookie, or a token that isn't the
    cookie's, for example a panel left open after the browser's cookie changed to another user's
    or after ``APP_SECRET`` changed. Requiring both is what stops a cross-site request, which
    carries the ``SameSite=None`` cookie but can't know the token.
    """
    header = request.headers.get('Authorization', '')
    state = self.state_from_cookie(request)
    if state is None or not header.startswith(BEARER):
      return None
    return state if state.has_access_token(header.removeprefix(BEARER)) else None


def _rendered(page: RenderedPage) -> HTTPResponse:
  """Turn a page from ``acme_crm.pages`` into a response, with its status and headers."""
  return html(page.html, status=page.status, headers=page.headers)


def _connection_response(connection: ExternalConnection) -> HTTPResponse:
  """Answer ``200`` with the connection as JSON, the body ``ext-connection`` returns."""
  return json(connection.model_dump(mode='json'))


def _unauthorized() -> HTTPResponse:
  """Answer ``401`` for a missing, unmatched or expired session.

  This is the app's own access token being rejected (no cookie, or a token that isn't the
  cookie's); the panel reacts by asking the user to reload.
  """
  error = ErrorResponse(code='invalid_access_token', message='Reload the panel.')
  return json(error.model_dump(mode='json'), status=401)


def _set_session_cookie(reply: HTTPResponse, value: str) -> None:
  """Set the session cookie on ``reply``, for ``COOKIE_MAX_AGE_SECONDS`` from now.

  The cookie is where this demo persists the user's access token and connection (see
  ``acme_crm.signing``). Its attributes are ``Secure``, ``HttpOnly``, ``SameSite=None`` and
  ``Partitioned``, because the panel runs in a third-party iframe, and the ``__Host-`` prefix, which
  pins it to this host and path ``/``.
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
      max_age=signing.COOKIE_MAX_AGE_SECONDS,
  )


def _register_page(app: App, ctx: AppContext) -> None:
  """Register ``GET /``, the panel page."""
  settings = ctx.settings

  @app.get('/')
  async def page(request: Request) -> HTTPResponse:
    """Render the panel page for the user in the ``idtoken`` query parameter.

    Invoked when Dialpad (or the dev host) loads the iframe. A token that doesn't decode gets a
    ``401`` HTML page. Otherwise the page starts or continues this browser's session: a valid
    session cookie for this same user keeps its access token and connection state, and anything
    else (no cookie, a forged or old one, another user's) starts a new token, not connected. The
    page embeds the token and the connection (with an authorize URL when not connected), and sets
    the session cookie, which refreshes its 30 days. The page data's ``app`` field carries the
    result of the demo call to Dialpad's API (never the api key itself). The server stores nothing.
    """
    try:
      claims = decode_idtoken(request.args.get('idtoken'), settings.client_secret)
    except IdTokenError:
      error = ErrorResponse(code='invalid_idtoken', message='Open this panel from Dialpad.')
      return _rendered(render_error_page(error, status=401,
                                         dialpad_origin=settings.dialpad_origin),)
    key = UserKey(company_id=claims.company_id, user_id=claims.user_id)
    # DEMO ONLY, and UNNECESSARY for this app: the panel works without this request. It shows how
    # the idtoken's `api_key` is used, by calling Dialpad's public API with it right here, on the
    # page request, while the idtoken is in hand. The key is used for this one call and dropped.
    # A real application must NOT work like this: it persists the api key in long-term storage
    # (the key never expires) and uses it to call Dialpad as and when necessary, for example from
    # a background job or a webhook handler, not only when the panel loads. Local mode has no real
    # key (the mock idtoken's is `mock-api-key`, which Dialpad would refuse), so it makes no call.
    demo = skipped() if settings.local_mode else await fetch_dialpad_user(
        claims.api_key,
        origin=settings.dialpad_origin,
        timeout=ctx.api_timeout,
    )
    existing = ctx.state_from_cookie(request)
    state = existing if existing and existing.belongs_to(key) else CookieBackedDatabaseStorage.new(
        key)
    page_data = PageData(
        dialpad_origin=settings.dialpad_origin,
        api_prefix=DEFAULT_API_PREFIX,
        access_token=state.get_access_token(),
        external_connection=ctx.external_connection(
            key,
            connected=state.is_external_connected(),
        ),
        app=demo.as_app_data(),
    )
    options = PageOptions(
        title=ACCOUNT_NAME,
        extra_connect_src=(settings.vite_websocket_origin,) if settings.local_mode else (),
    )
    reply = _rendered(
        render_page(page_data, nonce=generate_nonce(), assets=ctx.assets, options=options),)
    ctx.save_state(reply, state)
    return reply


def _register_contract(app: App, ctx: AppContext) -> None:
  """Register the two contract endpoints the SDK calls with the access token."""
  @app.get(f'{DEFAULT_API_PREFIX}/ext-connection')
  async def ext_connection(request: Request) -> HTTPResponse:
    """Answer whether the calling user is connected to Acme.

    The SDK calls this on start when the page said "not connected", after Dialpad replies to
    Connect, on every poll while the OAuth popup is open, and after a disconnect for a fresh
    authorize URL. The call must carry the access token as ``Authorization: Bearer`` and the
    session cookie, and the two tokens must match (``401`` otherwise). If the OAuth callback has
    recorded a result for this user, it is consumed here: the answer is "connected" and the
    session cookie is rewritten with ``connected`` on, so the next page load starts connected.
    Otherwise the cookie alone decides: it is this app's persistent storage of the connection,
    signed with ``APP_SECRET`` so it can't be forged. The consumed result is a demo-only handoff
    from the popup to this iframe; a real partner answers from the CRM tokens its callback stored
    (see ``acme_crm.stores.OAuthResults``).
    """
    state = ctx.state_for(request)
    if state is None:
      return _unauthorized()
    key = state.user_key()
    if ctx.results.consume(key):
      reply = _connection_response(ctx.external_connection(key, connected=True))
      ctx.save_state(reply, state.with_external_connected(connected=True))
      return reply
    connection = ctx.external_connection(key, connected=state.is_external_connected())
    return _connection_response(connection)

  @app.post(f'{DEFAULT_API_PREFIX}/ext-disconnect')
  async def ext_disconnect(request: Request) -> HTTPResponse:
    """End the connection: turn ``connected`` off in the session cookie and answer ``204``.

    Invoked from the panel's Disconnect button or the host's panel menu, with the same
    authentication as ``ext-connection``. After it the user is not connected; the SDK marks the
    panel disconnected and calls ``ext-connection`` once more for a fresh authorize URL, which is
    why the cookie keeps its access token instead of being cleared: that next call must still
    authenticate. A real partner would also delete the user's CRM tokens here.
    """
    state = ctx.state_for(request)
    if state is None:
      return _unauthorized()
    reply = empty(status=204)
    ctx.save_state(reply, state.with_external_connected(connected=False))
    return reply


def _register_fake_oauth(app: App, ctx: AppContext) -> None:
  """Register the demo-only OAuth round trip that stands in for a real CRM."""
  settings = ctx.settings

  @app.get('/oauth/fake-authorize')
  async def fake_authorize(request: Request) -> HTTPResponse:
    """Show the fake authorize screen: a page labelled as fake, with an Authorize button.

    Invoked when the user clicks Connect and Dialpad opens the authorize URL in a popup (the web)
    or its own login window (the desktop app). A real CRM would ask the user to sign in and
    approve access here. This page just asks for one click, so the popup stays open while the
    panel shows "connecting". Nothing is recorded and no cookie is set; pressing Authorize sends
    the ``state`` and a fixed ``code`` to ``/oauth/callback``.
    """
    state = request.args.get('state')
    if not state:
      return text('state is required', status=400)
    return _rendered(
        render_fake_authorize_page(
            callback_url=settings.callback_url,
            state=state,
            code=FAKE_CODE,
            scopes=CONNECTED_SCOPES,
            nonce=generate_nonce(),
        ),)

  @app.get('/oauth/callback')
  async def callback(request: Request) -> HTTPResponse:
    """Finish the OAuth round trip: record that this user connected and close the popup.

    Invoked inside the popup after the (fake) authorization. A real partner would exchange the
    ``code`` for CRM tokens and store them durably here, and ``ext-connection`` would then answer
    from them. This demo has no CRM tokens, so it only verifies the signed ``state`` and leaves a
    short-lived in-memory note that this user connected, which the panel's next ``ext-connection``
    check consumes (see ``acme_crm.stores.OAuthResults`` for the whole flow and why). An expired,
    forged or mismatched ``state`` renders an error page and records nothing. The reply is the
    close-popup page, which tells Dialpad and closes the window. No cookie is set: the popup is a
    separate window from the panel's iframe.
    """
    state = str(request.args.get('state', ''))
    claims = signing.verify_state(state, settings.app_secret, ctx.clock())
    if claims is None or request.args.get('code') != FAKE_CODE:
      error = ErrorResponse(code='invalid_state', message='This connection link has expired.')
      return _rendered(render_error_page(error, status=400,
                                         dialpad_origin=settings.dialpad_origin),)
    ctx.results.record(UserKey(company_id=claims.company_id, user_id=claims.user_id))
    return _rendered(render_close_popup(settings.dialpad_origin, nonce=generate_nonce()))


def _register_dev(app: App, ctx: AppContext) -> None:
  """Register ``GET /dev/frame-url``, which only exists in local mode.

  The route is registered only when the settings say local mode; no request can switch it on.
  """
  settings = ctx.settings

  @app.get('/dev/frame-url')
  async def frame_url(_request: Request) -> HTTPResponse:
    """Hand the dev host the URL to frame: this app's page with a fresh mock idtoken.

    The dev host stands in for Dialpad, which would fetch a real idtoken and append it itself. CORS
    allows only the dev host's origin.
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
    api_timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> App:
  """Build the Sanic app: its OAuth store, its routes, and the page's assets.

  Called once at startup by ``python -m acme_crm`` and once per test. Finished OAuth results start
  empty and live in this app's memory; everything else the app remembers is in the browsers'
  session cookies. ``clock`` returns the time in seconds, so
  tests can move time; ``name`` must be unique per app in one process; ``api_timeout`` is how long
  the page waits for the demo call to Dialpad's API. Outside local mode this also needs the built
  frontend (``pnpm build``) and serves it under ``/assets``.
  """
  app = Sanic(name, error_handler=QuietErrorHandler(), configure_logging=False)
  # The access log would print each page URL, idtoken included.
  app.config.ACCESS_LOG = False
  ctx = AppContext(
      settings=settings,
      assets=build_assets(settings),
      results=OAuthResults(clock),
      clock=clock,
      api_timeout=api_timeout,
  )

  @app.get('/healthz')
  async def healthz(_request: Request) -> HTTPResponse:
    """Answer ``ok`` once the app is up; the Playwright setup polls this before starting tests."""
    return text('ok')

  _register_page(app, ctx)
  _register_contract(app, ctx)
  _register_fake_oauth(app, ctx)
  if settings.local_mode:
    _register_dev(app, ctx)
  else:
    app.static('/assets', Path(settings.dist_dir) / 'assets')
  return app
