"""Run the backend: ``python -m backend`` (set ``LOCAL_MODE=1`` for local development).

See the README's Configuration section for the environment variables it reads.
"""

import logging
import os
from urllib.parse import urlsplit

from backend.app import create_app
from backend.settings import settings_from_env


def main() -> None:
  """Read the settings, build the app and serve it until the process is stopped.

  Listens on ``127.0.0.1`` at the port in ``BASE_URL``, else ``PORT``, else 8000. It binds to the
  loopback address only, so put a tunnel or reverse proxy in front to reach it from elsewhere.
  Exits immediately with a ``ConfigurationError`` if a setting is missing or invalid. Sanic's access
  log is off because it would print every page URL, idtoken included.
  """
  logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
  settings = settings_from_env()
  port = urlsplit(settings.base_url).port or int(os.environ.get('PORT', '8000'))
  app = create_app(settings)
  app.run(host='127.0.0.1', port=port, access_log=False, single_process=True)


if __name__ == '__main__':
  main()
