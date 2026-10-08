"""``POST /api/contact``: the CRM's view of a Dialpad contact, an iframe panel's own route.

The SDK makes only two requests of its own (``ext-connection`` and ``ext-disconnect``). Everything
else an iframe panel needs from its server is a route like this one, and each authenticates the same
way, with ``ctx.state_for(request)``: the bearer token must match the session cookie's.

The demo has no CRM, so the lookup is ``acme_crm.contacts.acme_fields``: the Dialpad contact's
fields with an ``Acme `` prefix, which proves the contact went to the server and back as the right
user. A real app would map the Dialpad contact to a CRM record with the user's stored CRM token,
fetch the record and return its fields; ``acme_crm.contacts`` describes each step.
"""

from dataclasses import asdict
from typing import TYPE_CHECKING

from sanic import HTTPResponse
from sanic import Request
from sanic.exceptions import BadRequest
from sanic.response import json

from acme_crm.contacts import acme_fields
from acme_crm.responses import error
from acme_crm.responses import unauthorized

if TYPE_CHECKING:
  from acme_crm.context import App
  from acme_crm.context import AppContext

# The path of the route.
CONTACT_PATH = '/api/contact'


def register(app: App, ctx: AppContext) -> None:
  """Register ``POST /api/contact``."""
  @app.post(CONTACT_PATH)
  async def contact(request: Request) -> HTTPResponse:
    """Answer with the CRM's view of the Dialpad contact in the request body.

    The body is ``{"contact": {...}}``, the contact as the SDK has it. The answer is
    ``{"fields": [{"label": ..., "value": ...}, ...]}``. The request is authenticated like every
    route the iframe panel calls, with ``ctx.state_for``: the bearer token must match the session
    cookie's (``401`` otherwise). A user who has not connected gets ``403``, because a real CRM
    lookup needs their CRM token. A body that is not that shape gets ``400``.

    The demo has no CRM, so the lookup is ``acme_fields``: the same fields with an ``Acme `` prefix.
    A real app would use the user's stored CRM token to map the Dialpad contact to a CRM record,
    fetch that record and return its fields; ``acme_crm.contacts`` describes each step.
    """
    state = ctx.state_for(request)
    if state is None:
      return unauthorized()
    if not state.is_external_connected():
      return error('not_connected', 'Connect your Acme account first.', 403)
    try:
      body = request.load_json()
    except BadRequest:
      body = None
    contact = body.get('contact') if isinstance(body, dict) else None
    if not isinstance(contact, dict):
      return error('invalid_request', 'Expected {"contact": {...}}.', 400)
    return json({'fields': [asdict(field) for field in acme_fields(contact)]})
