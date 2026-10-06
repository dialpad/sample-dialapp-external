"""Run the backend: ``python -m backend`` (set ``LOCAL_MODE=1`` for local development).

See the README's Configuration section for the environment variables it reads.
"""

import logging

from backend.app import create_app
from backend.settings import listen_port
from backend.settings import settings_from_env


def main() -> None:
  """Read the settings, build the app and serve it until the process is stopped.

  Listens on ``HOST`` (default ``127.0.0.1``, this machine only; a container sets ``0.0.0.0``) at
  ``PORT``, else the port in ``BASE_URL``, else 8000. Exits immediately with a
  ``ConfigurationError`` if a setting is missing or invalid. Sanic's access log is off because it
  would print every page URL, idtoken included.
  """
  logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
  settings = settings_from_env()
  port = listen_port(settings.base_url)
  app = create_app(settings)
  app.run(host=settings.host, port=port, access_log=False, single_process=True)


if __name__ == '__main__':
  main()
