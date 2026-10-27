// The CRM record's items in Dialpad's panel menu. `bootstrap.ts` adds them to the connected menu.
import type { MenuItem } from '@dialpad/dialapp-external-sdk';

/**
 * Rematch: forget the saved match of the open contact to a CRM record, and look the contact up
 * again. The label is what Dialpad shows, in English only here.
 */
export const CRM_MENU = [
  { id: 'rematch', label: 'Rematch' },
] as const satisfies readonly MenuItem[];

/**
 * What Rematch tells the user here. The demo has no contact mapping, so it offers Rematch to show
 * the round trip and says it isn't built. A real app offers it once its server has matched the
 * contact to a record (chapter 7 of the guide).
 */
export const CRM_MENU_NOT_IMPLEMENTED: Readonly<Record<string, string>> = {
  rematch: "Rematch isn't implemented in this sample app",
};
