"""Looking up the CRM's view of a Dialpad contact, for the iframe panel to show. DEMO ONLY.

Dialpad tells the iframe panel which contact is open (and which contact an active call is with),
but that is Dialpad's contact: a name, phone numbers and emails from Dialpad's directory. What a
partner's panel exists to show is the partner's own record for that person: their CRM account,
deals, notes. Getting from one to the other is the "contact mapping" that every real integration
has to do, and it can only be done on the server, because it needs the user's CRM credentials.

**What this demo does.** There is no CRM, so there is no mapping. The iframe panel sends the Dialpad
contact to ``POST /api/contact``, and ``acme_fields`` returns every non-empty field with an
``Acme `` prefix on its text, which proves the contact went to the server and back, and that the
request was authenticated as the right user. Nothing is looked up or stored.

**What a real app would do instead**, in the same route, once it has authenticated the request (see
``acme_crm.database.CookieBackedDatabaseStorage`` for who is asking):

1. **Check the connection and get the CRM token.** Load the CRM tokens the OAuth callback stored
   for this Dialpad user. None means the user is not connected: answer ``403`` so the panel shows
   its Connect screen. Refresh an expired access token with the stored refresh token first, and if
   the CRM says the grant was revoked, mark the user disconnected.
2. **Map the Dialpad contact to a CRM record.** Look first in your own mapping table (Dialpad
   contact id to CRM record id) for a match made earlier. Otherwise search the CRM with the
   contact's phone numbers and emails, normalised to the format the CRM stores (usually E.164
   phone numbers, lower-cased emails), and decide what zero, one and several matches mean: offer
   to create a record, use the match, or let the user pick. Save the choice in the mapping table.
3. **Fetch the mapped record.** Call the CRM's API with the user's CRM token as the bearer token
   (``Authorization: Bearer <CRM access token>``), and return only the fields the panel shows, in
   your own response shape. Never return the CRM token.
4. **Tell Dialpad about the match.** After the panel gets the record, it calls the SDK's
   ``linkRecord({...})`` so Dialpad can offer "View record" in the panel menu and use the record's
   URL for screen pops when a call comes in.
5. **Handle the CRM being slow or down** with a short timeout and an error the panel can show,
   as ``acme_crm.dialpad_api`` does for Dialpad's own API.
"""

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from collections.abc import Mapping

# What the demo puts in front of every text value to show it went through the server.
PREFIX = 'Acme '


@dataclass(frozen=True)
class AcmeField:
  """One row of the Acme'd contact: a contact field and its Acme'd text."""

  # The contact model's field name, for example ``displayName``.
  label: str
  # The field's value as shown, already prefixed; a list is joined with commas.
  value: str


def _is_empty(value: object) -> bool:
  """Whether a contact field has nothing to show: ``None``, an empty string or an empty list."""
  return value is None or value == '' or (isinstance(value, list) and len(value) == 0)


def _acme_scalar(value: object) -> str:
  """Acme one value: text gets the prefix, anything else (numbers, booleans) is shown as JSON."""
  return f'{PREFIX}{value}' if isinstance(value, str) else json.dumps(value, sort_keys=True)


def acme_fields(contact: Mapping[str, object]) -> list[AcmeField]:
  """Turn a Dialpad contact into rows for the iframe panel, with every text value "Acme'd".

  The stand-in for "look the contact up in the partner's system" (see the module docstring for
  what a real app does here). Strings get an ``Acme `` prefix, lists are Acme'd element by element
  and joined with commas, anything else (numbers, booleans, nested objects) is shown unchanged as
  JSON, and empty fields (``None``, ``''``, ``[]``) are left out. Zero and ``False`` are not empty.
  The rows keep the order of the contact's fields.
  """
  fields: list[AcmeField] = []
  for label, value in contact.items():
    if _is_empty(value):
      continue
    if isinstance(value, list):
      shown = ', '.join(_acme_scalar(item) for item in value)
    else:
      shown = _acme_scalar(value)
    fields.append(AcmeField(label=label, value=shown))
  return fields
