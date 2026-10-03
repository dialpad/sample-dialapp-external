// "Acme'ing" a Dialpad contact: the reference app has no CRM, so it proves data flow by showing
// every field of the contact the host sent with an "Acme " prefix on its text.

export interface AcmeField {
  /** The contact model's field name, for example `displayName`. */
  label: string;
  value: string;
}

const PREFIX = 'Acme ';

function isEmpty(value: unknown): boolean {
  return (
    value === null ||
    value === undefined ||
    value === '' ||
    (Array.isArray(value) && value.length === 0)
  );
}

function acmeScalar(value: unknown): string {
  return typeof value === 'string' ? `${PREFIX}${value}` : String(value);
}

/**
 * Strings get an `Acme ` prefix, lists are Acme'd element by element, anything else is shown
 * unchanged. Empty fields are omitted.
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
