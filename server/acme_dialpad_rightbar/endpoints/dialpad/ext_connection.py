"""``GET /dialpad/ext-connection``: whether the calling user is connected to the partner's system.

Part of the DialApp contract: the SDK calls it with the app's access token on start when the page
said "not connected", after Dialpad replies to Connect, on every poll while the OAuth popup is open,
and after a disconnect for a fresh authorize URL. The answer is the contract's
``ExternalConnection``.
"""

from typing import TYPE_CHECKING

from sanic import HTTPResponse
from sanic import Request

from acme_dialpad_rightbar.contract import DEFAULT_API_PREFIX
from acme_dialpad_rightbar.responses import connection_response
from acme_dialpad_rightbar.responses import unauthorized

if TYPE_CHECKING:
  from acme_dialpad_rightbar.context import App
  from acme_dialpad_rightbar.context import AppContext


def register(app: App, ctx: AppContext) -> None:
  """Register ``GET /dialpad/ext-connection``."""
  @app.get(f'{DEFAULT_API_PREFIX}/ext-connection')
  async def ext_connection(request: Request) -> HTTPResponse:
    """Answer whether the calling user is connected to Acme.

    The call must carry the access token as ``Authorization: Bearer`` and the session cookie, and
    the two tokens must match (``401`` otherwise). If the OAuth callback has recorded a result for
    this user, it is consumed here: the answer is "connected" and the session cookie is rewritten
    with ``connected`` on, so the next page load starts connected. Otherwise the cookie alone
    decides: it is this app's persistent storage of the connection, signed with ``APP_SECRET`` so it
    can't be forged. The consumed result is a demo-only handoff from the popup to this iframe; a
    real partner answers from the CRM tokens its callback stored (see
    ``acme_dialpad_rightbar.stores.OAuthResults``).
    """
    state = ctx.state_for(request)
    if state is None:
      return unauthorized()
    key = state.user_key()
    if ctx.results.consume(key):
      reply = connection_response(ctx.external_connection(key, connected=True))
      ctx.save_state(reply, state.with_external_connected(connected=True))
      return reply
    return connection_response(ctx.external_connection(key,
                                                       connected=state.is_external_connected()))
