"""Asset tags from a Vite manifest (backend/assets.py)."""

import pytest

from backend.assets import PageAssets


def test_vite_manifest_entry_collects_script_css_and_origin() -> None:
  manifest = {
      'src/main.ts': {
          'file': 'assets/main-abc.js',
          'css': ['assets/main-abc.css'],
          'imports': ['_vendor.js'],
          'isEntry': True,
      },
      '_vendor.js': {
          'file': 'assets/vendor-def.js',
          'css': ['assets/vendor-def.css'],
      },
  }

  assets = PageAssets.from_vite_manifest(manifest, 'src/main.ts', 'https://cdn.example.com/app')

  assert assets.scripts == ('https://cdn.example.com/app/assets/main-abc.js',)
  assert assets.styles == (
      'https://cdn.example.com/app/assets/vendor-def.css',
      'https://cdn.example.com/app/assets/main-abc.css',
  )
  assert assets.origins == ('https://cdn.example.com',)


def test_vite_manifest_same_origin_needs_no_extra_origin() -> None:
  manifest = {'src/main.ts': {'file': 'assets/main.js'}}

  assets = PageAssets.from_vite_manifest(manifest, 'src/main.ts', '/static/')

  assert assets.scripts == ('/static/assets/main.js',)
  assert assets.origins == ()


def test_vite_manifest_unknown_entry_is_an_error() -> None:
  with pytest.raises(KeyError, match=r'missing\.ts'):
    PageAssets.from_vite_manifest({}, 'missing.ts')
