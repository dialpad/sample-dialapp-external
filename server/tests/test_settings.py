"""Settings (``settings.py``): validation at startup and the defaults local mode fills in."""

import pytest

from acme_dialpad_rightbar.idtoken import TEST_CLIENT_SECRET
from acme_dialpad_rightbar.settings import ConfigurationError
from acme_dialpad_rightbar.settings import Settings
from acme_dialpad_rightbar.settings import listen_port
from acme_dialpad_rightbar.settings import settings_from_env
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


def test_an_explicit_port_wins_over_the_port_in_the_base_url() -> None:
  assert listen_port('http://localhost:8000', {'PORT': '8080'}) == 8080
  assert listen_port('https://acme.example.com', {'PORT': '8080'}) == 8080


def test_the_port_falls_back_to_the_base_url_then_to_8000() -> None:
  assert listen_port('http://localhost:9000', {}) == 9000
  assert listen_port('https://acme.example.com', {}) == 8000


def test_the_server_listens_on_this_machine_only_unless_host_says_otherwise() -> None:
  assert settings_from_env({'LOCAL_MODE': '1'}).host == '127.0.0.1'
  assert settings_from_env({'LOCAL_MODE': '1', 'HOST': '0.0.0.0'}).host == '0.0.0.0' # noqa: S104


def test_host_applies_outside_local_mode_too() -> None:
  required = {
      'DIALPAD_CLIENT_SECRET': TEST_CLIENT_SECRET,
      'APP_SECRET': 'x',
      'DIALPAD_ORIGIN': DIALPAD_ORIGIN,
      'BASE_URL': 'https://acme.example.com',
  }

  assert settings_from_env(required).host == '127.0.0.1'
  assert settings_from_env({**required, 'HOST': '0.0.0.0'}).host == '0.0.0.0' # noqa: S104


def test_local_mode_comes_from_configuration_and_fills_in_defaults() -> None:
  settings = settings_from_env({'LOCAL_MODE': '1'})

  assert settings.local_mode is True
  assert settings.client_secret == TEST_CLIENT_SECRET
  assert settings.dialpad_origin == 'http://localhost:5173'
  assert settings.vite_websocket_origin == 'ws://localhost:5173'
