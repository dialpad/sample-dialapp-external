// Dialpad's panel menu and header refresh button: what they show while the user is connected, and
// what the menu's items do. `bootstrap` calls `setUpPanelMenu` once the SDK has started.
import type { MenuItem, Rightbar } from '@dialpad/dialapp-external-sdk';

import { CRM_MENU, CRM_MENU_NOT_IMPLEMENTED } from './crm/menu'; // crm-record

/**
 * The panel menu while the user is connected. The ids are the app's own; the labels are what
 * Dialpad shows, in English only here. A real app picks translated labels from
 * `state.user.language` (chapter 4 of the guide).
 */
export const CONNECTED_MENU = [
  ...CRM_MENU, // crm-record
  { id: 'create-task', label: 'Create Task' },
  { id: 'disconnect', label: 'Disconnect' },
] as const satisfies readonly MenuItem[];

/**
 * What the panel menu's items other than Disconnect tell the user here, by item id. The demo has no
 * tasks, so it offers Create Task to show the round trip and says it isn't built.
 */
export const MENU_NOT_IMPLEMENTED: Readonly<Record<string, string>> = {
  ...CRM_MENU_NOT_IMPLEMENTED, // crm-record
  'create-task': "Create Task isn't implemented in this sample app",
};

/**
 * Show the panel menu and the refresh button while the user is connected, and answer the menu.
 *
 * Runs at every start, because Dialpad forgets the menu when the panel reloads. Disconnect calls the
 * SDK's `disconnect()`; the other items only show a toast. The refresh button needs nothing here:
 * `crm/AcmeContact.vue` handles `refreshContact`. If Dialpad rejects a menu, button or toast, the
 * panel logs it and goes on. Chapter 4 of the guide explains both controls.
 */
export function setUpPanelMenu(rightbar: Rightbar): void {
  rightbar.watch(
    (s) => s.connection.connected,
    (connected) => {
      rightbar
        .setMenu(connected ? CONNECTED_MENU : [])
        .catch((error: unknown) => {
          console.warn("Dialpad didn't set the panel menu", error);
        });
      rightbar.showRefreshButton(connected).catch((error: unknown) => {
        console.warn("Dialpad didn't show the refresh button", error);
      });
    },
  );
  rightbar.on('menuSelect', (id) => {
    if (id === 'disconnect') {
      void rightbar.disconnect();
      return;
    }
    const text = MENU_NOT_IMPLEMENTED[id];
    if (text) {
      rightbar.showToast({ text, type: 'info' }).catch((error: unknown) => {
        console.warn("Dialpad didn't show the toast", error);
      });
    }
  });
}
