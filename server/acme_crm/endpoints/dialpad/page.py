"""``GET /``: the iframe panel page, which Dialpad loads in an iframe with the idtoken.

Dialpad opens the URL registered as the OAuth app's conversation sidebar URI and appends
``?idtoken=<token>``. This is the one request authenticated by the idtoken (decoded with the OAuth
app's client secret); every later request from the iframe panel uses the access token this page
hands out instead. See ``acme_crm.idtoken`` for the token and the README's Security section for why.
"""

from typing import TYPE_CHECKING

from sanic import HTTPResponse
from sanic import Request

from acme_crm.context import ACCOUNT_NAME
from acme_crm.contract import DEFAULT_API_PREFIX
from acme_crm.contract import ErrorResponse
from acme_crm.contract import PageData
from acme_crm.database import CookieBackedDatabaseStorage
from acme_crm.dialpad_api import fetch_dialpad_user
from acme_crm.dialpad_api import skipped
from acme_crm.idtoken import IdTokenError
from acme_crm.idtoken import decode_idtoken
from acme_crm.pages import PageOptions
from acme_crm.pages import generate_nonce
from acme_crm.pages import render_error_page
from acme_crm.pages import render_page
from acme_crm.responses import rendered
from acme_crm.stores import UserKey

if TYPE_CHECKING:
  from acme_crm.context import App
  from acme_crm.context import AppContext


def register(app: App, ctx: AppContext) -> None:
  """Register ``GET /``, the iframe panel page."""
  settings = ctx.settings

  @app.get('/')
  async def page(request: Request) -> HTTPResponse:
    """Render the iframe panel page for the user in the ``idtoken`` query parameter.

    Invoked when Dialpad (or the dev host) loads the iframe. A token that doesn't decode gets a
    ``401`` HTML page. Otherwise the page starts or continues this browser's session: a valid
    session cookie for this same user keeps its access token and connection state, and anything
    else (no cookie, a forged or old one, another user's) starts a new token, not connected. The
    page embeds the token and the connection (with an authorize URL when not connected), and sets
    the session cookie, which refreshes its 30 days. The page data's ``app`` field carries the
    result of the demo call to Dialpad's API (never the api key itself). The server stores nothing.
    """
    try:
      claims = decode_idtoken(request.args.get('idtoken'), settings.client_secret)
    except IdTokenError:
      error = ErrorResponse(code='invalid_idtoken', message='Open this panel from Dialpad.')
      return rendered(render_error_page(error, status=401, dialpad_origin=settings.dialpad_origin))
    key = UserKey(company_id=claims.company_id, user_id=claims.user_id)
    # DEMO ONLY, and UNNECESSARY for this app: the iframe panel works without this request. It shows
    # how the idtoken's `api_key` is used, by calling Dialpad's public API with it right here, on
    # the page request, while the idtoken is in hand. The key is used for this one call and dropped.
    # A real application must NOT work like this: it persists the api key in long-term storage
    # (the key never expires) and uses it to call Dialpad as and when necessary, for example from
    # a background job or a webhook handler, not only when the iframe panel loads. Local mode has no
    # real key (the mock idtoken's is `mock-api-key`, which Dialpad would refuse), so it makes no
    # call.
    demo = skipped() if settings.local_mode else await fetch_dialpad_user(
        claims.api_key,
        origin=settings.dialpad_origin,
        timeout=ctx.api_timeout,
    )
    existing = ctx.state_from_cookie(request)
    state = existing if existing and existing.belongs_to(key) else CookieBackedDatabaseStorage.new(
        key)
    page_data = PageData(
        dialpad_origin=settings.dialpad_origin,
        api_prefix=DEFAULT_API_PREFIX,
        access_token=state.get_access_token(),
        external_connection=ctx.external_connection(
            key,
            connected=state.is_external_connected(),
        ),
        app=demo.as_app_data(),
    )
    options = PageOptions(
        title=ACCOUNT_NAME,
        extra_connect_src=(settings.vite_websocket_origin,) if settings.local_mode else (),
    )
    reply = rendered(
        render_page(page_data, nonce=generate_nonce(), assets=ctx.assets, options=options))
    ctx.save_state(reply, state)
    return reply
