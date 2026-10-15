import { defineConfig, devices } from '@playwright/test';

// The browser tests run the whole local stack: the Sanic server in local mode (port 8000) and the
// Vite dev server (port 5173), which serves the app's scripts and the dev host. Playwright starts
// both and waits for them; outside CI it reuses servers you already started with `pnpm dev`.
// The tests run one at a time (`workers: 1`) because they share the server's in-memory state.
export default defineConfig({
  testDir: 'e2e',
  fullyParallel: false,
  // One worker: every test uses the same default Dialpad user on one server, which remembers a
  // finished OAuth round trip until a connection check collects it. Tests in parallel would
  // collect each other's.
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      // The server's own virtual environment (see guide/02-run-the-demo.md), run from server/ so it finds acme_dialpad_rightbar.
      command: '.venv/bin/python -m acme_dialpad_rightbar',
      cwd: '../server',
      url: 'http://localhost:8000/healthz',
      env: { LOCAL_MODE: '1' },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'pnpm exec vite',
      url: 'http://localhost:5173/dev-host/',
      reuseExistingServer: !process.env.CI,
    },
  ],
});
