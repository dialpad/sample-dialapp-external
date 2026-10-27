"""The fake storage: this demo's stand-in for a database, kept in a signed cookie. DEMO ONLY.

A real partner keeps what it knows about each Dialpad user in its database, in whatever tables it
needs: the access tokens it handed out to the panel, and whether the user is connected to the CRM
(the CRM tokens the OAuth callback stored). This demo has no database and no CRM, so it keeps that
in the browser instead: one signed cookie (HMAC-SHA256 with ``APP_SECRET``, bound to the Dialpad
user and company, valid for 30 days).

* ``FakeStorage`` is what the route handlers use, as ``ctx.storage``: it reads the cookie for a
  page load (``for_page``), authenticates a request from the iframe panel (``authenticate``), and
  writes the cookie on a reply (``save``). A real app swaps this class for one backed by its own
  storage, and the handlers stay as they are.
* ``CookieBackedDatabaseStorage`` plays one user's stored data. The handlers read it only through
  its getters, ``get_access_token`` and ``is_external_connected``, and change it only by building a
  new one.
* ``issue_cookie`` and ``read_cookie`` sign and verify the cookie's value, signed like the OAuth
  ``state`` (``acme_dialpad_rightbar.signing``), under a different ``kind``.

How the storage cookie is used:

* The page load sets it, keeping the existing token when the browser already has a valid cookie for
  this user, so iframe panels open in the same browser share one token. The token is also embedded
  in the page data for the SDK.
* Every route the iframe panel calls accepts a call only when the ``Authorization: Bearer`` value
  equals the token in the cookie (compared in constant time). The cookie is ``SameSite=None``, so
  browsers attach it to cross-site requests too; requiring the header as well, which only code
  holding the page data can send, is what keeps another site from driving these endpoints (the
  "double submit" pattern).
* ``ext-connection`` and ``ext-disconnect`` rewrite it when the connection changes. Disconnect
  keeps the token and only turns ``connected`` off, so the SDK's next call still authenticates.

It lasts 30 days, refreshed by each page load, and survives a server restart or scale-to-zero;
changing ``APP_SECRET`` invalidates every cookie, so every open iframe panel gets ``401`` and must
reload. It isn't encrypted: anyone who can read the cookie (it is ``HttpOnly``, so page scripts
can't) sees the ids and the token in it, but nobody without the app secret can forge or alter one.

Limits of keeping this in a cookie, which a real partner's stored tokens don't have: it is
per browser (connecting in one browser doesn't connect another, and Disconnect only changes the
cookie in the browser that asked), a browser that refuses the cookie can't use the iframe panel at
all, and the server cannot revoke one before its 30 days are up other than by changing the secret.
"""

import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Self

from acme_dialpad_rightbar import signing
from acme_dialpad_rightbar.context import BEARER
from acme_dialpad_rightbar.context import UserKey

if TYPE_CHECKING:
  from collections.abc import Callable

  from sanic import HTTPResponse
  from sanic import Request

# How long the storage cookie is honoured; also its ``Max-Age``.
COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
# The storage cookie (access token and connection state), sent by browsers as `__Host-acme_session`.
# The name, and the `kind` below, keep their original values so cookies already set stay valid.
COOKIE_NAME = 'acme_session'
# Sanic prefixes the name with `__Host-` when host_prefix is set, and reports it that way back.
COOKIE_HEADER_NAME = f'__Host-{COOKIE_NAME}'

# The `kind` the cookie's signed value carries, so it's never accepted as an OAuth `state`.
_COOKIE = 'session'


@dataclass(frozen=True)
class CookieClaims:
  """What a verified storage cookie holds: whose it is, its access token, and the connection."""

  user_id: int
  company_id: int
  token: str
  connected: bool


def issue_cookie(claims: CookieClaims, secret: str, now: float) -> str:
  """Sign the storage cookie value: this user's access token and whether they are connected.

  Called on every page load (which refreshes the cookie's 30 days) and whenever the connection
  changes, in ``ext-connection`` when the user just finished OAuth and in ``ext-disconnect``.
  """
  return signing.sign(
      {
          'kind': _COOKIE,
          'user_id': claims.user_id,
          'company_id': claims.company_id,
          'token': claims.token,
          'connected': claims.connected,
          'iat': now,
      },
      secret,
  )


def read_cookie(value: str | None, secret: str, now: float) -> CookieClaims | None:
  """Return what a storage cookie value says, or ``None`` if it is missing, forged or too old.

  Called on the page request (the caller then checks the cookie belongs to the idtoken's user) and
  to authenticate the iframe panel's requests (the caller compares the token with the
  ``Authorization`` header). A malformed value, one signed for another purpose such as a ``state``,
  and one issued more than 30 days ago are all just "no cookie", never an error.
  """
  if value is None or value == '':
    return None
  payload = signing.verify(value, secret)
  if payload is None or payload.get('kind') != _COOKIE:
    return None
  issued = payload.get('iat')
  if not isinstance(issued, int | float) or now - issued > COOKIE_MAX_AGE_SECONDS:
    return None
  user_id = payload.get('user_id')
  company_id = payload.get('company_id')
  token = payload.get('token')
  connected = payload.get('connected')
  if not (isinstance(user_id, int) and isinstance(company_id, int)):
    return None
  if not (isinstance(token, str) and token != '' and isinstance(connected, bool)):
    return None
  return CookieClaims(user_id=user_id, company_id=company_id, token=token, connected=connected)


class CookieBackedDatabaseStorage:
  """One Dialpad user's access token and connection, read from and written to a cookie value.

  It is bound to the user and company it was created for: a browser that switches Dialpad users
  must not reuse the previous user's state (see ``belongs_to``). It is immutable: ``from_cookie``
  reads one from a request, ``new`` starts one, and ``to_cookie`` serialises it for the response;
  nothing is kept on the server.
  """
  def __init__(self, claims: CookieClaims) -> None:
    """Wrap already verified claims; use ``new`` or ``from_cookie`` instead of calling this."""
    self._claims = claims

  @classmethod
  def new(cls, key: UserKey) -> Self:
    """Start a state for this user: a fresh random access token, and not connected."""
    claims = CookieClaims(
        user_id=key.user_id,
        company_id=key.company_id,
        token=signing.new_access_token(),
        connected=False,
    )
    return cls(claims)

  @classmethod
  def from_cookie(cls, value: str | None, secret: str, now: float) -> Self | None:
    """Read the state from a storage cookie value, or ``None`` if it is missing, forged or old.

    The signature, the purpose and the 30-day age are checked by ``read_cookie``.
    """
    claims = read_cookie(value, secret, now)
    return None if claims is None else cls(claims)

  def to_cookie(self, secret: str, now: float) -> str:
    """Sign this state as a storage cookie value, stamped with the time of issue ``now``."""
    return issue_cookie(self._claims, secret, now)

  def user_key(self) -> UserKey:
    """Return the Dialpad user (company and user ids) this state belongs to."""
    return UserKey(company_id=self._claims.company_id, user_id=self._claims.user_id)

  def belongs_to(self, key: UserKey) -> bool:
    """Whether this state was created for exactly this user and company."""
    return self.user_key() == key

  def get_access_token(self) -> str:
    """Return the user's access token: what the iframe panel sends as ``Authorization: Bearer``."""
    return self._claims.token

  def has_access_token(self, candidate: str) -> bool:
    """Whether ``candidate`` is this state's access token, compared in constant time."""
    return secrets.compare_digest(candidate, self._claims.token)

  def is_external_connected(self) -> bool:
    """Whether the user is connected to the partner system (Acme CRM) in this state."""
    return self._claims.connected

  def with_external_connected(self, *, connected: bool) -> Self:
    """Return a copy of this state with the connection turned on or off, keeping the token.

    The access token is kept because the iframe panel keeps sending it: after a disconnect its next
    ``ext-connection`` call must still authenticate.
    """
    return type(self)(CookieClaims(
        user_id=self._claims.user_id,
        company_id=self._claims.company_id,
        token=self._claims.token,
        connected=connected,
    ))


def _set_cookie(reply: HTTPResponse, value: str) -> None:
  """Set the storage cookie on ``reply``, for ``COOKIE_MAX_AGE_SECONDS`` from now.

  Its attributes are ``Secure``, ``HttpOnly``, ``SameSite=None`` and ``Partitioned``, because the
  iframe panel runs in a third-party iframe, and the ``__Host-`` prefix, which pins it to this host
  and path ``/``.
  """
  reply.add_cookie(
      COOKIE_NAME,
      value,
      path='/',
      secure=True,
      httponly=True,
      samesite='None',
      partitioned=True,
      host_prefix=True,
      max_age=COOKIE_MAX_AGE_SECONDS,
  )


class FakeStorage:
  """What the route handlers store about a user, kept in the cookie: ``ctx.storage``.

  A real app replaces this class with one backed by its own database, in whatever tables it needs:
  for each access token, a hash of it, the Dialpad user, and an expiry. Its methods keep the same
  meaning.
  """
  def __init__(self, app_secret: str, clock: Callable[[], float]) -> None:
    """Sign and verify cookies with ``app_secret``; ``clock`` returns the time in seconds."""
    self._secret = app_secret
    self._clock = clock

  def from_request(self, request: Request) -> CookieBackedDatabaseStorage | None:
    """Read this browser's state from the request's storage cookie, if it has a valid one.

    ``None`` when it is missing, forged or too old. Reads the cookie only; never sets it.
    """
    return CookieBackedDatabaseStorage.from_cookie(
        request.cookies.get(COOKIE_HEADER_NAME),
        self._secret,
        self._clock(),
    )

  def for_page(self, request: Request, key: UserKey) -> CookieBackedDatabaseStorage:
    """Return the state for a page load by this user: the browser's own, or a new one.

    A valid storage cookie for this same user keeps its access token and connection; anything else
    (no cookie, a forged or old one, another user's) starts a new token, not connected.
    """
    existing = self.from_request(request)
    return existing if existing and existing.belongs_to(key) else CookieBackedDatabaseStorage.new(
        key)

  def save(self, reply: HTTPResponse, state: CookieBackedDatabaseStorage) -> None:
    """Write ``state`` to ``reply`` as the storage cookie, which lasts 30 days from now."""
    _set_cookie(reply, state.to_cookie(self._secret, self._clock()))

  def authenticate(self, request: Request) -> CookieBackedDatabaseStorage | None:
    """Authenticate a request from the iframe panel: its bearer token must be the cookie's token.

    Every route the iframe panel calls uses this, the SDK's two contract endpoints and any the
    application adds.

    Returns the state in the cookie when the header's token matches the state's access token,
    else ``None``: no header, no cookie, a forged or expired cookie, or a token that isn't the
    cookie's, for example an iframe panel left open after the browser's cookie changed to another
    user's or after ``APP_SECRET`` changed. Requiring both is what stops a cross-site request, which
    carries the ``SameSite=None`` cookie but can't know the token.
    """
    header = request.headers.get('Authorization', '')
    state = self.from_request(request)
    if state is None or not header.startswith(BEARER):
      return None
    return state if state.has_access_token(header.removeprefix(BEARER)) else None
