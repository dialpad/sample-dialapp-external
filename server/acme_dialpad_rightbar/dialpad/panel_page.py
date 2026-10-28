"""The iframe panel page: the page data element, the app's assets, and its Content-Security-Policy.

The CSP lets only the Dialpad origin frame the panel, and only this app's scripts run. The page
data is JSON in a ``<script>`` element, encoded with ``pages.json_for_script`` so no value can close
the element.
"""

from dataclasses import dataclass
from dataclasses import field
from html import escape
from typing import TYPE_CHECKING
from typing import Any

from acme_dialpad_rightbar.dialpad.contract import PAGE_DATA_ELEMENT_ID
from acme_dialpad_rightbar.dialpad.contract import PAGE_DATA_VERSION
from acme_dialpad_rightbar.pages import RenderedPage
from acme_dialpad_rightbar.pages import build_csp
from acme_dialpad_rightbar.pages import common_headers
from acme_dialpad_rightbar.pages import json_for_script
from acme_dialpad_rightbar.pages import require_origin

if TYPE_CHECKING:
  from collections.abc import Sequence

  from acme_dialpad_rightbar.assets import PageAssets
  from acme_dialpad_rightbar.dialpad.contract import PageData

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


@dataclass(frozen=True)
class PageOptions:
  """Optional knobs for ``render_page``.

  ``title`` is the page's ``<title>``. ``extra_connect_src`` adds a ``connect-src`` directive
  (``'self'`` plus these sources), for example the Vite dev server's websocket origin in local mode.
  """

  title: str = 'Dialpad panel'
  extra_connect_src: Sequence[str] = field(default=())


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
                       f'nonce="{escape(nonce)}">{json_for_script(envelope)}</script>')
  html = _PAGE_TEMPLATE.format(
      title=escape(opts.title),
      styles=styles,
      page_data_element=page_data_element,
      scripts=scripts,
  )
  directives: list[tuple[str, Sequence[str]]] = [
      ('frame-ancestors', [require_origin(page_data.dialpad_origin)]),
      ('script-src', ["'self'", f"'nonce-{nonce}'", *dict.fromkeys(assets.origins)]),
      ('object-src', ["'none'"]),
      ('base-uri', ["'none'"]),
  ]
  if opts.extra_connect_src:
    directives.append(('connect-src', ["'self'", *dict.fromkeys(opts.extra_connect_src)]))
  return RenderedPage(html=html, headers=common_headers(build_csp(directives)))
