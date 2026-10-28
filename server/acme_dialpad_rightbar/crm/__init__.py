"""The CRM record: what the iframe panel calls to show a contact's record in the CRM.

* ``POST /api/contact``: the CRM's view of a Dialpad contact, and the record to link
  (``contact.py``). The client library doesn't invoke it; the application's own frontend does.
* ``GET /records/<contact id>``: a stand-in for the CRM's page for a record, clearly labelled fake,
  which the iframe panel links so Dialpad's View button opens it (``fake_record.py``). A real
  partner links their CRM's own record page instead.

An app that doesn't show a CRM record deletes this package, ``server/tests/test_crm.py``, and the
lines tagged ``crm-record`` (chapter 11 of the guide).
"""

from typing import TYPE_CHECKING

from acme_dialpad_rightbar.crm import contact
from acme_dialpad_rightbar.crm import fake_record

if TYPE_CHECKING:
  from acme_dialpad_rightbar.context import App
  from acme_dialpad_rightbar.context import AppContext


def register_crm_endpoints(app: App, ctx: AppContext) -> None:
  """Add the CRM record's routes to ``app``."""
  contact.register(app, ctx)
  fake_record.register(app, ctx)
