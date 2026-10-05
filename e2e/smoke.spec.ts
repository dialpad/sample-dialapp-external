// One browser smoke test of flows 1, 2, 4 and 5 against the dev page: Connect completes by polling,
// the next iframe is connected on first paint, and Disconnect returns to the Connect gate. Time is
// moved with Playwright's clock, not real waits.
import { expect, test } from '@playwright/test';

test('connect by polling, reconnect on first paint, then disconnect', async ({
  page,
}) => {
  await page.clock.install();
  await page.goto('/dev/');
  const panel = page.frameLocator('iframe');

  // Flow 1: first open, not connected.
  await expect(panel.getByTestId('connect-gate')).toBeVisible();

  // Flow 2: Connect opens the fake authorize URL in a popup; the dev page never replies, so the
  // SDK's polling (first check after 7 seconds) completes it.
  const popup = page.waitForEvent('popup');
  await panel.getByTestId('connect-button').click();
  const authWindow = await popup;
  await expect(panel.getByRole('status')).toContainText('Waiting');
  // The clock acts on every page in the context, so don't move it while the popup is closing.
  await expect.poll(() => authWindow.isClosed()).toBe(true);
  await page.clock.runFor(7_000);
  await expect(panel.getByTestId('connected-view')).toBeVisible();
  await expect(panel.getByTestId('claims-card')).toContainText('Jane Agent');

  // Data flows from the host to the panel: the contact the dev page sends is shown Acme'd.
  await page.getByRole('button', { name: 'Send contact' }).click();
  await expect(panel.getByTestId('acme-contact')).toContainText(
    'Acme Pat Customer',
  );

  // Flow 4: a new iframe (the dev page reloaded) carries the cookie, so the first paint is connected.
  await page.reload();
  await expect(panel.getByTestId('connected-view')).toBeVisible();
  await expect(panel.getByTestId('connect-gate')).toHaveCount(0);

  // Flow 5: Disconnect, with inline confirmation.
  await panel.getByTestId('disconnect-button').click();
  await panel.getByTestId('disconnect-confirm').click();
  await expect(panel.getByTestId('connect-gate')).toBeVisible();
});
