"""The page's script and style tags: Vite's dev server in local mode, the built bundle otherwise.

The toolkit renders the page; this module only tells it which assets to link and which origins
the Content-Security-Policy must allow them from.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING

from dialpad_dialapp_toolkit import PageAssets

if TYPE_CHECKING:
  from backend.settings import Settings

# The frontend's entry module, as Vite names it in its manifest and in the dev server's URLs.
ENTRY = 'src/main.ts'


def build_assets(settings: Settings) -> PageAssets:
  """Return the script and style tags for the panel's entry module.

  Called once at startup. In local mode the scripts are served by the Vite dev server (with hot
  reload) from its own origin. Otherwise they come from the build in ``dist/``: the hashed file
  names are read from Vite's manifest and served by this backend under ``/assets``. Raises
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
