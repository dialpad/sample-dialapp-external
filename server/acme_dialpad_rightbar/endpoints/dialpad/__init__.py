"""The endpoints of the DialApp contract: the ones Dialpad, or the SDK it ships, calls.

* ``GET /``: the iframe panel page, loaded by Dialpad with the idtoken (``page.py``).
* ``GET /dialpad/ext-connection``: whether the user is connected to the partner's system
  (``ext_connection.py``).
* ``POST /dialpad/ext-disconnect``: end that connection (``ext_disconnect.py``).

The SDK makes the last two itself, with the app's own access token. Everything else the iframe panel
calls is the application's own: see ``acme_dialpad_rightbar.endpoints.app``.
"""

from typing import TYPE_CHECKING

from acme_dialpad_rightbar.endpoints.dialpad import ext_connection
from acme_dialpad_rightbar.endpoints.dialpad import ext_disconnect
from acme_dialpad_rightbar.endpoints.dialpad import page

if TYPE_CHECKING:
  from acme_dialpad_rightbar.context import App
  from acme_dialpad_rightbar.context import AppContext


def register_dialpad_endpoints(app: App, ctx: AppContext) -> None:
  """Add every DialApp contract endpoint to ``app``."""
  page.register(app, ctx)
  ext_connection.register(app, ctx)
  ext_disconnect.register(app, ctx)
