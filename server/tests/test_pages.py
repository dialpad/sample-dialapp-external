"""The app's own pages (``pages.py``): iframe panel page, close popup and error page."""

import json
import re
from html.parser import HTMLParser
from typing import Any
from typing import cast
from typing import override

import pytest

from acme_dialpad_rightbar.assets import PageAssets
from acme_dialpad_rightbar.connect.close_popup import render_close_popup
from acme_dialpad_rightbar.dialpad.contract import ErrorResponse
from acme_dialpad_rightbar.dialpad.contract import ExternalConnection
from acme_dialpad_rightbar.dialpad.contract import PageData
from acme_dialpad_rightbar.dialpad.panel_page import PageOptions
from acme_dialpad_rightbar.dialpad.panel_page import render_page
from acme_dialpad_rightbar.pages import render_error_page

NONCE = 'test-nonce-123'
ASSETS = PageAssets(scripts=('/static/app.js',), styles=('/static/app.css',))


class _Scripts(HTMLParser):
  """Collect every ``<script>`` element's attributes and text."""
  def __init__(self) -> None:
    super().__init__()
    self.scripts: list[tuple[dict[str, str | None], str]] = []
    self._current: dict[str, str | None] | None = None
    self._text: list[str] = []

  @override
  def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    if tag == 'script':
      self._current = dict(attrs)
      self._text = []

  @override
  def handle_data(self, data: str) -> None:
    if self._current is not None:
      self._text.append(data)

  @override
  def handle_endtag(self, tag: str) -> None:
    if tag == 'script' and self._current is not None:
      self.scripts.append((self._current, ''.join(self._text)))
      self._current = None


def _scripts(html: str) -> list[tuple[dict[str, str | None], str]]:
  parser = _Scripts()
  parser.feed(html)
  return parser.scripts


def _page_data_json(html: str) -> dict[str, object]:
  [text] = [text for attrs, text in _scripts(html) if attrs.get('id') == 'dialpad-page-data']
  data = json.loads(text)
  assert isinstance(data, dict)
  return cast('dict[str, object]', data)


def make_page_data(**overrides: Any) -> PageData: # noqa: ANN401
  """Return valid page data: not connected, with one authorization URL; fields overridable."""
  values: dict[str, Any] = {
      'dialpad_origin': 'https://dialpad.com',
      'access_token': 'an-access-token',
      'external_connection': ExternalConnection(
          connected=False,
          authorization_urls={'acme-for-dialpad': 'https://acme.example.com/oauth'},
          name='acme-for-dialpad',
      ),
  }
  values.update(overrides)
  return PageData.model_validate(values)


# The iframe panel page: nothing sensitive in it, and page data can't break out of its element


def test_hostile_page_data_stays_inside_its_element_and_round_trips() -> None:
  hostile = '</script><script>alert(1)</script><!-- ' + chr(0x2028) + ' & \' "'
  page_data = make_page_data(
      external_connection={
          'connected': False,
          'authorization_urls': {
              hostile: 'https://partner.example.com/oauth'
          },
          'name': hostile,
      },
      app={'note': hostile},
  )

  page = render_page(page_data, nonce=NONCE, assets=ASSETS)

  assert '</script><script>alert(1)' not in page.html
  assert '<!--' not in page.html
  scripts = _scripts(page.html)
  assert [attrs.get('id') for attrs, _ in scripts] == ['dialpad-page-data', None]
  data = _page_data_json(page.html)
  assert data['app'] == {'note': hostile}
  assert data == {'version': 1, **page_data.model_dump(mode='json')}


def test_page_data_is_a_versioned_json_element_and_every_script_carries_the_nonce() -> None:
  assets = PageAssets(scripts=('/static/a.js', 'https://cdn.example.com/b.js'))

  page = render_page(make_page_data(), nonce=NONCE, assets=assets)

  scripts = _scripts(page.html)
  [(data_attrs, _)] = [script for script in scripts if 'id' in script[0]]
  assert data_attrs == {'type': 'application/json', 'id': 'dialpad-page-data', 'nonce': NONCE}
  assert _page_data_json(page.html)['version'] == 1
  assert all(attrs.get('nonce') == NONCE for attrs, _ in scripts)
  assert [attrs.get('type') for attrs, _ in scripts] == ['application/json', 'module', 'module']
  # ...and nowhere else on the page.
  assert len(re.findall(re.escape(NONCE), page.html)) == len(scripts)


def test_page_headers_match_the_contract_and_asset_origins_join_the_policy() -> None:
  page = render_page(make_page_data(dialpad_origin='https://dialpadbeta.com'),
                     nonce=NONCE,
                     assets=ASSETS)

  csp = page.headers['Content-Security-Policy']
  assert 'frame-ancestors https://dialpadbeta.com' in csp.split('; ')
  assert f"script-src 'self' 'nonce-{NONCE}'" in csp.split('; ')
  assert "object-src 'none'" in csp.split('; ')
  assert "base-uri 'none'" in csp.split('; ')
  assert 'connect-src' not in csp
  assert "'unsafe-inline'" not in csp
  assert "'unsafe-eval'" not in csp
  assert page.headers['Referrer-Policy'] == 'no-referrer'
  assert page.headers['Cache-Control'] == 'no-store'
  assert page.headers['X-Content-Type-Options'] == 'nosniff'
  assert page.status == 200

  # Another origin, an asset host and an extra connect source (what local mode adds).
  local = render_page(
      make_page_data(dialpad_origin='http://localhost:5174'),
      nonce=NONCE,
      assets=PageAssets(
          scripts=('http://localhost:5173/@vite/client', 'http://localhost:5173/src/main.ts'),
          origins=('http://localhost:5173',),
      ),
      options=PageOptions(extra_connect_src=('ws://localhost:5173',)),
  )
  directives = local.headers['Content-Security-Policy'].split('; ')
  assert 'frame-ancestors http://localhost:5174' in directives
  assert f"script-src 'self' 'nonce-{NONCE}' http://localhost:5173" in directives
  assert "connect-src 'self' ws://localhost:5173" in directives


def test_styles_title_and_mount_element_are_rendered_and_escaped() -> None:
  assets = PageAssets(scripts=('/a.js?x="1"&y=2',), styles=('/static/app.css',))

  page = render_page(
      make_page_data(),
      nonce=NONCE,
      assets=assets,
      options=PageOptions(title='Acme <CRM>'),
  )

  assert '<link rel="stylesheet" href="/static/app.css">' in page.html
  assert '<div id="app"></div>' in page.html
  assert '<title>Acme &lt;CRM&gt;</title>' in page.html
  assert 'src="/a.js?x=&quot;1&quot;&amp;y=2"' in page.html


# The error page


def test_error_page_is_minimal_framable_and_escapes_its_code_and_message() -> None:
  error = ErrorResponse(code='<b>oops</b>', message='<b>Open this panel from Dialpad</b>')

  page = render_error_page(error, status=401, dialpad_origin='https://dialpad.com')

  assert page.status == 401
  assert _scripts(page.html) == []
  assert '<b>' not in page.html
  assert '<p>&lt;b&gt;Open this panel from Dialpad&lt;/b&gt;</p>' in page.html
  assert '<small>&lt;b&gt;oops&lt;/b&gt;</small>' in page.html
  directives = page.headers['Content-Security-Policy'].split('; ')
  assert "default-src 'none'" in directives
  assert 'frame-ancestors https://dialpad.com' in directives
  assert page.headers['Referrer-Policy'] == 'no-referrer'
  assert page.headers['Cache-Control'] == 'no-store'
  assert "'unsafe-inline'" not in page.headers['Content-Security-Policy']
  nonce = re.search(r"style-src 'nonce-([^']+)'", page.headers['Content-Security-Policy'])
  assert nonce is not None
  assert f'<style nonce="{nonce.group(1)}">' in page.html


_RENDERERS = {
    'page': lambda origin: render_page(
        make_page_data(dialpad_origin=origin), nonce=NONCE, assets=ASSETS),
    'close popup': lambda origin: render_close_popup(origin, nonce=NONCE),
    'error page': lambda origin: render_error_page(
        ErrorResponse(code='invalid_idtoken', message='x'), status=401, dialpad_origin=origin),
}


@pytest.mark.parametrize('renderer', list(_RENDERERS))
@pytest.mark.parametrize(
    'origin',
    [
        'https://evil.example/</script><script>alert(1)//',
        'https://dialpad.com/',
        'https://dialpad.com; script-src *',
        '',
    ],
)
def test_renderers_refuse_anything_but_an_origin(renderer: str, origin: str) -> None:
  with pytest.raises(ValueError, match='expected an origin'):
    _RENDERERS[renderer](origin)


# The close-popup page


def test_close_popup_posts_to_the_dialpad_origin_only_with_an_opener_then_closes() -> None:
  page = render_close_popup('https://dialpadbeta.com', nonce=NONCE)

  calls = re.findall(r'postMessage\(([^)]*)\)', page.html)
  assert calls == ["'close_popup', dialpadOrigin"]
  assert 'const dialpadOrigin = "https://dialpadbeta.com";' in page.html
  assert "'*'" not in page.html
  assert '"*"' not in page.html
  script = page.html[page.html.index('<script'):page.html.index('</script>')]
  call = 'window.opener.postMessage('
  assert script.index('if (window.opener)') < script.index(call)
  assert script.index(call) < script.index('window.close()')
  assert 'You can close this window.' in page.html


def test_close_popup_is_locked_down_with_a_nonce_for_its_one_script_and_style() -> None:
  page = render_close_popup('https://dialpad.com', nonce=NONCE)

  assert re.findall(r'<script\b[^>]*>', page.html) == [f'<script nonce="{NONCE}">']
  assert re.findall(r'<style\b[^>]*>', page.html) == [f'<style nonce="{NONCE}">']
  csp = page.headers['Content-Security-Policy']
  directives = csp.split('; ')
  assert "default-src 'none'" in directives
  assert f"script-src 'nonce-{NONCE}'" in directives
  assert f"style-src 'nonce-{NONCE}'" in directives
  assert "frame-ancestors 'none'" in directives
  assert "'unsafe-inline'" not in csp
  assert page.headers['Referrer-Policy'] == 'no-referrer'
  assert page.headers['Cache-Control'] == 'no-store'
