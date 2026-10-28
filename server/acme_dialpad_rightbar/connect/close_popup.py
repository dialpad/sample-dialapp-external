"""The page the OAuth callback returns: it tells Dialpad Connect finished, and closes the popup."""

from html import escape

from acme_dialpad_rightbar.pages import RenderedPage
from acme_dialpad_rightbar.pages import build_csp
from acme_dialpad_rightbar.pages import common_headers
from acme_dialpad_rightbar.pages import json_for_script
from acme_dialpad_rightbar.pages import require_origin

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
      dialpad_origin=json_for_script(require_origin(dialpad_origin)),
      nonce=escape(nonce),
  )
  csp = build_csp([
      ('default-src', ["'none'"]),
      ('script-src', [f"'nonce-{nonce}'"]),
      ('style-src', [f"'nonce-{nonce}'"]),
      ('frame-ancestors', ["'none'"]),
      ('base-uri', ["'none'"]),
  ])
  return RenderedPage(html=html, headers=common_headers(csp))
