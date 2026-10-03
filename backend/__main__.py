"""Run the backend: ``python -m backend`` (set ``LOCAL_MODE=1`` for local development)."""

import logging
import os
from urllib.parse import urlsplit

from backend.app import create_app
from backend.settings import settings_from_env


def main() -> None:
  """Start the Sanic server on the port in ``BASE_URL`` (default 8000)."""
  logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
  settings = settings_from_env()
  port = urlsplit(settings.base_url).port or int(os.environ.get('PORT', '8000'))
  app = create_app(settings)
  app.run(host='127.0.0.1', port=port, access_log=False, single_process=True)


if __name__ == '__main__':
  main()
