"""Configuration, read from the environment. Secrets never appear in logs or responses."""

import os
from dataclasses import dataclass
from dataclasses import field

from dialpad_dialapp_toolkit.testing import TEST_CLIENT_SECRET

# Local mode defaults: the dev page (served by Vite) frames this backend.
MIN_CLIENT_SECRET_LENGTH = 48
DEFAULT_LOCAL_BASE_URL = 'http://localhost:8000'
DEFAULT_LOCAL_DEV_PAGE_ORIGIN = 'http://localhost:5173'
DEFAULT_LOCAL_APP_SECRET = 'local-mode-app-secret-not-for-production' # noqa: S105


class ConfigurationError(Exception):
  """A required setting is missing."""


@dataclass(frozen=True)
class Settings:
  """Everything the backend needs to know about its environment.

  ``local_mode`` is configuration only; no request can switch it on. In local mode the dev page,
  not Dialpad, frames the app, so ``dialpad_origin`` is the dev page's origin and the page's
  Content-Security-Policy gains the Vite dev server's origins.
  """

  client_secret: str = field(repr=False)
  app_secret: str = field(repr=False)
  dialpad_origin: str
  base_url: str
  local_mode: bool = False
  vite_origin: str = DEFAULT_LOCAL_DEV_PAGE_ORIGIN
  # Where the built frontend lives, for non-local mode (a Vite manifest is read from here).
  dist_dir: str = 'dist'

  def __post_init__(self) -> None:
    """Reject a client secret too short to key the idtoken's JWE (Dialpad's are 50 characters)."""
    if len(self.client_secret) < MIN_CLIENT_SECRET_LENGTH:
      message = f'DIALPAD_CLIENT_SECRET must be at least {MIN_CLIENT_SECRET_LENGTH} characters'
      raise ConfigurationError(message)

  @property
  def vite_websocket_origin(self) -> str:
    """The Vite dev server's websocket origin, for hot reload."""
    return self.vite_origin.replace('http://', 'ws://', 1).replace('https://', 'wss://', 1)

  @property
  def authorize_url(self) -> str:
    """The fake authorize endpoint's absolute URL, without a ``state``."""
    return f'{self.base_url}/oauth/fake-authorize'

  @property
  def callback_url(self) -> str:
    """The fake callback endpoint's absolute URL."""
    return f'{self.base_url}/oauth/callback'


def _required(env: dict[str, str], name: str) -> str:
  value = env.get(name)
  if not value:
    message = f'{name} is required'
    raise ConfigurationError(message)
  return value


def settings_from_env(env: dict[str, str] | None = None) -> Settings:
  """Build settings from ``env`` (default: the process environment).

  ``LOCAL_MODE=1`` fills in every value a local run needs, including the toolkit's test client
  secret, which is also what the dev page signs its mock idtoken with. Outside local mode the
  client secret, app secret, Dialpad origin and base URL are all required.
  """
  env = dict(os.environ) if env is None else env
  if env.get('LOCAL_MODE') == '1':
    vite_origin = env.get('VITE_ORIGIN', DEFAULT_LOCAL_DEV_PAGE_ORIGIN)
    return Settings(
        client_secret=env.get('DIALPAD_CLIENT_SECRET', TEST_CLIENT_SECRET),
        app_secret=env.get('APP_SECRET', DEFAULT_LOCAL_APP_SECRET),
        dialpad_origin=env.get('DIALPAD_ORIGIN', vite_origin),
        base_url=env.get('BASE_URL', DEFAULT_LOCAL_BASE_URL),
        local_mode=True,
        vite_origin=vite_origin,
    )
  return Settings(
      client_secret=_required(env, 'DIALPAD_CLIENT_SECRET'),
      app_secret=_required(env, 'APP_SECRET'),
      dialpad_origin=_required(env, 'DIALPAD_ORIGIN'),
      base_url=_required(env, 'BASE_URL').rstrip('/'),
      dist_dir=env.get('DIST_DIR', 'dist'),
  )
