"""A demo-only call to Dialpad's public API with the idtoken's ``api_key``.

**This whole module is unnecessary for the app to work, and exists for demo purposes only.** The
panel gets everything it needs from the SDK (the user from Dialpad's ``get/user``, the contact and
call from the host), so nothing here is required. It only shows how the ``api_key`` in the idtoken
is used: as a bearer token for Dialpad's public API, through Dialpad's own Python client
(``python-dialpad``), here to ask "who am I" with ``GET /api/v2/users/me``.

A real application would not do this once, at page load, and forget the key. The key never expires,
so a real application **persists it in long-term storage** the first time it sees it (keyed by the
Dialpad user, and kept as secret as its CRM tokens) and **uses it to call Dialpad as and when
needed**: from a background job, a webhook handler, or any later request, not only while the panel
is loading. This reference app stores nothing, so it can only show the first use, on the page
request, while the idtoken is in hand. The key is never put in the page, logged or returned.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Final
from typing import Literal

import httpx
from dialpad import AsyncDialpadClient

if TYPE_CHECKING:
  from pydantic import SecretStr

logger = logging.getLogger('acme_crm')

# How long the page request waits for Dialpad's API before showing the panel without the answer.
# Short on purpose: the call is a demo, and the panel must not wait on it.
DEFAULT_TIMEOUT_SECONDS: Final = 3.0
# The key of the demo's result in the page data's partner-defined ``app`` field.
APP_KEY: Final = 'dialpadApi'

Status = Literal['ok', 'unavailable', 'skipped']


@dataclass(frozen=True)
class DialpadApiResult:
  """What the demo call came to, in the shape the panel shows.

  ``status`` is ``ok`` (``user`` holds the fields shown), ``unavailable`` (Dialpad's API refused,
  failed or took too long; the page renders anyway) or ``skipped`` (never called, as in local
  mode). It never holds the api key.
  """

  status: Status
  user: dict[str, object] | None = None

  def as_app_data(self) -> dict[str, object]:
    """Return this result as the page data's ``app`` field, which the SDK hands to the panel."""
    return {APP_KEY: {'status': self.status, 'user': self.user}}


def skipped() -> DialpadApiResult:
  """Return the result for a request that made no call (local mode has no real api key)."""
  return DialpadApiResult(status='skipped')


async def fetch_dialpad_user(
    api_key: SecretStr,
    *,
    origin: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS, # noqa: ASYNC109 (a deadline for the whole call)
) -> DialpadApiResult:
  """Ask Dialpad who the api key belongs to, with ``GET {origin}/api/v2/users/me``.

  DEMO ONLY: unnecessary for the app (see the module docstring). Called once per page request,
  while the idtoken is in hand; the key is used for this one call and then dropped, because this
  app persists nothing. The request is made by Dialpad's Python client, not by hand.

  Never raises for a Dialpad problem: a refused key (401), a network error, a slow answer (more
  than ``timeout`` seconds, with no retry) or an unreadable body all give ``unavailable`` and a log
  line with only the failure's type or status code, so the page renders either way.
  """
  client = AsyncDialpadClient(token=api_key.get_secret_value(), base_url=origin)
  try:
    async with asyncio.timeout(timeout):
      user = await client.users.get('me')
  except httpx.HTTPStatusError as error:
    logger.warning('Dialpad API answered %s', error.response.status_code)
    return DialpadApiResult(status='unavailable')
  except (httpx.HTTPError, TimeoutError, ValueError) as error:
    logger.warning('Dialpad API request failed: %s', type(error).__name__)
    return DialpadApiResult(status='unavailable')
  finally:
    # The client has no public close and keeps an httpx session open, so close it here.
    await client._session.aclose() # noqa: SLF001
  if not isinstance(user, dict):
    logger.warning('Dialpad API answered with %s, not an object', type(user).__name__)
    return DialpadApiResult(status='unavailable')
  emails = user.get('emails') or []
  return DialpadApiResult(
      status='ok',
      user={
          'id': user.get('id'),
          'displayName': user.get('display_name'),
          'email': emails[0] if emails else None,
          'state': user.get('state'),
      },
  )
