"""What every route handler shares: the app's settings, its one in-memory store, assets and clock.

``AppContext`` is built once by ``acme_crm.app.create_app`` and handed to each endpoint's
``register`` function, so a handler needs no globals. It also holds the two operations every
endpoint that talks to the iframe panel needs: reading the session cookie (``state_from_cookie``,
``save_state``) and authenticating a request (``state_for``). The constants here name the demo's
one OAuth client and its session cookie.

What this demo has to remember for good, the user's access token and whether they are connected,
it keeps in the browser: one signed session cookie (HMAC-SHA256 with ``APP_SECRET``, bound to the
Dialpad user and company, valid for 30 days) is the app's persistent storage. The server keeps no
database. The page load sets the cookie and embeds the same token in the page data; the endpoints
the iframe panel calls accept a request only when its ``Authorization: Bearer`` value equals the
token in the cookie. The handlers read and change that state only through
``CookieBackedDatabaseStorage`` (``acme_crm.database``), whose getters are ``get_access_token`` and
``is_external_connected``: it plays the per-user database row a real partner would keep. A real
partner stores the CRM tokens it gets from the OAuth callback instead, and answers from those; see
``acme_crm.stores.OAuthResults`` and ``acme_crm.signing``.
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from sanic import HTTPResponse
from sanic import Request
from sanic import Sanic
from sanic.config import Config

from acme_crm import signing
from acme_crm.contract import ExternalConnection
from acme_crm.database import CookieBackedDatabaseStorage

if TYPE_CHECKING:
  from collections.abc import Callable

  from acme_crm.assets import PageAssets
  from acme_crm.settings import Settings
  from acme_crm.stores import OAuthResults
  from acme_crm.stores import UserKey

App = Sanic[Config, SimpleNamespace]

# The name the iframe panel shows and the page title.
ACCOUNT_NAME = 'Acme CRM (demo)'
# The OAuth client's name and scopes, as the contract's `ExternalConnection` carries them.
CLIENT_NAME = 'acme-crm'
CONNECTED_SCOPES = ['contacts.read']
# The session cookie (access token and connection state), sent by browsers as `__Host-acme_session`.
COOKIE_NAME = 'acme_session'
# Sanic prefixes the name with `__Host-` when host_prefix is set, and reports it that way back.
COOKIE_HEADER_NAME = f'__Host-{COOKIE_NAME}'
# The prefix of the access token in the `Authorization` header.
BEARER = 'Bearer '


def _set_session_cookie(reply: HTTPResponse, value: str) -> None:
  """Set the session cookie on ``reply``, for ``COOKIE_MAX_AGE_SECONDS`` from now.

  The cookie is where this demo persists the user's access token and connection (see
  ``acme_crm.signing``). Its attributes are ``Secure``, ``HttpOnly``, ``SameSite=None`` and
  ``Partitioned``, because the iframe panel runs in a third-party iframe, and the ``__Host-``
  prefix, which pins it to this host and path ``/``.
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

    The cookie is this app's persistent storage (see ``acme_crm.database``): reading it is how a
    page load, or an API call, learns the access token and whether the user is connected, with no
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
    """Authenticate a request from the iframe panel: its bearer token must be the cookie's token.

    Every route the iframe panel calls uses this, the SDK's two contract endpoints and any the
    application adds.

    Returns the state in the cookie when the header's token matches the state's access token,
    else ``None``: no header, no cookie, a forged or expired cookie, or a token that isn't the
    cookie's, for example an iframe panel left open after the browser's cookie changed to another
    user's or after ``APP_SECRET`` changed. Requiring both is what stops a cross-site request, which
    carries the ``SameSite=None`` cookie but can't know the token.
    """
    header = request.headers.get('Authorization', '')
    state = self.state_from_cookie(request)
    if state is None or not header.startswith(BEARER):
      return None
    return state if state.has_access_token(header.removeprefix(BEARER)) else None
