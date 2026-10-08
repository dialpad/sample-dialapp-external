"""``GET /healthz``: answers ``ok`` once the app is up.

This exists mainly for the browser end-to-end tests: Playwright's ``webServer`` setup polls it to
know when the server is ready before the tests start. Partners can ignore it, and need not copy it.
Nothing else uses it (no Dockerfile ``HEALTHCHECK``, no probe). On Cloud Run the public URL never
reaches it (Google's front end answers that path itself); a container host that wants a health
check can point one at it.
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
