"""``GET /oauth/callback``: where the CRM sends the popup after the user approves access.

A real CRM redirects the OAuth popup to the callback URL registered with it, with a ``code`` and the
``state`` it was given. The demo's fake authorize page does the same.
"""

from typing import TYPE_CHECKING

from sanic import HTTPResponse
from sanic import Request

from acme_crm import signing
from acme_crm.contract import ErrorResponse
from acme_crm.fake_oauth import FAKE_CODE
from acme_crm.pages import generate_nonce
from acme_crm.pages import render_close_popup
from acme_crm.pages import render_error_page
from acme_crm.responses import rendered
from acme_crm.stores import UserKey

if TYPE_CHECKING:
  from acme_crm.context import App
  from acme_crm.context import AppContext


def register(app: App, ctx: AppContext) -> None:
  """Register ``GET /oauth/callback``."""
  settings = ctx.settings

  @app.get('/oauth/callback')
  async def callback(request: Request) -> HTTPResponse:
    """Finish the OAuth round trip: record that this user connected and close the popup.

    Invoked inside the popup after the (fake) authorization. A real partner would exchange the
    ``code`` for CRM tokens and store them durably here, and ``ext-connection`` would then answer
    from them. This demo has no CRM tokens, so it only verifies the signed ``state`` and leaves a
    short-lived in-memory note that this user connected, which the iframe panel's next
    ``ext-connection`` check consumes (see ``acme_crm.stores.OAuthResults`` for the whole flow and
    why). An expired, forged or mismatched ``state`` renders an error page and records nothing. The
    reply is the close-popup page, which tells Dialpad and closes the window. No cookie is set: the
    popup is a separate window from the iframe panel.
    """
    state = str(request.args.get('state', ''))
    claims = signing.verify_state(state, settings.app_secret, ctx.clock())
    if claims is None or request.args.get('code') != FAKE_CODE:
      error = ErrorResponse(code='invalid_state', message='This connection link has expired.')
      return rendered(render_error_page(error, status=400, dialpad_origin=settings.dialpad_origin))
    ctx.results.record(UserKey(company_id=claims.company_id, user_id=claims.user_id))
    return rendered(render_close_popup(settings.dialpad_origin, nonce=generate_nonce()))
