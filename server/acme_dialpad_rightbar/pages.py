"""The pages this app renders itself: the iframe panel page, the close popup and the error page.

Each render function returns a ``RenderedPage``; the route sends its HTML with its status and all of
its headers, which carry the Content-Security-Policy that lets only the Dialpad origin frame the
iframe panel, and only this app's scripts run. The pages are string templates, like
``fake_oauth.py``'s, and every value put into one is escaped for the place it lands: ``html.escape``
for HTML text and attributes, and a ``<script>``-safe JSON encoding for the page data and the
close-popup's origin. Nothing here keeps state between calls.
"""

import json
import re
import secrets
from dataclasses import dataclass
from dataclasses import field
from html import escape
from typing import TYPE_CHECKING
from typing import Any

from acme_dialpad_rightbar.contract import PAGE_DATA_ELEMENT_ID
from acme_dialpad_rightbar.contract import PAGE_DATA_VERSION

if TYPE_CHECKING:
  from collections.abc import Sequence

  from acme_dialpad_rightbar.assets import PageAssets
  from acme_dialpad_rightbar.contract import ErrorResponse
  from acme_dialpad_rightbar.contract import PageData

# An http(s) origin: scheme, host name or bracketed IPv6 address, optional port. Nothing else.
_LABEL = r'[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?'
_HOST = rf'(?:{_LABEL}(?:\.{_LABEL})*|\[[0-9A-Fa-f:.]+\])'
_ORIGIN = re.compile(rf'https?://{_HOST}(?::\d{{1,5}})?')

_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="referrer" content="no-referrer">
    <title>{title}</title>{styles}
    {page_data_element}{scripts}
  </head>
  <body>
    <div id="app"></div>
  </body>
</html>
"""

_CLOSE_POPUP_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light dark">
    <meta name="referrer" content="no-referrer">
    <title>Connected</title>
    <style nonce="{nonce}">
      body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
    </style>
  </head>
  <body>
    <p id="fallback" role="status" hidden>You can close this window.</p>
    <script nonce="{nonce}">
      {{
        const dialpadOrigin = {dialpad_origin};
        // On the web the opener is Dialpad, which resolves the pending Connect request; the desktop
        // app's login window has no opener. postMessage drops the message if the opener has
        // navigated to another origin.
        if (window.opener) {{
          window.opener.postMessage('close_popup', dialpadOrigin);
        }}
        window.close();
        // Still open: the browser refused to close a window it didn't open by script.
        setTimeout(() => {{
          document.getElementById('fallback').hidden = false;
        }}, 300);
      }}
    </script>
    <noscript><p>You can close this window.</p></noscript>
  </body>
</html>
"""

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


@dataclass(frozen=True)
class PageOptions:
  """Optional knobs for ``render_page``.

  ``title`` is the page's ``<title>``. ``extra_connect_src`` adds a ``connect-src`` directive
  (``'self'`` plus these sources), for example the Vite dev server's websocket origin in local mode.
  """

  title: str = 'Dialpad panel'
  extra_connect_src: Sequence[str] = field(default=())


def generate_nonce() -> str:
  """Return a fresh nonce for one response's inline scripts and styles.

  Call it once per request and pass the same value to ``render_page`` or ``render_close_popup``;
  reusing a nonce across responses defeats the Content-Security-Policy.
  """
  return secrets.token_urlsafe(18)


def _require_origin(value: str) -> str:
  """Return ``value`` if it's an http(s) origin, such as ``https://dialpad.com``.

  The Dialpad origin goes into the Content-Security-Policy header and the close-popup script, so
  anything else (a path, a ``;``, whitespace) is refused rather than escaped.
  """
  if not _ORIGIN.fullmatch(value):
    msg = f'expected an origin such as https://dialpad.com, got {value!r}'
    raise ValueError(msg)
  return value


def _csp(directives: Sequence[tuple[str, Sequence[str]]]) -> str:
  """Join directives into a Content-Security-Policy header value."""
  return '; '.join(' '.join([name, *values]) for name, values in directives)


def _common_headers(csp: str) -> dict[str, str]:
  """Return the headers every rendered page is served with: the CSP, no referrer, no caching."""
  return {
      'Content-Security-Policy': csp,
      'Referrer-Policy': 'no-referrer',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
  }


def _json_for_script(value: object) -> str:
  r"""Encode ``value`` as JSON that is safe inside a ``<script>`` element.

  ``<``, ``>``, ``&`` and ``'`` become ``\u003c``-style escapes (which JSON reads back as the same
  characters), so no value can close the element, open a comment or break out of a quoted string.
  Keys are sorted so the same data always renders the same bytes.
  """
  return (json.dumps(value, sort_keys=True).replace('<', '\\u003c').replace('>', '\\u003e').replace(
      '&', '\\u0026').replace("'", '\\u0027'))


def render_page(
    page_data: PageData,
    *,
    nonce: str,
    assets: PageAssets,
    options: PageOptions | None = None,
) -> RenderedPage:
  """Render the whole iframe panel page: the page data element, the app's assets, and the headers.

  Called by the page route on every iframe panel open, after ``decode_idtoken`` succeeds. The page
  is one mount element plus the page data (with the format ``version`` the SDK checks, never the API
  key); once the browser loads it, the SDK's ``createRightbar()`` reads the data and starts. The
  Content-Security-Policy lets only the Dialpad origin frame the page, and only same-origin
  scripts, the assets' origins and the nonce run scripts. Raises ``ValueError`` if
  ``page_data.dialpad_origin`` isn't an http(s) origin.
  """
  opts = options or PageOptions()
  envelope: dict[str, Any] = {'version': PAGE_DATA_VERSION, **page_data.model_dump(mode='json')}
  styles = ''.join(f'\n    <link rel="stylesheet" href="{escape(href)}">' for href in assets.styles)
  scripts = ''.join(
      f'\n    <script type="module" src="{escape(src)}" nonce="{escape(nonce)}"></script>'
      for src in assets.scripts)
  page_data_element = (f'<script type="application/json" id="{PAGE_DATA_ELEMENT_ID}" '
                       f'nonce="{escape(nonce)}">{_json_for_script(envelope)}</script>')
  html = _PAGE_TEMPLATE.format(
      title=escape(opts.title),
      styles=styles,
      page_data_element=page_data_element,
      scripts=scripts,
  )
  directives: list[tuple[str, Sequence[str]]] = [
      ('frame-ancestors', [_require_origin(page_data.dialpad_origin)]),
      ('script-src', ["'self'", f"'nonce-{nonce}'", *dict.fromkeys(assets.origins)]),
      ('object-src', ["'none'"]),
      ('base-uri', ["'none'"]),
  ]
  if opts.extra_connect_src:
    directives.append(('connect-src', ["'self'", *dict.fromkeys(opts.extra_connect_src)]))
  return RenderedPage(html=html, headers=_common_headers(_csp(directives)))


def render_close_popup(dialpad_origin: str, *, nonce: str) -> RenderedPage:
  """Render the page the OAuth callback returns once it has recorded the connection.

  Called by the OAuth callback route at the end of Connect. It posts ``close_popup`` to its opener,
  to the Dialpad origin only, when it has one (the web), then closes itself (the desktop app's login
  window has no opener). If the browser refuses to close the window, it shows a short "you can close
  this window" message. The iframe panel's SDK then sees the new connection on its next status check
  and shows the user as connected. Raises ``ValueError`` if ``dialpad_origin`` isn't an http(s)
  origin.
  """
  html = _CLOSE_POPUP_TEMPLATE.format(
      dialpad_origin=_json_for_script(_require_origin(dialpad_origin)),
      nonce=escape(nonce),
  )
  csp = _csp([
      ('default-src', ["'none'"]),
      ('script-src', [f"'nonce-{nonce}'"]),
      ('style-src', [f"'nonce-{nonce}'"]),
      ('frame-ancestors', ["'none'"]),
      ('base-uri', ["'none'"]),
  ])
  return RenderedPage(html=html, headers=_common_headers(csp))


def render_error_page(
    error: ErrorResponse,
    *,
    status: int,
    dialpad_origin: str,
) -> RenderedPage:
  """Render the minimal HTML page for ``401`` (bad or missing idtoken) or ``403`` (refused user).

  Called by the page route instead of ``render_page`` when ``decode_idtoken`` raises or the app
  refuses the user. The page shows the error's message in the iframe panel, carries no page data and
  runs no scripts, so the SDK never starts. Raises ``ValueError`` if ``dialpad_origin`` isn't an
  http(s) origin.
  """
  nonce = generate_nonce()
  html = _ERROR_TEMPLATE.format(
      message=escape(error.message),
      code=escape(error.code),
      nonce=escape(nonce),
  )
  csp = _csp([
      ('default-src', ["'none'"]),
      ('style-src', [f"'nonce-{nonce}'"]),
      ('frame-ancestors', [_require_origin(dialpad_origin)]),
      ('base-uri', ["'none'"]),
  ])
  return RenderedPage(html=html, headers=_common_headers(csp), status=status)
