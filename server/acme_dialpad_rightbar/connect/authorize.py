"""The user's connection to the partner's service, as the page data and ``ext-connection`` say.

``external_connection`` builds the contract's ``ExternalConnection``: whether the user is connected,
and the authorize URL that Connect opens. Every URL it builds carries a fresh signed ``state``
(``connect.state``), so a URL is never reused.
"""

from typing import TYPE_CHECKING
from urllib.parse import urlencode

from acme_dialpad_rightbar.connect.state import issue_state
from acme_dialpad_rightbar.dialpad.contract import ExternalConnection
from acme_dialpad_rightbar.settings import CLIENT_NAME
from acme_dialpad_rightbar.settings import CONNECTED_SCOPES

if TYPE_CHECKING:
  from acme_dialpad_rightbar.context import AppContext
  from acme_dialpad_rightbar.context import UserKey


def authorize_url(ctx: AppContext, key: UserKey) -> str:
  """Build the URL the Connect button sends this user to, with a fresh signed ``state``.

  Called every time a connection status is built (page render and each ``ext-connection`` answer),
  so a URL is never reused. The ``state`` binds the OAuth round trip to this user for 10 minutes:
  the callback records a result only for the user it names.
  """
  state = issue_state(key.user_id, key.company_id, ctx.settings.app_secret, ctx.clock())
  return f'{ctx.settings.authorize_url}?{urlencode({"state": state})}'


def external_connection(ctx: AppContext, key: UserKey, *, connected: bool) -> ExternalConnection:
  """Build the connection status as the contract's ``ExternalConnection``.

  Used for the page data and every ``ext-connection`` answer. It always carries one authorize URL
  (even when connected, so the SDK has a fresh one ready after a disconnect); the scopes are the
  client's when connected and empty otherwise.
  """
  return ExternalConnection(
      connected=connected,
      authorization_urls={CLIENT_NAME: authorize_url(ctx, key)},
      name=CLIENT_NAME,
      scopes=CONNECTED_SCOPES if connected else [],
  )
