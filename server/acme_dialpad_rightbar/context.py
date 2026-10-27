"""What every route handler shares: the app's settings, its storage, assets and clock.

``AppContext`` is built once by ``acme_dialpad_rightbar.app.create_app`` and handed to each
endpoint's ``register`` function, so a handler needs no globals. It holds the app's storage
(``storage``), which every endpoint that talks to the iframe panel uses to authenticate a request,
and builds the connection status the page data and ``ext-connection`` carry. The constants here name
the demo's one OAuth client.

The storage and the OAuth results are the demo's stand-ins for a database
(``acme_dialpad_rightbar.demo``): the storage keeps the user's access token and whether they are
connected in a signed cookie, and the OAuth callback leaves a note in memory that the user finished
connecting. A real partner keeps both in its own database, in whatever tables it needs: the access
tokens it hands out, and the CRM tokens its OAuth callback stores, which is what "connected" means.
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING
from typing import NamedTuple
from urllib.parse import urlencode

from sanic import Sanic
from sanic.config import Config

from acme_dialpad_rightbar import signing
from acme_dialpad_rightbar.contract import ExternalConnection

if TYPE_CHECKING:
  from collections.abc import Callable

  from acme_dialpad_rightbar.assets import PageAssets
  from acme_dialpad_rightbar.demo.fake_storage import FakeStorage
  from acme_dialpad_rightbar.demo.oauth_results import OAuthResults
  from acme_dialpad_rightbar.settings import Settings

App = Sanic[Config, SimpleNamespace]

# The name the iframe panel shows and the page title.
ACCOUNT_NAME = 'Acme for Dialpad (demo)'
# The OAuth client's name and scopes, as the contract's `ExternalConnection` carries them.
CLIENT_NAME = 'acme-for-dialpad'
CONNECTED_SCOPES = ['contacts.read']
# The prefix of the access token in the `Authorization` header.
BEARER = 'Bearer '


class UserKey(NamedTuple):
  """A Dialpad user, identified by the company and user ids the idtoken carries.

  What the server keys a user's data by, and hashable so it can index a dict.
  """

  company_id: int
  user_id: int


@dataclass
class AppContext:
  """Everything the route handlers share: configuration, storage, OAuth results, assets, clock.

  One instance is created per app by ``create_app`` and captured by the handlers. ``clock`` is
  injectable so tests can move time: the OAuth ``state`` expires after 10 minutes, a stored OAuth
  result after 5 minutes, and the storage cookie after 30 days.
  """

  settings: Settings
  assets: PageAssets
  storage: FakeStorage
  results: OAuthResults
  clock: Callable[[], float]
  # Seconds the page request waits for the demo call to Dialpad's API (see `demo.dialpad_api`).
  api_timeout: float

  def authorize_url(self, key: UserKey) -> str:
    """Build the URL the Connect button sends this user to, with a fresh signed ``state``.

    Called every time a connection status is built (page render and each ``ext-connection``
    answer), so a URL is never reused. The ``state`` binds the OAuth round trip to this user for 10
    minutes: the callback records a result only for the user it names.
    """
    state = signing.issue_state(key.user_id, key.company_id, self.settings.app_secret, self.clock())
    return f'{self.settings.authorize_url}?{urlencode({"state": state})}'

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
