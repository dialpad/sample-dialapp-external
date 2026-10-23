// The panel's request for the CRM's view of a Dialpad contact: `POST /api/contact`.
//
// What the demo does: it sends the Dialpad contact to its own server, which answers with the
// contact's fields "Acme'd" (every text value prefixed with `Acme `), and a record to link: the
// server's fake record page for the contact's id. That proves the contact went to the server and
// back as the right user; there is no CRM behind it.
//
// What a real app would do: the same request, but the server uses the user's stored CRM token to
// map the Dialpad contact to a CRM record (by a saved mapping, or by searching the CRM for the
// contact's phone numbers and emails), fetches that record and returns the fields to show and the
// record's URL in the CRM. Either way the panel then calls the SDK's `linkRecord(...)`, so Dialpad
// shows a "View <type>" button in the panel header that opens the record's URL, and uses that URL
// for screen pops. The server side is described in
// `server/acme_dialpad_rightbar/endpoints/app/contact.py`.
import type { Contact, LinkedRecord } from '@dialpad/dialapp-external-sdk';

import { api } from './api';

/** One row of the contact the server answered with: a field name and the text to show for it. */
export interface AcmeField {
  /** The contact model's field name, for example `displayName`. */
  label: string;
  /** The field's value as shown, already prefixed; a list is joined with commas. */
  value: string;
}

/** The server's answer for one contact: the rows to show, and the record to link, if any. */
export interface AcmeContact {
  fields: AcmeField[];
  /** The record for `linkRecord`, or `null` when the contact has nothing to link. */
  record: LinkedRecord | null;
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
 * Whether `url` is an absolute http(s) URL.
 *
 * Uses the `URL` constructor rather than `URL.canParse`, which Chrome added only in 120; the SDK
 * supports Chrome 109 and later.
 */
function isWebUrl(url: string): boolean {
  try {
    return ['http:', 'https:'].includes(new URL(url).protocol);
  } catch {
    return false;
  }
}

/**
 * Read the server's `record`, `{ type, url }` or `null`, or throw if it is neither.
 *
 * Dialpad opens the URL in a new tab, so only an http(s) URL is accepted.
 */
function readRecord(record: unknown): LinkedRecord | null {
  if (record === null) {
    return null;
  }
  if (
    !isRecord(record) ||
    typeof record.type !== 'string' ||
    typeof record.url !== 'string' ||
    !isWebUrl(record.url)
  ) {
    throw new TypeError('The contact answer has a malformed record');
  }
  return { type: record.type, url: record.url };
}

/**
 * Ask the server for the CRM's view of `contact`.
 *
 * Sent through `api()`, so it carries the access token like every request this panel makes, and a
 * `401` shows the "reload the panel" notice. Throws when the server answers with an error status
 * (for example `403` when the user is not connected) or with something that is not a field list
 * and a record.
 */
export async function fetchAcmeContact(contact: Contact): Promise<AcmeContact> {
  const response = await api(CONTACT_PATH, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contact }),
  });
  if (!response.ok) {
    throw new Error(`The contact lookup failed with status ${response.status}`);
  }
  const body: unknown = await response.json();
  return {
    fields: readFields(body),
    record: readRecord(isRecord(body) ? body.record : undefined),
  };
}
