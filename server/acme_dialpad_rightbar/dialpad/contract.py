"""The contract's schemas: what the page embeds and what the contract endpoints answer.

These pydantic models are this app's own copy of the DialApp contract (the frontend SDK reads the
page data and the ``ext-connection`` answer in exactly this shape), so keep their field names and
rules in step with the SDK. All models are frozen.
"""

from typing import Any
from typing import Self

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import SecretStr
from pydantic import model_validator

# The ``version`` the page data element carries. The frontend SDK rejects versions it doesn't know.
PAGE_DATA_VERSION = 1

# The id of the ``<script type="application/json">`` element carrying the page data.
PAGE_DATA_ELEMENT_ID = 'dialpad-page-data'

# Where the contract endpoints live: ``/dialpad/ext-connection`` and ``/dialpad/ext-disconnect``.
# The SDK always calls them here, so the page data carries no prefix.
CONTRACT_PATH_PREFIX = '/dialpad'


class IdTokenClaims(BaseModel):
  """What decoding a Dialpad idtoken returns.

  The ``csr`` claim is dropped while decoding and never exposed, and unknown claims are ignored so
  new claims from Dialpad don't break the app. ``api_key`` is server-side only: ``PageData`` has no
  field for it, and no claim goes into the page.
  """

  model_config = ConfigDict(extra='ignore', frozen=True)

  user_id: int
  company_id: int
  office_id: int
  name: str | None = None
  email: str | None = None
  phone_number: str | None = None
  image_url: str | None = None
  api_key: SecretStr = Field(description=(
      'Dialpad public API key for this user and app. Server-side only: never rendered into the '
      'page or sent to the browser.'),)


class ExternalConnection(BaseModel):
  """The Dialpad user's connection to the partner's system.

  The page data carries it so the first paint needs no request, and ``/dialpad/ext-connection``
  returns it whenever the SDK checks again (on start when not connected, and while Connect polls).
  """

  model_config = ConfigDict(extra='forbid', frozen=True)

  connected: bool = Field(
      description="Whether this Dialpad user has a working connection in the partner's store",)
  authorization_urls: dict[str, str] = Field(
      default_factory=dict,
      description=(
          'Where Connect sends the user, keyed by OAuth client name. Most apps have one entry; a '
          'company with several OAuth clients has one per client. Required when not connected.'),
  )
  name: str = Field(
      description="The name of the integration's OAuth client, for example ``hubspot``",)
  scopes: list[str] = Field(
      default_factory=list,
      description=(
          "The OAuth scopes the connection's client has, which apps can gate features on. Empty "
          'when not connected.'),
  )

  @model_validator(mode='after')
  def _require_authorization_urls(self) -> Self:
    """Refuse a disconnected status without an authorization URL: Connect needs one to open."""
    if not self.connected and not self.authorization_urls:
      msg = 'authorization_urls must not be empty when connected is false'
      raise ValueError(msg)
    return self


class PageData(BaseModel):
  """Embedded in the page and read by the frontend SDK.

  It carries no user: the SDK asks Dialpad for the user (``get/user``) once it starts.
  """

  model_config = ConfigDict(extra='forbid', frozen=True)

  dialpad_origin: str = Field(
      description='The Dialpad origin for this environment; the SDK talks only to it',)
  access_token: str = Field(description="The partner's own access token for this Dialpad user",)
  external_connection: ExternalConnection = Field(
      description='The connection at render time, so the first paint needs no extra request',)
  app: dict[str, Any] | None = Field(
      default=None,
      description='Partner-defined bootstrap data, passed through as JSON',
  )


class ErrorResponse(BaseModel):
  """Returned with ``401`` on a bad or missing idtoken, and ``403`` when a user is refused."""

  model_config = ConfigDict(extra='forbid', frozen=True)

  code: str
  message: str
