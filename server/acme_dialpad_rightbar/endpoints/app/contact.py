"""``POST /api/contact``: the CRM's view of a Dialpad contact, an iframe panel's own route.

Dialpad tells the iframe panel which contact is open, but that is Dialpad's contact: a name, phone
numbers and emails from Dialpad's directory. What a partner's iframe panel exists to show is the
partner's own record for that person. Getting from one to the other is the "contact mapping", and
it can only be done on the server, because it needs the user's CRM credentials.

The SDK makes only two requests of its own (``ext-connection`` and ``ext-disconnect``). Everything
else an iframe panel needs from its server is a route like this one, and each authenticates the same
way, with ``ctx.state_for(request)``: the bearer token must match the session cookie's.

**What this demo does.** There is no CRM, so there is no mapping. The route returns every non-empty
field of the Dialpad contact with an ``Acme `` prefix on its text, which proves the contact went to
the server and back, and that the request was authenticated as the right user. Nothing is looked up
or stored.

**What a real app would do instead**, in this route, once it has authenticated the request:

1. **Check the connection and get the CRM token.** Load the CRM tokens the OAuth callback stored
   for this Dialpad user. None means the user is not connected: answer ``403`` so the iframe panel
   shows its Connect screen. Refresh an expired access token with the stored refresh token first,
   and if the CRM says the grant was revoked, mark the user disconnected.
2. **Map the Dialpad contact to a CRM record.** Look first in your own mapping table (Dialpad
   contact id to CRM record id) for a match made earlier. Otherwise search the CRM with the
   contact's phone numbers and emails, normalised to the format the CRM stores (usually E.164
   phone numbers, lower-cased emails), and decide what zero, one and several matches mean: offer
   to create a record, use the match, or let the user pick. Save the choice in the mapping table.
3. **Fetch the mapped record.** Call the CRM's API with the user's CRM token as the bearer token
   (``Authorization: Bearer <CRM access token>``), and return only the fields the iframe panel
   shows, in your own response shape. Never return the CRM token.
4. **Tell Dialpad about the match.** After the iframe panel gets the record, it calls the SDK's
   ``linkRecord({...})`` so Dialpad can offer "View record" in the panel menu and use the record's
   URL for screen pops when a call comes in.
5. **Handle the CRM being slow or down** with a short timeout and an error the iframe panel can
   show, as ``acme_dialpad_rightbar.dialpad_api`` does for Dialpad's own API.
"""

import json
from typing import TYPE_CHECKING

from sanic import HTTPResponse
from sanic import Request
from sanic.exceptions import BadRequest
from sanic.response import json as json_response

from acme_dialpad_rightbar.responses import error
from acme_dialpad_rightbar.responses import unauthorized

if TYPE_CHECKING:
  from acme_dialpad_rightbar.context import App
  from acme_dialpad_rightbar.context import AppContext

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

    The demo's "lookup" is the prefixing below: text gets ``Acme ``, lists are prefixed element by
    element and joined with commas, anything else (numbers, booleans, nested objects) is shown as
    JSON, and empty fields (``None``, ``''``, ``[]``) are left out. The module docstring says what a
    real app does here.
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
    fields = body.get('contact') if isinstance(body, dict) else None
    if not isinstance(fields, dict):
      return error('invalid_request', 'Expected {"contact": {...}}.', 400)
    rows = []
    for label, value in fields.items():
      if value is None or value in ('', []):
        continue
      items = value if isinstance(value, list) else [value]
      shown = ', '.join(
          f'Acme {item}' if isinstance(item, str) else json.dumps(item) for item in items)
      rows.append({'label': label, 'value': shown})
    return json_response({'fields': rows})
