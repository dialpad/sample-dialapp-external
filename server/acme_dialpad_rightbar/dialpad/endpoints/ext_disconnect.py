"""``POST /dialpad/ext-disconnect``: end the calling user's connection to the partner's system.

Part of the DialApp contract: the SDK calls it with the app's access token when the user presses
Disconnect in the iframe panel, or in Dialpad's own panel menu.
"""

from typing import TYPE_CHECKING

from sanic import HTTPResponse
from sanic import Request
from sanic.response import empty

from acme_dialpad_rightbar.dialpad.contract import CONTRACT_PATH_PREFIX
from acme_dialpad_rightbar.responses import unauthorized

if TYPE_CHECKING:
  from acme_dialpad_rightbar.context import App
  from acme_dialpad_rightbar.context import AppContext


def register(app: App, ctx: AppContext) -> None:
  """Register ``POST /dialpad/ext-disconnect``."""
  @app.post(f'{CONTRACT_PATH_PREFIX}/ext-disconnect')
  async def ext_disconnect(request: Request) -> HTTPResponse:
    """End the connection: turn ``connected`` off in the stored user and answer ``204``.

    Invoked from the iframe panel's Disconnect button or the host's iframe panel menu, with the same
    authentication as ``ext-connection``. After it the user is not connected; the SDK marks the
    iframe panel disconnected and calls ``ext-connection`` once more for a fresh authorize URL,
    which is why the stored user keeps its access token instead of being cleared: that next call
    must still authenticate. A real partner would also delete the user's CRM tokens here.
    """
    user = ctx.storage.authenticate(request)
    if user is None:
      return unauthorized()
    reply = empty(status=204)
    ctx.storage.save(reply, user.with_external_connected(connected=False))
    return reply
