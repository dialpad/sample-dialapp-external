"""``GET /dialpad/ext-connection``: whether the calling user is connected to the partner's system.

Part of the DialApp contract: the SDK calls it with the app's access token on start when the page
said "not connected", after Dialpad replies to Connect, on every poll while the OAuth popup is open,
and after a disconnect for a fresh authorize URL. The answer is the contract's
``ExternalConnection``.
"""

from typing import TYPE_CHECKING

from sanic import HTTPResponse
from sanic import Request

from acme_dialpad_rightbar.contract import CONTRACT_PATH_PREFIX
from acme_dialpad_rightbar.responses import connection_response
from acme_dialpad_rightbar.responses import unauthorized

if TYPE_CHECKING:
  from acme_dialpad_rightbar.context import App
  from acme_dialpad_rightbar.context import AppContext


def register(app: App, ctx: AppContext) -> None:
  """Register ``GET /dialpad/ext-connection``."""
  @app.get(f'{CONTRACT_PATH_PREFIX}/ext-connection')
  async def ext_connection(request: Request) -> HTTPResponse:
    """Answer whether the calling user is connected to Acme.

    The call must carry the access token as ``Authorization: Bearer``, and it must match the stored
    token (``401`` otherwise; in the demo, the storage cookie's token). If the OAuth callback has
    recorded a result for this user, it is consumed here: the answer is "connected" and the stored
    user is saved with ``connected`` on, so the next page load starts connected. Otherwise the
    stored user alone decides. The consumed result is a demo-only handoff from the popup to this
    iframe; a real partner answers from the CRM tokens its callback stored (see
    ``acme_dialpad_rightbar.demo.oauth_results.OAuthResults``).
    """
    user = ctx.storage.authenticate(request)
    if user is None:
      return unauthorized()
    key = user.user_key()
    if ctx.results.consume(key):
      reply = connection_response(ctx.external_connection(key, connected=True))
      ctx.storage.save(reply, user.with_external_connected(connected=True))
      return reply
    return connection_response(ctx.external_connection(key, connected=user.is_external_connected()))
