"""Settings (``settings.py``): validation at startup and the defaults local mode fills in."""

import pytest

from acme_dialpad_rightbar.dialpad.idtoken import TEST_CLIENT_SECRET
from acme_dialpad_rightbar.settings import ConfigurationError
from acme_dialpad_rightbar.settings import Settings
from acme_dialpad_rightbar.settings import listen_port
from acme_dialpad_rightbar.settings import settings_from_env
from tests.conftest import DIALPAD_ORIGIN


def test_a_client_secret_shorter_than_48_characters_is_rejected() -> None:
  with pytest.raises(ConfigurationError):
    Settings(client_secret='short', app_secret='x', dialpad_origin=DIALPAD_ORIGIN, base_url='x')


@pytest.mark.parametrize(
    ('origin', 'valid'),
    [
        ('https://dialpad.com', True),
        ('http://localhost:5173', True),
        ('http://[::1]:5173', True),
        ('https://dialpad.com/', False),
        ('dialpad.com', False),
        ('ftp://dialpad.com', False),
        ('https://dialpad.com; script-src *', False),
        ('https://dialpad.com?x=1', False),
        ('', False),
    ],
)
def test_only_a_bare_dialpad_origin_is_accepted_at_startup(origin: str,
                                                           valid: bool) -> None: # noqa: FBT001
  def build() -> Settings:
    return Settings(
        client_secret=TEST_CLIENT_SECRET,
        app_secret='x',
        dialpad_origin=origin,
        base_url='https://acme.example.com',
    )

  if valid:
    assert build().dialpad_origin == origin
  else:
    with pytest.raises(ConfigurationError, match='DIALPAD_ORIGIN'):
      build()


def test_settings_require_every_value_outside_local_mode() -> None:
  with pytest.raises(ConfigurationError):
    settings_from_env({})


def test_the_port_is_port_then_the_base_urls_port_then_8000() -> None:
  assert listen_port('http://localhost:8000', {'PORT': '8080'}) == 8080
  assert listen_port('https://acme.example.com', {'PORT': '8080'}) == 8080
  assert listen_port('http://localhost:9000', {}) == 9000
  assert listen_port('https://acme.example.com', {}) == 8000


def test_the_server_listens_on_this_machine_only_unless_host_says_otherwise() -> None:
  required = {
      'DIALPAD_CLIENT_SECRET': TEST_CLIENT_SECRET,
      'APP_SECRET': 'x',
      'DIALPAD_ORIGIN': DIALPAD_ORIGIN,
      'BASE_URL': 'https://acme.example.com',
  }

  for env in ({'LOCAL_MODE': '1'}, required):
    assert settings_from_env(env).host == '127.0.0.1'
    assert settings_from_env({**env, 'HOST': '0.0.0.0'}).host == '0.0.0.0' # noqa: S104


def test_local_mode_comes_from_configuration_and_fills_in_defaults() -> None:
  settings = settings_from_env({'LOCAL_MODE': '1'})

  assert settings.local_mode is True
  assert settings.client_secret == TEST_CLIENT_SECRET
  assert settings.dialpad_origin == 'http://localhost:5173'
  assert settings.vite_websocket_origin == 'ws://localhost:5173'
