// Comparing Dialpad contacts: the panel's contact and the active call's contact are separate
// objects, so the app needs to know when they are the same person.
import type { Contact } from '@dialpad/dialapp-external-sdk';

/**
 * Whether two Dialpad contacts are the same contact.
 *
 * Used to avoid showing the same person twice when a call's contact is also the panel's contact,
 * which is the usual case: Dialpad opens the caller's contact in the right bar. Contacts with ids
 * are the same exactly when the ids are. Without ids on both, they are the same when their display
 * name, primary phone and primary email all match. Either one missing is never "the same".
 */
export function isSameContact(a: Contact | null, b: Contact | null): boolean {
  if (!a || !b) {
    return false;
  }
  if (a.id !== null && b.id !== null) {
    return a.id === b.id;
  }
  return (
    a.displayName === b.displayName &&
    a.primaryPhone === b.primaryPhone &&
    a.primaryEmail === b.primaryEmail
  );
}
