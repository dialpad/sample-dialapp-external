"""What every page this app renders shares, and the error page.

Each render function (here, ``dialpad.panel_page`` and ``connect.close_popup``) returns a
``RenderedPage``; the route sends its HTML with its status and all of its headers, which carry the
Content-Security-Policy. The pages are string templates, and every value put into one is escaped
for the place it lands: ``html.escape`` for HTML text and attributes, and ``json_for_script`` for
JSON inside a ``<script>`` element. Nothing here keeps state between calls.
"""

import json
import re
import secrets
from dataclasses import dataclass
from html import escape
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from collections.abc import Sequence

  from acme_dialpad_rightbar.dialpad.contract import ErrorResponse

# An http(s) origin: scheme, host name or bracketed IPv6 address, optional port. Nothing else.
_LABEL = r'[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?'
_HOST = rf'(?:{_LABEL}(?:\.{_LABEL})*|\[[0-9A-Fa-f:.]+\])'
_ORIGIN = re.compile(rf'https?://{_HOST}(?::\d{{1,5}})?')

_ERROR_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light dark">
    <meta name="referrer" content="no-referrer">
    <title>Panel unavailable</title>
    <style nonce="{nonce}">
      body {{ font-family: system-ui, sans-serif; margin: 1rem; }}
    </style>
  </head>
  <body>
    <p>{message}</p>
    <p><small>{code}</small></p>
  </body>
</html>
"""


@dataclass(frozen=True)
class RenderedPage:
  """An HTML response: the body, its status code, and the headers it must be served with.

  Returned by every render function. Serve the headers as they are: the Content-Security-Policy
  carries the nonce baked into the HTML, and ``Cache-Control: no-store`` keeps per-user page data
  out of caches.
  """

  html: str
  headers: dict[str, str]
  status: int = 200


def generate_nonce() -> str:
  """Return a fresh nonce for one response's inline scripts and styles.

  Call it once per request and pass the same value to the render function; reusing a nonce across
  responses defeats the Content-Security-Policy.
  """
  return secrets.token_urlsafe(18)


def require_origin(value: str) -> str:
  """Return ``value`` if it's an http(s) origin, such as ``https://dialpad.com``.

  The Dialpad origin goes into the Content-Security-Policy header and the close-popup script, so
  anything else (a path, a ``;``, whitespace) is refused rather than escaped.
  """
  if not _ORIGIN.fullmatch(value):
    msg = f'expected an origin such as https://dialpad.com, got {value!r}'
    raise ValueError(msg)
  return value


def build_csp(directives: Sequence[tuple[str, Sequence[str]]]) -> str:
  """Join directives into a Content-Security-Policy header value."""
  return '; '.join(' '.join([name, *values]) for name, values in directives)


def common_headers(csp: str) -> dict[str, str]:
  """Return the headers every rendered page is served with: the CSP, no referrer, no caching."""
  return {
      'Content-Security-Policy': csp,
      'Referrer-Policy': 'no-referrer',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
  }


def json_for_script(value: object) -> str:
  r"""Encode ``value`` as JSON that is safe inside a ``<script>`` element.

  ``<``, ``>``, ``&`` and ``'`` become ``\u003c``-style escapes (which JSON reads back as the same
  characters), so no value can close the element, open a comment or break out of a quoted string.
  Keys are sorted so the same data always renders the same bytes.
  """
  return (json.dumps(value, sort_keys=True).replace('<', '\\u003c').replace('>', '\\u003e').replace(
      '&', '\\u0026').replace("'", '\\u0027'))


def render_error_page(
    error: ErrorResponse,
    *,
    status: int,
    dialpad_origin: str,
) -> RenderedPage:
  """Render the minimal HTML page for an error, such as ``401`` (bad or missing idtoken).

  Called by the panel page's route when ``decode_idtoken`` raises or the app refuses the user, and
  by the OAuth callback when its ``state`` is bad. The page shows the error's message, carries no
  page data and runs no scripts, so the SDK never starts. Raises ``ValueError`` if
  ``dialpad_origin`` isn't an http(s) origin.
  """
  nonce = generate_nonce()
  html = _ERROR_TEMPLATE.format(
      message=escape(error.message),
      code=escape(error.code),
      nonce=escape(nonce),
  )
  csp = build_csp([
      ('default-src', ["'none'"]),
      ('style-src', [f"'nonce-{nonce}'"]),
      ('frame-ancestors', [require_origin(dialpad_origin)]),
      ('base-uri', ["'none'"]),
  ])
  return RenderedPage(html=html, headers=common_headers(csp), status=status)
