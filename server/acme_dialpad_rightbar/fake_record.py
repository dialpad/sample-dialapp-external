"""The fake CRM record: the page Dialpad's "View Contact" button opens for a linked contact.

Once the iframe panel has looked a contact up, it calls the SDK's ``linkRecord`` with a URL, and
Dialpad shows a "View Contact" button that opens it in a new tab. A real partner links the CRM's own
page for the record. There is no CRM here, so the URL is this page: clearly labelled fake, and
showing only the Dialpad contact id it was linked for.

The page takes no token and shows nothing private: Dialpad opens it as a plain browser tab, without
the panel's bearer token, so anyone with the URL sees the same thing.
"""

from html import escape

from acme_dialpad_rightbar.pages import RenderedPage

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
