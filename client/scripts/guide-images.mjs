// Captures the guide's images of the dev host into ../guide/images/.
//
//   pnpm run guide:images
//
// Start the server in local mode and Vite first (guide/02-run-the-demo.md). For each panel width,
// the script opens the dev host in Chromium, connects through the fake authorize page, waits for
// the connected view, and saves the image at twice the CSS size. Images of Dialpad itself are
// captured by hand; guide/images/README.md lists them.
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from '@playwright/test';

/** Where the guide keeps its images. */
const out = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../../guide/images',
);
const devHost = 'http://localhost:5173/dev-host/';

const browser = await chromium.launch();

/**
 * Open the dev host at `query` in a fresh context and connect, so the panel shows its connected
 * view. A fresh context for each page keeps the session cookies apart.
 */
async function openConnected(query) {
  const context = await browser.newContext({
    viewport: { width: 900, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();
  await page.goto(devHost + query);
  const panel = page.frameLocator('#panel iframe');
  const popup = page.waitForEvent('popup');
  await panel.getByRole('button', { name: 'Connect' }).click();
  await (await popup).getByRole('button', { name: 'Authorize' }).click();
  // The dev host never answers Connect, so the SDK's first check, after 7 seconds, finishes it.
  await panel.getByTestId('connected-view').waitFor({ timeout: 30_000 });
  await page.getByText('Connected to Acme CRM').waitFor();
  // Let the contact lookup's answer replace its loading state.
  await panel.getByText('Acme Pat Customer').first().waitFor();
  return { context, page };
}

try {
  const sidebar = await openConnected('');
  await sidebar.page.screenshot({
    path: `${out}/dev-host.png`,
    fullPage: true,
  });
  await sidebar.page
    .locator('#panel iframe')
    .screenshot({ path: `${out}/panel-318.png` });
  await sidebar.context.close();

  const dpe = await openConnected('?dpe');
  await dpe.page
    .locator('#panel iframe')
    .screenshot({ path: `${out}/panel-250.png` });
  await dpe.context.close();
} finally {
  await browser.close();
}
console.log(`Saved dev-host.png, panel-318.png and panel-250.png in ${out}`);
