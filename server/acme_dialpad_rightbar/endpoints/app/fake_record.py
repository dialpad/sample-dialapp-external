"""``GET /records/<contact id>``: the demo's stand-in for a CRM's page for one record.

The iframe panel links this URL with the SDK's ``linkRecord`` after it looks a contact up, so
Dialpad's "View Contact" button opens it in a new tab. A real partner links the CRM's own page for
the mapped record instead (see ``contact.py``).
"""

from typing import TYPE_CHECKING

from sanic import HTTPResponse
from sanic import Request

from acme_dialpad_rightbar.fake_record import render_fake_record_page
from acme_dialpad_rightbar.pages import generate_nonce
from acme_dialpad_rightbar.responses import rendered

if TYPE_CHECKING:
  from acme_dialpad_rightbar.context import App
  from acme_dialpad_rightbar.context import AppContext


def register(app: App, _ctx: AppContext) -> None:
  """Register ``GET /records/<contact id>``."""
  @app.get('/records/<contact_id:str>', unquote=True)
  async def fake_record(_request: Request, contact_id: str) -> HTTPResponse:
    """Show the fake CRM record page for this Dialpad contact id.

    Invoked when the user presses "View Contact" in Dialpad. It takes no token and shows only the
    id from the URL, escaped; nothing is looked up or recorded.
    """
    return rendered(render_fake_record_page(contact_id=contact_id, nonce=generate_nonce()))
