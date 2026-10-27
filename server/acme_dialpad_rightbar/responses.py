"""The response shapes the endpoints share: rendered pages, the connection, and errors."""

from typing import TYPE_CHECKING

from sanic.response import html
from sanic.response import json

from acme_dialpad_rightbar.dialpad.contract import ErrorResponse

if TYPE_CHECKING:
  from sanic import HTTPResponse

  from acme_dialpad_rightbar.dialpad.contract import ExternalConnection
  from acme_dialpad_rightbar.pages import RenderedPage


def rendered(page: RenderedPage) -> HTTPResponse:
  """Turn a page from ``acme_dialpad_rightbar.pages`` into a response, with status and headers."""
  return html(page.html, status=page.status, headers=page.headers)


def connection_response(connection: ExternalConnection) -> HTTPResponse:
  """Answer ``200`` with the connection as JSON, the body ``ext-connection`` returns."""
  return json(connection.model_dump(mode='json'))


def error(code: str, message: str, status: int) -> HTTPResponse:
  """Answer with the contract's ``ErrorResponse`` shape (``code`` and ``message``) as JSON."""
  return json(ErrorResponse(code=code, message=message).model_dump(mode='json'), status=status)


def unauthorized() -> HTTPResponse:
  """Answer ``401`` for a missing, unmatched or expired access token.

  This is the app's own access token being rejected (no cookie, or a token that isn't the
  cookie's); the iframe panel reacts by asking the user to reload.
  """
  return error('invalid_access_token', 'Reload the panel.', 401)
