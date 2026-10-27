"""Connect: OAuth between the Dialpad user and their account in the partner's service.

* ``authorize.py``: the connection status the page data and ``ext-connection`` report, with the
  authorize URL that Connect opens.
* ``state.py``: the signed OAuth ``state``, which ties a round trip to one Dialpad user.
* ``callback.py``: ``GET /oauth/callback``, where the service sends the popup after the user
  approves. A real partner exchanges the ``code`` for its tokens and stores them here.
* ``close_popup.py``: the page the callback returns, which tells Dialpad and closes the popup.

Chapter 6 of the guide explains Connect. ``ext-connection`` and ``ext-disconnect`` themselves are
part of the Dialpad contract, in ``acme_dialpad_rightbar.dialpad.endpoints``.
"""

from typing import TYPE_CHECKING

from acme_dialpad_rightbar.connect import callback

if TYPE_CHECKING:
  from acme_dialpad_rightbar.context import App
  from acme_dialpad_rightbar.context import AppContext


def register_connect_endpoints(app: App, ctx: AppContext) -> None:
  """Add Connect's route, the OAuth callback, to ``app``."""
  callback.register(app, ctx)
