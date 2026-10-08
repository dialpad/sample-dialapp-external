"""The Acme for Dialpad server: bare Sanic, built on its own copy of the DialApp contract.

``create_app`` wires it together: the shared ``AppContext`` (``acme_dialpad_rightbar.context``), the
endpoints (``acme_dialpad_rightbar.endpoints``: ``dialpad/`` for the DialApp contract's, ``app/``
for the application's own), and the built iframe panel's assets. Where each piece of state lives,
and how a request from the iframe panel is authenticated, is explained in
``acme_dialpad_rightbar.context``.
"""

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING
from typing import override

from sanic import Request
from sanic import Sanic
from sanic.handlers import ErrorHandler

from acme_dialpad_rightbar.assets import build_assets
from acme_dialpad_rightbar.context import App
from acme_dialpad_rightbar.context import AppContext
from acme_dialpad_rightbar.dialpad_api import DEFAULT_TIMEOUT_SECONDS
from acme_dialpad_rightbar.endpoints.app import register_app_endpoints
from acme_dialpad_rightbar.endpoints.dialpad import register_dialpad_endpoints
from acme_dialpad_rightbar.stores import OAuthResults

if TYPE_CHECKING:
  from collections.abc import Callable

  from acme_dialpad_rightbar.settings import Settings

logger = logging.getLogger('acme_dialpad_rightbar')


class QuietErrorHandler(ErrorHandler):
  """Error handler that never logs a request's query string.

  Sanic's default handler logs the full URL of a failing request. The page URL carries the idtoken,
  which never expires, so a failure there would write a long-lived credential into the logs.
  """
  @staticmethod
  @override
  def log(request: Request, exception: Exception) -> None:
    """Log an unhandled error as ``METHOD /path failed: ExceptionType``.

    Sanic calls this for every exception a handler raises; the response (a 500 page) is built
    separately and carries no detail.
    """
    logger.error('%s %s failed: %s', request.method, request.path, type(exception).__name__)


def create_app(
    settings: Settings,
    *,
    clock: Callable[[], float] = time.time,
    name: str = 'acme_dialpad_rightbar',
    api_timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> App:
  """Build the Sanic app: its OAuth store, its routes, and the page's assets.

  Called once at startup by ``python -m acme_dialpad_rightbar`` and once per test. Finished OAuth
  results start empty and live in this app's memory; everything else the app remembers is in the
  browsers' session cookies. ``clock`` returns the time in seconds, so tests can move time; ``name``
  must be unique per app in one process; ``api_timeout`` is how long the page waits for the demo
  call to Dialpad's API. Outside local mode this also needs the built iframe panel (``pnpm build``)
  and serves it under ``/assets``.
  """
  app = Sanic(name, error_handler=QuietErrorHandler(), configure_logging=False)
  # The access log would print each page URL, idtoken included.
  app.config.ACCESS_LOG = False
  ctx = AppContext(
      settings=settings,
      assets=build_assets(settings),
      results=OAuthResults(clock),
      clock=clock,
      api_timeout=api_timeout,
  )
  register_dialpad_endpoints(app, ctx)
  register_app_endpoints(app, ctx)
  if not settings.local_mode:
    app.static('/assets', Path(settings.dist_dir) / 'assets')
  return app
