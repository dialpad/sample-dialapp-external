// Real-browser checks of the SDK, against the dev page. See README.md in this folder.
import { expect, test, type FrameLocator, type Page } from '@playwright/test';

const BACKEND = 'http://localhost:8000';

async function openDevPage(page: Page): Promise<FrameLocator> {
  await page.clock.install();
  await page.goto('/dev/');
  const panel = page.frameLocator('iframe');
  await expect(panel.getByTestId('connect-gate')).toBeVisible();
  return panel;
}

/** Clicks Connect, lets the popup finish and close itself, then moves the clock to the first poll. */
async function connectByPolling(
  page: Page,
  panel: FrameLocator,
): Promise<void> {
  const popup = page.waitForEvent('popup');
  await panel.getByTestId('connect-button').click();
  const authWindow = await popup;
  // The clock acts on every page in the context, so don't move it while the popup is closing.
  await expect.poll(() => authWindow.isClosed()).toBe(true);
  await page.clock.runFor(7_000);
  await expect(panel.getByTestId('connected-view')).toBeVisible();
}

async function hostThinksConnected(page: Page): Promise<boolean | undefined> {
  return page.evaluate(() => window.mockHost?.received.connected);
}

test('opened outside Dialpad, the panel asks to be opened from Dialpad', async ({
  page,
  request,
}) => {
  // The backend's page URL with a mock idtoken, opened directly instead of inside the dev page.
  const response = await request.get(`${BACKEND}/dev/frame-url`);
  const { url } = (await response.json()) as { url: string };

  await page.goto(url);

  await expect(page.getByTestId('bootstrap-error')).toHaveText(
    'Open this panel from Dialpad.',
  );
  await expect(page.getByTestId('connect-gate')).toHaveCount(0);
});

test('Connect that is never completed times out and the host stays not connected', async ({
  page,
  context,
}) => {
  // Block the fake authorize page, so the popup never finishes the OAuth round trip.
  await context.route('**/oauth/fake-authorize**', (route) => route.abort());
  const panel = await openDevPage(page);

  const popup = page.waitForEvent('popup');
  await panel.getByTestId('connect-button').click();
  await popup;
  await expect(panel.getByRole('status')).toContainText('Waiting');

  await page.clock.runFor(125_000);

  await expect(panel.getByRole('alert')).toContainText(
    "didn't respond in time",
  );
  await expect(panel.getByTestId('connect-button')).toHaveText('Try again');
  await expect(panel.getByRole('status')).toHaveCount(0);
  expect(await hostThinksConnected(page)).toBe(false);
});

test("Disconnect from Dialpad's panel menu shows the Connect gate", async ({
  page,
}) => {
  const panel = await openDevPage(page);
  await connectByPolling(page, panel);
  await expect.poll(() => hostThinksConnected(page)).toBe(true);

  const disconnectCalled = page.waitForRequest(
    (req) =>
      req.method() === 'POST' && req.url().endsWith('/dialpad/ext-disconnect'),
  );
  await page.evaluate(() => {
    window.mockHost?.trigger('disconnect');
  });
  await disconnectCalled;

  await expect(panel.getByTestId('connect-gate')).toBeVisible();
  await expect(panel.getByTestId('connected-view')).toHaveCount(0);
  await expect.poll(() => hostThinksConnected(page)).toBe(false);
});
