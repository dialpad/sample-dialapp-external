"""Settings: validation at startup and the defaults local mode fills in (backend/settings.py)."""

import pytest
from dialpad_dialapp_toolkit.testing import TEST_CLIENT_SECRET

from backend.settings import ConfigurationError
from backend.settings import Settings
from backend.settings import settings_from_env
from tests.conftest import DIALPAD_ORIGIN


def test_a_client_secret_shorter_than_48_characters_is_rejected() -> None:
  with pytest.raises(ConfigurationError):
    Settings(client_secret='short', app_secret='x', dialpad_origin=DIALPAD_ORIGIN, base_url='x')


@pytest.mark.parametrize(
    'origin',
    [
        'https://dialpadbeta.com/',
        'https://dialpadbeta.com/path',
        'dialpadbeta.com',
        'ftp://dialpadbeta.com',
        'https://dialpadbeta.com; script-src *',
        ' https://dialpadbeta.com',
        'https://dialpadbeta.com?x=1',
        '',
    ],
)
def test_a_dialpad_origin_that_is_not_a_bare_origin_is_rejected_at_startup(origin: str) -> None:
  with pytest.raises(ConfigurationError, match='DIALPAD_ORIGIN'):
    Settings(
        client_secret=TEST_CLIENT_SECRET,
        app_secret='x',
        dialpad_origin=origin,
        base_url='https://acme.example.com',
    )


@pytest.mark.parametrize(
    'origin',
    [
        'https://dialpadbeta.com', 'https://dialpad.com', 'http://localhost:5173',
        'http://[::1]:5173'
    ],
)
def test_a_bare_dialpad_origin_is_accepted(origin: str) -> None:
  settings = Settings(
      client_secret=TEST_CLIENT_SECRET,
      app_secret='x',
      dialpad_origin=origin,
      base_url='https://acme.example.com',
  )

  assert settings.dialpad_origin == origin


def test_settings_require_every_value_outside_local_mode() -> None:
  with pytest.raises(ConfigurationError):
    settings_from_env({})


def test_local_mode_comes_from_configuration_and_fills_in_defaults() -> None:
  settings = settings_from_env({'LOCAL_MODE': '1'})

  assert settings.local_mode is True
  assert settings.client_secret == TEST_CLIENT_SECRET
  assert settings.dialpad_origin == 'http://localhost:5173'
  assert settings.vite_websocket_origin == 'ws://localhost:5173'
