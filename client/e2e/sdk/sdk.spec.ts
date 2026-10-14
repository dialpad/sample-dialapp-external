// Real-browser tests of the iframe panel and the SDK against the dev host, in Chromium. See README.md in
// this folder: they are not part of the template.
//
// The Playwright config starts the server in local mode and Vite. Every test opens the dev host
// (a stand-in for Dialpad) with Playwright's clock installed, so waiting for the SDK's polling and
// timeouts costs no real time, and reads what the mock host believes through `window.mockHost`.
import { expect, test, type FrameLocator, type Page } from '@playwright/test';

/** Where the server runs in local mode. */
const SERVER = 'http://localhost:8000';

/**
 * Open the dev host with Playwright's clock installed and wait for the iframe panel's Connect gate.
 *
 * Starts from a fresh browser context, so the user is not connected (no cookie). Returns the
 * iframe panel for queries; the clock is paused until a test moves it.
 */
async function openDevPage(page: Page): Promise<FrameLocator> {
  await page.clock.install();
  await page.goto('/dev-host/');
  const panel = page.frameLocator('iframe');
  await expect(panel.getByTestId('connect-gate')).toBeVisible();
  return panel;
}

/**
 * Click Connect and return the popup Dialpad opens for the authorize URL.
 *
 * The popup shows the fake OAuth page and stays open until Authorize is pressed. The iframe panel shows
 * "Waiting for you to finish connecting" meanwhile.
 */
async function startConnect(page: Page, panel: FrameLocator): Promise<Page> {
  const popup = page.waitForEvent('popup');
  await panel.getByTestId('connect-button').click();
  return popup;
}

/**
 * Finish Connect the way the desktop app does, by polling: press Authorize, wait for the popup to
 * close itself, then move the clock to the SDK's first poll (7 seconds after Connect).
 *
 * When it returns, the server has handed the finished OAuth to that poll and the iframe panel shows the
 * connected view.
 */
async function authorizeAndPoll(
  page: Page,
  panel: FrameLocator,
  authWindow: Page,
): Promise<void> {
  await authWindow.getByRole('button', { name: 'Authorize' }).click();
  // The clock acts on every page in the context, so don't move it while the popup is closing.
  await expect.poll(() => authWindow.isClosed()).toBe(true);
  await page.clock.runFor(7_000);
  await expect(panel.getByTestId('connected-view')).toBeVisible();
}

/**
 * What the mock host believes: whether the iframe panel last told Dialpad it is connected.
 *
 * The SDK reports this automatically so Dialpad's iframe panel menu (which has Disconnect only while
 * connected) always matches the iframe panel.
 */
async function hostThinksConnected(page: Page): Promise<boolean | undefined> {
  return page.evaluate(() => window.mockHost?.received.connected);
}

/** The dev host's list of toasts, which Dialpad would show outside the panel. */
function toastList(page: Page) {
  return page.locator('#toasts li');
}

/** The dev host's view of the record the panel linked, which Dialpad shows as a header button. */
function linkedRecord(page: Page) {
  return page.locator('#linked-record');
}

test('connect by polling, reconnect on first paint, then disconnect', async ({
  page,
}) => {
  // First open, not connected.
  const panel = await openDevPage(page);

  // Connect opens the fake authorize page in a popup. The dev host never replies, so the SDK's
  // polling (first check after 7 seconds) completes it once Authorize is pressed.
  const authWindow = await startConnect(page, panel);
  await expect(authWindow.getByRole('note')).toContainText('fake OAuth page');
  await expect(panel.getByRole('status')).toContainText('Waiting');
  await authorizeAndPoll(page, panel, authWindow);
  await expect(toastList(page)).toHaveText(['success: Connected to Acme CRM']);
  await expect(panel.getByTestId('user-card')).toContainText('Jane Agent');
  // The server's demo call to Dialpad's API is skipped in local mode, and the card says so.
  await expect(panel.getByTestId('dialpad-api-card')).toContainText(
    'Skipped in local mode',
  );

  // Data flows from the host to the iframe panel: the contact open in the dev host, shown Acme'd, is
  // there as soon as the user is connected, and its record is linked back to the host. Changing
  // contact cycles through three and wraps, and the link follows.
  const contact = panel.getByTestId('acme-contact');
  await expect(contact).toContainText('Acme Pat Customer');
  await expect(linkedRecord(page).getByRole('link')).toHaveAttribute(
    'href',
    /\/records\/4800000000000001$/,
  );
  await page.getByRole('button', { name: 'Change contact' }).click();
  await expect(contact).toContainText('Acme Sam Prospect');
  await expect(linkedRecord(page).getByRole('link')).toHaveAttribute(
    'href',
    /\/records\/4800000000000002$/,
  );
  await page.getByRole('button', { name: 'Change contact' }).click();
  await expect(contact).toContainText('Acme Robin Partner');
  await page.getByRole('button', { name: 'Change contact' }).click();
  await expect(contact).toContainText('Acme Pat Customer');

  // A new iframe (the dev host reloaded) carries the cookie, so the first paint is connected.
  await page.reload();
  await expect(panel.getByTestId('connected-view')).toBeVisible();
  await expect(panel.getByTestId('connect-gate')).toHaveCount(0);

  // Disconnect, with inline confirmation.
  await panel.getByTestId('disconnect-button').click();
  await panel.getByTestId('disconnect-confirm').click();
  await expect(panel.getByTestId('connect-gate')).toBeVisible();
  await expect(linkedRecord(page)).toHaveText('None');
});

test("calls reach the iframe panel, with the call's contact when it differs", async ({
  page,
}) => {
  const panel = await openDevPage(page);
  await authorizeAndPoll(page, panel, await startConnect(page, panel));

  // The button steps a call through ringing, connected and ended; the next click is a new call.
  const call = panel.getByTestId('call-card');
  const nextCallState = page.getByRole('button', { name: 'Change call state' });
  await expect(call).toContainText('No active call');
  await nextCallState.click();
  await expect(call).toContainText('Ringing');

  // The call's contact is the one open when it started, so while they are the same person there is
  // one contact section. Changing the iframe panel's contact mid-call shows both; changing it back hides
  // the call's again.
  const contact = panel.getByTestId('acme-contact');
  const callContact = panel.getByTestId('call-contact');
  await expect(callContact).toHaveCount(0);
  await page.getByRole('button', { name: 'Change contact' }).click();
  await expect(contact).toContainText('Acme Sam Prospect');
  await expect(callContact).toContainText('Acme Pat Customer');
  await page.getByRole('button', { name: 'Change contact' }).click();
  await page.getByRole('button', { name: 'Change contact' }).click();
  await expect(contact).toContainText('Acme Pat Customer');
  await expect(callContact).toHaveCount(0);

  await nextCallState.click();
  await expect(call).toContainText('Connected');
  await nextCallState.click();
  await expect(call).toContainText('Ended');
  await nextCallState.click();
  await expect(call).toContainText('Ringing');
});

test('opened outside Dialpad, the iframe panel asks to be opened from Dialpad', async ({
  page,
  request,
}) => {
  // The server's page URL with a mock idtoken, opened directly instead of inside the dev host.
  const response = await request.get(`${SERVER}/dev/frame-url`);
  const { url } = (await response.json()) as { url: string };

  await page.goto(url);

  await expect(page.getByTestId('bootstrap-error')).toHaveText(
    'Open this panel from Dialpad.',
  );
  await expect(page.getByTestId('connect-gate')).toHaveCount(0);
});

test('Connect that is never completed times out and the host stays not connected', async ({
  page,
}) => {
  const panel = await openDevPage(page);

  // Authorize is never pressed, so the OAuth round trip never finishes.
  const authWindow = await startConnect(page, panel);
  await expect(authWindow.getByRole('note')).toContainText('fake OAuth page');
  await expect(panel.getByRole('status')).toContainText('Waiting');

  await page.clock.runFor(125_000);

  await expect(panel.getByRole('alert')).toContainText(
    "didn't respond in time",
  );
  await expect(panel.getByTestId('connect-button')).toHaveText('Try again');
  await expect(panel.getByRole('status')).toHaveCount(0);
  expect(await hostThinksConnected(page)).toBe(false);
});

test("Disconnect from Dialpad's iframe panel menu shows the Connect gate", async ({
  page,
}) => {
  const panel = await openDevPage(page);
  await authorizeAndPoll(page, panel, await startConnect(page, panel));
  await expect.poll(() => hostThinksConnected(page)).toBe(true);

  const disconnectCalled = page.waitForRequest(
    (req) =>
      req.method() === 'POST' && req.url().endsWith('/dialpad/ext-disconnect'),
  );
  await page
    .getByRole('button', { name: "Disconnect from Dialpad's menu" })
    .click();
  await disconnectCalled;

  await expect(panel.getByTestId('connect-gate')).toBeVisible();
  await expect(panel.getByTestId('connected-view')).toHaveCount(0);
  await expect.poll(() => hostThinksConnected(page)).toBe(false);
  await expect(toastList(page)).toHaveText([
    'success: Connected to Acme CRM',
    'info: Disconnected from Acme CRM',
  ]);
});

test('a failed contact lookup shows an error toast as well as the message in the panel', async ({
  page,
}) => {
  const panel = await openDevPage(page);
  await authorizeAndPoll(page, panel, await startConnect(page, panel));
  await expect(panel.getByTestId('acme-contact')).toContainText(
    'Acme Pat Customer',
  );

  await page.route('**/api/contact', (route) =>
    route.fulfill({ status: 500, json: { code: 'oops', message: 'oops' } }),
  );
  await page.getByRole('button', { name: 'Change contact' }).click();

  await expect(panel.getByTestId('acme-contact')).toContainText(
    "Couldn't load the contact",
  );
  await expect(toastList(page)).toHaveText([
    'success: Connected to Acme CRM',
    "error: Couldn't load the contact from Acme CRM",
  ]);
});
