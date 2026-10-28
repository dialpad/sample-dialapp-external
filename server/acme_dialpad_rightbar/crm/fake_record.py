"""``GET /records/<contact id>``: the fake CRM record, the page Dialpad's View button opens.

Once the iframe panel has looked a contact up, it calls the SDK's ``linkRecord`` with a URL, and
Dialpad shows an arrow button, with the tooltip "View Contact", that opens it in a new tab. A real
partner links the CRM's own page for the record. There is no CRM here, so the URL is this page:
clearly labelled fake, and showing only the Dialpad contact id it was linked for.

The page takes no token and shows nothing private: Dialpad opens it as a plain browser tab, without
the panel's bearer token, so anyone with the URL sees the same thing.
"""

from html import escape
from typing import TYPE_CHECKING
from urllib.parse import quote

from sanic import HTTPResponse
from sanic import Request

from acme_dialpad_rightbar.pages import RenderedPage
from acme_dialpad_rightbar.pages import generate_nonce
from acme_dialpad_rightbar.responses import rendered

if TYPE_CHECKING:
  from acme_dialpad_rightbar.context import App
  from acme_dialpad_rightbar.context import AppContext

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="referrer" content="no-referrer">
<title>Fake CRM record: Acme for Dialpad (demo)</title>
<style nonce="{nonce}">
  body {{ font-family: system-ui, sans-serif; max-width: 26rem; margin: 3rem auto; padding: 0 1rem;
         line-height: 1.5; }}
  .banner {{ background: #fff3cd; color: #664d03; border: 1px solid #ffda6a; border-radius: .5rem;
            padding: .5rem .75rem; font-weight: 600; }}
  @media (prefers-color-scheme: dark) {{
    .banner {{ background: #332701; color: #ffda6a; border-color: #664d03; }}
  }}
</style>
</head>
<body>
<p class="banner" role="note">This is a fake CRM record (demo only)</p>
<h1>Acme contact</h1>
<p>Dialpad contact id: <code>{contact_id}</code></p>
<p>A real app links its CRM's page for the record mapped to this contact. There is no Acme CRM, so
the demo links this page instead.</p>
</body>
</html>
"""


def record_url(base_url: str, contact_id: str) -> str:
  """Return the absolute URL of the fake CRM record page for this Dialpad contact id.

  The iframe panel links it with the SDK's ``linkRecord``, so Dialpad's View button opens it. The id
  is percent-encoded, so it stays one path segment whatever it contains.
  """
  return f'{base_url}/records/{quote(contact_id, safe="")}'


def register(app: App, _ctx: AppContext) -> None:
  """Register ``GET /records/<contact id>``."""
  @app.get('/records/<contact_id:str>', unquote=True)
  async def fake_record(_request: Request, contact_id: str) -> HTTPResponse:
    """Show the fake CRM record page for this Dialpad contact id.

    Invoked when the user presses Dialpad's View button. It takes no token and shows only the id
    from the URL, escaped; nothing is looked up or recorded.
    """
    return rendered(render_fake_record_page(contact_id=contact_id, nonce=generate_nonce()))


def render_fake_record_page(*, contact_id: str, nonce: str) -> RenderedPage:
  """Render the fake CRM record page for one Dialpad contact id.

  The id comes from the URL, so it is HTML-escaped. The headers lock the page down (no scripts, no
  framing, no referrer); the inline style is allowed by ``nonce`` only.
  """
  html = _TEMPLATE.format(nonce=escape(nonce), contact_id=escape(contact_id))
  csp = '; '.join([
      "default-src 'none'",
      f"style-src 'nonce-{nonce}'",
      "frame-ancestors 'none'",
      "base-uri 'none'",
  ])
  headers = {
      'Content-Security-Policy': csp,
      'Referrer-Policy': 'no-referrer',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
  }
  return RenderedPage(html=html, headers=headers)
