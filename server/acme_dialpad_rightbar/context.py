"""What every route handler shares: the app's settings, its storage, assets and clock.

``AppContext`` is built once by ``acme_dialpad_rightbar.app.create_app`` and handed to each
endpoint's ``register`` function, so a handler needs no globals. It holds the app's storage
(``storage``), which every endpoint that talks to the iframe panel uses to authenticate a request.

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

from sanic import Sanic
from sanic.config import Config

if TYPE_CHECKING:
  from collections.abc import Callable

  from acme_dialpad_rightbar.assets import PageAssets
  from acme_dialpad_rightbar.demo.fake_storage import FakeStorage
  from acme_dialpad_rightbar.demo.oauth_results import OAuthResults
  from acme_dialpad_rightbar.settings import Settings

App = Sanic[Config, SimpleNamespace]

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
