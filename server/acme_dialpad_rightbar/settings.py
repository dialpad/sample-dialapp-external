"""Configuration, read from the environment. Secrets never appear in logs or responses.

``settings_from_env`` is the only entry point: ``python -m acme_dialpad_rightbar`` calls it once at
startup, and a bad value stops the process there with a ``ConfigurationError`` rather than failing
on a request.
"""

import os
from dataclasses import dataclass
from dataclasses import field
from urllib.parse import urlsplit

from acme_dialpad_rightbar.idtoken import TEST_CLIENT_SECRET

# The idtoken's JWE is keyed with the first 48 characters of the client secret; Dialpad's secrets
# are 50 characters.
MIN_CLIENT_SECRET_LENGTH = 48
# Local mode defaults: the dev host (served by Vite) frames this server.
# Where the server listens unless HOST says otherwise: this machine only, so a local run can't be
# reached from the network.
DEFAULT_HOST = '127.0.0.1'
# The port used when neither PORT nor BASE_URL names one.
DEFAULT_PORT = 8000
DEFAULT_LOCAL_BASE_URL = 'http://localhost:8000'
DEFAULT_LOCAL_DEV_PAGE_ORIGIN = 'http://localhost:5173'
DEFAULT_LOCAL_APP_SECRET = 'local-mode-app-secret-not-for-production' # noqa: S105
# Where the built iframe panel is, relative to the server/ folder the server runs from; a container
# sets DIST_DIR to wherever its image keeps it.
DEFAULT_DIST_DIR = '../client/dist'


class ConfigurationError(Exception):
  """A setting is missing or invalid; raised at startup, before the server listens."""


def _is_bare_origin(value: str) -> bool:
  """Whether ``value`` is exactly ``scheme://host[:port]``: no path, query, spaces or ``;``.

  The Dialpad origin goes into the page's Content-Security-Policy header, where a stray ``;`` or
  space would add directives, so it is checked at startup (``acme_dialpad_rightbar.pages`` refuses
  it at render time too). A trailing slash, the likeliest typo, fails the exact comparison.
  """
  if ';' in value or any(char.isspace() for char in value):
    return False
  parts = urlsplit(value)
  return parts.scheme in {'http', 'https'} and f'{parts.scheme}://{parts.netloc}' == value


@dataclass(frozen=True)
class Settings:
  """Everything the server needs to know about its environment, immutable once built.

  ``local_mode`` is configuration only; no request can switch it on. In local mode the dev host,
  not Dialpad, frames the app, so ``dialpad_origin`` is the dev host's origin and the page's
  Content-Security-Policy gains the Vite dev server's origins. The two secrets are left out of
  ``repr`` so they can't leak into a log line or a traceback.
  """

  client_secret: str = field(repr=False)
  app_secret: str = field(repr=False)
  dialpad_origin: str
  base_url: str
  local_mode: bool = False
  vite_origin: str = DEFAULT_LOCAL_DEV_PAGE_ORIGIN
  # Where the built iframe panel (client/'s `pnpm build`) lives, for non-local mode; a Vite manifest
  # is read from here.
  dist_dir: str = DEFAULT_DIST_DIR
  # The address the server listens on. Containers (Cloud Run, Docker) need '0.0.0.0'.
  host: str = DEFAULT_HOST

  def __post_init__(self) -> None:
    """Reject a bad Dialpad origin or client secret as soon as the settings are built.

    That is at startup, so a typo in an environment variable surfaces as a clear message instead
    of a 500 on the first page load.
    """
    if not _is_bare_origin(self.dialpad_origin):
      message = ('DIALPAD_ORIGIN must be a bare origin such as https://dialpadbeta.com, '
                 f'got {self.dialpad_origin!r}')
      raise ConfigurationError(message)
    if len(self.client_secret) < MIN_CLIENT_SECRET_LENGTH:
      message = f'DIALPAD_CLIENT_SECRET must be at least {MIN_CLIENT_SECRET_LENGTH} characters'
      raise ConfigurationError(message)

  @property
  def vite_websocket_origin(self) -> str:
    """Return the Vite dev server's websocket origin (``ws://``/``wss://``), for hot reload.

    Local mode adds it to the page's ``connect-src`` so the dev server's websocket isn't blocked.
    """
    return self.vite_origin.replace('http://', 'ws://', 1).replace('https://', 'wss://', 1)

  @property
  def authorize_url(self) -> str:
    """Return the absolute URL of the fake authorize endpoint, without a ``state``.

    Dialpad opens it (with a ``state`` appended) when the user clicks Connect.
    """
    return f'{self.base_url}/oauth/fake-authorize'

  @property
  def callback_url(self) -> str:
    """Return the absolute URL the fake authorize endpoint redirects to.

    A real CRM would redirect to the callback URL registered with it, which is built the same way.
    """
    return f'{self.base_url}/oauth/callback'


def _required(env: dict[str, str], name: str) -> str:
  """Return the environment variable ``name``, or raise ``ConfigurationError`` if unset or empty."""
  value = env.get(name)
  if value is None or value == '':
    message = f'{name} is required'
    raise ConfigurationError(message)
  return value


def listen_port(base_url: str, env: dict[str, str] | None = None) -> int:
  """Return the port to listen on: ``PORT`` if set, else the one in ``base_url``, else 8000.

  An explicit ``PORT`` wins because a container host (Cloud Run) tells the app which port to listen
  on, and the public ``base_url`` has no say in that. Without it, a local ``BASE_URL`` such as
  ``http://localhost:8000`` supplies the port, which keeps local runs to one setting.
  """
  env = dict(os.environ) if env is None else env
  port = env.get('PORT', '')
  if port:
    return int(port)
  return urlsplit(base_url).port or DEFAULT_PORT


def settings_from_env(env: dict[str, str] | None = None) -> Settings:
  """Build the settings from ``env`` (default: the process environment).

  Called once, at startup. ``HOST`` (default ``127.0.0.1``) is the address to listen on and
  applies in both modes. ``LOCAL_MODE=1`` fills in every value a local run needs, including the
  test client secret from ``acme_dialpad_rightbar.idtoken``, which is also what the dev host signs
  its mock idtoken with. Any of those can still be overridden. Outside local mode the client secret,
  app secret, Dialpad origin and base URL are all required, and a missing one raises
  ``ConfigurationError``.
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
        host=env.get('HOST', DEFAULT_HOST),
    )
  return Settings(
      client_secret=_required(env, 'DIALPAD_CLIENT_SECRET'),
      app_secret=_required(env, 'APP_SECRET'),
      dialpad_origin=_required(env, 'DIALPAD_ORIGIN'),
      base_url=_required(env, 'BASE_URL').rstrip('/'),
      dist_dir=env.get('DIST_DIR', DEFAULT_DIST_DIR),
      host=env.get('HOST', DEFAULT_HOST),
  )
