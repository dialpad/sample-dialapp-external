"""The application's own endpoints, as opposed to the DialApp contract's (``endpoints/dialpad/``).

* ``POST /api/contact``: a sample endpoint that the client library doesn't invoke, but the
  application's own frontend does, showcasing feature extensibility (``contact.py``). A real
  application has many such routes: contacts, notes, search, and so on.
* ``GET /records/<contact id>``: a stand-in for the partner CRM's page for a record, clearly
  labelled fake, which the iframe panel links so Dialpad's "View Contact" button opens it
  (``fake_record.py``). A real partner links their CRM's own record page.
* ``GET /oauth/fake-authorize``: a stand-in for the partner CRM's consent screen, clearly labelled
  fake (``oauth_fake_authorize.py``). A real partner replaces it with their CRM's authorize URL.
* ``GET /oauth/callback``: the OAuth redirect URI, which a real app has too (``oauth_callback.py``).
  The demo only records that the user connected; a real partner exchanges the ``code`` for CRM
  tokens here and persists them in a database.
* ``GET /healthz``: answers ``ok`` once the app is up. Used by the Playwright e2e setup; partners
  can ignore it (``healthz.py``).
* ``GET /dev/frame-url``: local mode only, hands the dev host a page URL with a mock idtoken
  (``dev_frame_url.py``).
"""

from typing import TYPE_CHECKING

from acme_dialpad_rightbar.endpoints.app import contact
from acme_dialpad_rightbar.endpoints.app import dev_frame_url
from acme_dialpad_rightbar.endpoints.app import fake_record
from acme_dialpad_rightbar.endpoints.app import healthz
from acme_dialpad_rightbar.endpoints.app import oauth_callback
from acme_dialpad_rightbar.endpoints.app import oauth_fake_authorize

if TYPE_CHECKING:
  from acme_dialpad_rightbar.context import App
  from acme_dialpad_rightbar.context import AppContext


def register_app_endpoints(app: App, ctx: AppContext) -> None:
  """Add every application endpoint to ``app``.

  The dev route is registered only when the settings say local mode; no request can switch it on.
  """
  healthz.register(app, ctx)
  contact.register(app, ctx)
  fake_record.register(app, ctx)
  oauth_fake_authorize.register(app, ctx)
  oauth_callback.register(app, ctx)
  if ctx.settings.local_mode:
    dev_frame_url.register(app, ctx)
