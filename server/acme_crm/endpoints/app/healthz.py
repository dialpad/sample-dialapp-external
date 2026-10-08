"""``GET /healthz``: answers ``ok`` once the app is up.

The browser tests' setup polls it before starting. On Cloud Run the public URL never reaches it
(Google's front end answers that path itself), so it is for local runs and other container hosts.
"""

from typing import TYPE_CHECKING

from sanic import HTTPResponse
from sanic import Request
from sanic.response import text

if TYPE_CHECKING:
  from acme_crm.context import App
  from acme_crm.context import AppContext


def register(app: App, _ctx: AppContext) -> None:
  """Register ``GET /healthz``."""
  @app.get('/healthz')
  async def healthz(_request: Request) -> HTTPResponse:
    """Answer ``ok``."""
    return text('ok')
