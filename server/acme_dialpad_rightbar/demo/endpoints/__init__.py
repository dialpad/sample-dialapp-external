"""The routes only the demo has. A real app deletes them, or keeps the dev route for local mode.

* ``GET /oauth/fake-authorize``: a stand-in for the CRM's consent screen, clearly labelled fake
  (``fake_authorize.py``). A real partner's authorize URL is their CRM's.
* ``GET /healthz``: answers ``ok`` once the app is up, for the Playwright browser tests
  (``healthz.py``).
* ``GET /dev/frame-url``: local mode only, hands the dev host a page URL with a mock idtoken
  (``dev_frame_url.py``).
"""

from typing import TYPE_CHECKING

from acme_dialpad_rightbar.demo.endpoints import dev_frame_url
from acme_dialpad_rightbar.demo.endpoints import fake_authorize
from acme_dialpad_rightbar.demo.endpoints import healthz

if TYPE_CHECKING:
  from acme_dialpad_rightbar.context import App
  from acme_dialpad_rightbar.context import AppContext


def register_demo_endpoints(app: App, ctx: AppContext) -> None:
  """Add the demo's routes to ``app``.

  The dev route is registered only when the settings say local mode; no request can switch it on.
  """
  healthz.register(app, ctx)
  fake_authorize.register(app, ctx)
  if ctx.settings.local_mode:
    dev_frame_url.register(app, ctx)
