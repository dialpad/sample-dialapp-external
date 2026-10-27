"""The fake OAuth screen: the page that stands in for a real CRM's sign-in and consent screen.

A real CRM would ask the user to sign in and approve the app's access. This one is a single page
with an Authorize button, clearly labelled as fake, so the popup stays open long enough to see the
"connecting" state in the iframe panel. Pressing the button sends the user to the OAuth callback
with the ``state`` and a fixed ``code``, exactly where a real CRM's redirect would end up.
"""

from html import escape
from typing import TYPE_CHECKING

from acme_dialpad_rightbar.pages import RenderedPage

if TYPE_CHECKING:
  from collections.abc import Sequence

# The fixed authorization code the fake OAuth round trip hands back; a real CRM issues a one-time
# code that the callback exchanges for tokens.
FAKE_CODE = 'fake-code'

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Fake OAuth: authorize Acme for Dialpad (demo)</title>
<style nonce="{nonce}">
  body {{ font-family: system-ui, sans-serif; max-width: 26rem; margin: 3rem auto; padding: 0 1rem;
         line-height: 1.5; }}
  .banner {{ background: #fff3cd; color: #664d03; border: 1px solid #ffda6a; border-radius: .5rem;
            padding: .5rem .75rem; font-weight: 600; }}
  button {{ font: inherit; padding: .5rem 1.25rem; border: 0; border-radius: .5rem;
           background: #6f42c1; color: #fff; cursor: pointer; }}
  @media (prefers-color-scheme: dark) {{
    .banner {{ background: #332701; color: #ffda6a; border-color: #664d03; }}
  }}
</style>
</head>
<body>
<p class="banner" role="note">This is a fake OAuth page (demo only)</p>
<h1>Authorize Acme for Dialpad</h1>
<p>This stands in for a real CRM's sign-in and consent screen. There is no real Acme account, and
nothing here asks for a password.</p>
<p>Authorizing connects your Dialpad user to the Acme for Dialpad demo panel.
Scopes requested: {scopes}.</p>
<form method="get" action="{action}">
<input type="hidden" name="state" value="{state}">
<input type="hidden" name="code" value="{code}">
<button type="submit">Authorize</button>
</form>
</body>
</html>
"""


def render_fake_authorize_page(
    *,
    callback_url: str,
    state: str,
    code: str,
    scopes: Sequence[str],
    nonce: str,
) -> RenderedPage:
  """Render the fake authorize screen for one OAuth round trip.

  Shown in the popup (or the desktop app's login window) when the user clicks Connect, instead of
  redirecting straight on. Nothing is recorded here and no cookie is set: the page only carries the
  ``state`` to the callback when the user presses Authorize, which is a plain GET of
  ``callback_url?state=...&code=...``. Every value is HTML-escaped, since ``state`` comes from the
  URL. The headers lock the page down (no scripts, forms may only submit to this origin, no
  framing); the inline style is allowed by ``nonce`` only.
  """
  html = _TEMPLATE.format(
      nonce=escape(nonce),
      action=escape(callback_url),
      state=escape(state),
      code=escape(code),
      scopes=escape(', '.join(scopes)),
  )
  csp = '; '.join([
      "default-src 'none'",
      f"style-src 'nonce-{nonce}'",
      "form-action 'self'",
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
