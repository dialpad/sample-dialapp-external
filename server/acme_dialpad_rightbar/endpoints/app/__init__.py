"""The application's own endpoints, as opposed to the DialApp contract's (``endpoints/dialpad/``).

* ``GET /oauth/callback``: the OAuth redirect URI, which a real app has too (``oauth_callback.py``).
  The demo only records that the user connected; a real partner exchanges the ``code`` for CRM
  tokens here and persists them in a database.

A real application has many routes of its own: contacts, notes, search, and so on. This one's are in
``acme_dialpad_rightbar.crm`` (the CRM record) and ``acme_dialpad_rightbar.demo.endpoints`` (the
routes only the demo has).
"""

from typing import TYPE_CHECKING

from acme_dialpad_rightbar.endpoints.app import oauth_callback

if TYPE_CHECKING:
  from acme_dialpad_rightbar.context import App
  from acme_dialpad_rightbar.context import AppContext


def register_app_endpoints(app: App, ctx: AppContext) -> None:
  """Add every application endpoint to ``app``."""
  oauth_callback.register(app, ctx)
