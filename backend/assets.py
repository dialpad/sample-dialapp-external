"""The page's script and style tags: Vite's dev server in local mode, the built bundle otherwise."""

import json
from pathlib import Path
from typing import TYPE_CHECKING

from dialpad_dialapp_toolkit import PageAssets

if TYPE_CHECKING:
  from backend.settings import Settings

ENTRY = 'src/main.ts'


def build_assets(settings: Settings) -> PageAssets:
  """Return the asset tags for the panel's entry module."""
  if settings.local_mode:
    origin = settings.vite_origin
    return PageAssets(scripts=(f'{origin}/@vite/client', f'{origin}/{ENTRY}'), origins=(origin,))
  manifest_path = Path(settings.dist_dir) / '.vite' / 'manifest.json'
  if not manifest_path.is_file():
    message = f'{manifest_path} not found; run `pnpm build` first'
    raise FileNotFoundError(message)
  manifest = json.loads(manifest_path.read_text())
  return PageAssets.from_vite_manifest(manifest, ENTRY, base_url='/')
