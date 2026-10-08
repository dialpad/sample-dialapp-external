// "Acme'ing" a Dialpad contact: the reference app has no CRM, so it proves data flow by showing
// every field of the contact the host sent with an "Acme " prefix on its text.

/** One row of the Acme'd contact: a contact field and its Acme'd text. */
export interface AcmeField {
  /** The contact model's field name, for example `displayName`. */
  label: string;
  /** The field's value as shown, already prefixed; a list is joined with commas. */
  value: string;
}

/** What the reference app puts in front of every text value to show it went through the app. */
const PREFIX = 'Acme ';

/** Whether a contact field has nothing to show: null, undefined, an empty string or empty list. */
function isEmpty(value: unknown): boolean {
  return (
    value === null ||
    value === undefined ||
    value === '' ||
    (Array.isArray(value) && value.length === 0)
  );
}

/** Acme one value: text gets the prefix, numbers and booleans are shown as they are. */
function acmeScalar(value: unknown): string {
  return typeof value === 'string' ? `${PREFIX}${value}` : String(value);
}

/**
 * Turn the Dialpad contact into rows for the iframe panel, with every text value "Acme'd".
 *
 * The reference app has no CRM, so this stands in for "look the contact up in the partner's
 * system": it proves the contact reached the iframe panel from Dialpad, one labelled row per field.
 * Strings get an `Acme ` prefix, lists are Acme'd element by element, anything else (numbers,
 * booleans) is shown unchanged, and empty fields are left out. Zero and `false` are not empty.
 */
export function acmeFields(contact: object): AcmeField[] {
  return Object.entries(contact)
    .filter(([, value]) => !isEmpty(value))
    .map(([label, value]) => ({
      label,
      value: Array.isArray(value)
        ? (value as unknown[]).map(acmeScalar).join(', ')
        : acmeScalar(value),
    }));
}
