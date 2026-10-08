"""The page's script and style tags: Vite's dev server in local mode, the built bundle otherwise.

``PageAssets`` is what ``pages.render_page`` links, and the origins its Content-Security-Policy must
allow them from; ``build_assets`` decides which assets those are.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import urljoin
from urllib.parse import urlsplit

if TYPE_CHECKING:
  from collections.abc import Mapping
  from collections.abc import Sequence

  from acme_dialpad_rightbar.settings import Settings

# The frontend's entry module, as Vite names it in its manifest and in the dev server's URLs.
ENTRY = 'src/main.ts'


def _origin_of(url: str) -> str | None:
  """Return ``url``'s origin, or ``None`` for a relative URL."""
  parts = urlsplit(url)
  if not parts.scheme or not parts.netloc:
    return None
  return f'{parts.scheme}://{parts.netloc}'


@dataclass(frozen=True)
class PageAssets:
  """The app's script and style URLs, and the origins they're served from.

  Scripts are loaded as ES modules. ``origins`` are added to ``script-src`` (for assets on a CDN or
  a local Vite dev server); same-origin assets need none.
  """

  scripts: Sequence[str] = ()
  styles: Sequence[str] = ()
  origins: Sequence[str] = ()

  @classmethod
  def from_vite_manifest(
      cls,
      manifest: Mapping[str, Any],
      entry: str,
      base_url: str = '/',
  ) -> PageAssets:
    """Asset tags for one entry of a Vite build manifest (``.vite/manifest.json``).

    ``base_url`` is where the build output is served, for example ``/static/`` or a CDN URL. The
    entry's own CSS and the CSS of every chunk it imports are included, in import order. A
    ``base_url`` on another origin adds that origin to ``origins``. Raises ``KeyError`` when
    ``entry`` is not in the manifest.
    """
    if entry not in manifest:
      msg = f'{entry!r} is not in the Vite manifest'
      raise KeyError(msg)

    base = base_url if base_url.endswith('/') else f'{base_url}/'
    styles: list[str] = []
    seen: set[str] = set()

    def collect_css(key: str) -> None:
      if key in seen:
        return
      seen.add(key)
      chunk = manifest[key]
      for imported in chunk.get('imports', []):
        collect_css(imported)
      styles.extend(urljoin(base, css) for css in chunk.get('css', []))

    collect_css(entry)
    origin = _origin_of(base)
    return cls(
        scripts=(urljoin(base, manifest[entry]['file']),),
        styles=tuple(dict.fromkeys(styles)),
        origins=(origin,) if origin is not None else (),
    )


def build_assets(settings: Settings) -> PageAssets:
  """Return the script and style tags for the iframe panel's entry module.

  Called once at startup. In local mode the scripts are served by the Vite dev server (with hot
  reload) from its own origin. Otherwise they come from the build in ``client/dist/``: the hashed
  file names are read from Vite's manifest and served by this server under ``/assets``. Raises
  ``FileNotFoundError`` if the build is missing, so a forgotten ``pnpm build`` stops startup.
  """
  if settings.local_mode:
    origin = settings.vite_origin
    return PageAssets(scripts=(f'{origin}/@vite/client', f'{origin}/{ENTRY}'), origins=(origin,))
  manifest_path = Path(settings.dist_dir) / '.vite' / 'manifest.json'
  if not manifest_path.is_file():
    message = f'{manifest_path} not found; run `pnpm build` first'
    raise FileNotFoundError(message)
  manifest = json.loads(manifest_path.read_text())
  return PageAssets.from_vite_manifest(manifest, ENTRY, base_url='/')
