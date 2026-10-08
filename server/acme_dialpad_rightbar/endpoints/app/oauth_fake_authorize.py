"""``GET /oauth/fake-authorize``: the demo's stand-in for a CRM's sign-in and consent screen.

Dialpad opens the authorize URL from the page data in a popup (on the web) or its own login window
(the desktop app) when the user presses Connect. A real partner's authorize URL is their CRM's;
this page is clearly labelled fake and only asks for one click.
"""

from typing import TYPE_CHECKING

from sanic import HTTPResponse
from sanic import Request
from sanic.response import text

from acme_dialpad_rightbar.context import CONNECTED_SCOPES
from acme_dialpad_rightbar.fake_oauth import FAKE_CODE
from acme_dialpad_rightbar.fake_oauth import render_fake_authorize_page
from acme_dialpad_rightbar.pages import generate_nonce
from acme_dialpad_rightbar.responses import rendered

if TYPE_CHECKING:
  from acme_dialpad_rightbar.context import App
  from acme_dialpad_rightbar.context import AppContext


def register(app: App, ctx: AppContext) -> None:
  """Register ``GET /oauth/fake-authorize``."""
  settings = ctx.settings

  @app.get('/oauth/fake-authorize')
  async def fake_authorize(request: Request) -> HTTPResponse:
    """Show the fake authorize screen: a page labelled as fake, with an Authorize button.

    Invoked when the user clicks Connect and Dialpad opens the authorize URL in a popup (the web)
    or its own login window (the desktop app). A real CRM would ask the user to sign in and
    approve access here. This page just asks for one click, so the popup stays open while the
    iframe panel shows "connecting". Nothing is recorded and no cookie is set; pressing Authorize
    sends the ``state`` and a fixed ``code`` to ``/oauth/callback``.
    """
    state = request.args.get('state')
    if not state:
      return text('state is required', status=400)
    return rendered(
        render_fake_authorize_page(
            callback_url=settings.callback_url,
            state=state,
            code=FAKE_CODE,
            scopes=CONNECTED_SCOPES,
            nonce=generate_nonce(),
        ))
