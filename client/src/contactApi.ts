// The panel's request for the CRM's view of a Dialpad contact: `POST /api/contact`.
//
// What the demo does: it sends the Dialpad contact to its own server, which answers with the
// contact's fields "Acme'd" (every text value prefixed with `Acme `). That proves the contact went
// to the server and back as the right user; there is no CRM behind it.
//
// What a real app would do: the same request, but the server uses the user's stored CRM token to
// map the Dialpad contact to a CRM record (by a saved mapping, or by searching the CRM for the
// contact's phone numbers and emails), fetches that record and returns the fields to show. Once the
// panel has the record it calls the SDK's `linkRecord(...)`, so Dialpad shows a "View <type>" button
// in the panel header that opens the record's URL, and uses that URL for screen pops. The server
// side is described in `server/acme_dialpad_rightbar/endpoints/app/contact.py`.
import type { Contact } from '@dialpad/dialapp-external-sdk';

import { api } from './api';

/** One row of the contact the server answered with: a field name and the text to show for it. */
export interface AcmeField {
  /** The contact model's field name, for example `displayName`. */
  label: string;
  /** The field's value as shown, already prefixed; a list is joined with commas. */
  value: string;
}

/** The path of the server route; it is the app's own, not part of the DialApp contract. */
export const CONTACT_PATH = '/api/contact';

/** Whether `value` is a plain JSON object. */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Read the server's answer, `{ fields: [{ label, value }, ...] }`, or throw if it is not that.
 *
 * The body is JSON from the network, so its shape is checked rather than trusted.
 */
function readFields(body: unknown): AcmeField[] {
  const fields = isRecord(body) ? body.fields : undefined;
  if (!Array.isArray(fields)) {
    throw new TypeError('The contact answer has no fields list');
  }
  return fields.map((field: unknown) => {
    if (
      !isRecord(field) ||
      typeof field.label !== 'string' ||
      typeof field.value !== 'string'
    ) {
      throw new TypeError('The contact answer has a malformed field');
    }
    return { label: field.label, value: field.value };
  });
}

/**
 * Ask the server for the CRM's view of `contact`.
 *
 * Sent through `api()`, so it carries the access token like every request this panel makes, and a
 * `401` shows the "reload the panel" notice. Throws when the server answers with an error status
 * (for example `403` when the user is not connected) or with something that is not a field list.
 */
export async function fetchAcmeFields(contact: Contact): Promise<AcmeField[]> {
  const response = await api(CONTACT_PATH, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contact }),
  });
  if (!response.ok) {
    throw new Error(`The contact lookup failed with status ${response.status}`);
  }
  return readFields(await response.json());
}
