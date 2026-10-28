"""``GET /dev/frame-url``: local mode only. Hands the dev host a page URL with a mock idtoken.

The dev host stands in for Dialpad, which would fetch a real idtoken and append it to the panel
URL itself. Registered only when the settings say local mode; no request can switch it on.
"""

from typing import TYPE_CHECKING
from urllib.parse import urlencode

from sanic import HTTPResponse
from sanic import Request
from sanic.response import json

from acme_dialpad_rightbar.dialpad.idtoken import encode_mock_idtoken

if TYPE_CHECKING:
  from acme_dialpad_rightbar.context import App
  from acme_dialpad_rightbar.context import AppContext


def register(app: App, ctx: AppContext) -> None:
  """Register ``GET /dev/frame-url``."""
  settings = ctx.settings

  @app.get('/dev/frame-url')
  async def frame_url(_request: Request) -> HTTPResponse:
    """Hand the dev host the URL to frame: this app's page with a fresh mock idtoken.

    The dev host stands in for Dialpad, which would fetch a real idtoken and append it itself. CORS
    allows only the dev host's origin.
    """
    token = encode_mock_idtoken(settings.client_secret)
    return json(
        {'url': f'{settings.base_url}/?{urlencode({"idtoken": token})}'},
        headers={'Access-Control-Allow-Origin': settings.vite_origin},
    )
