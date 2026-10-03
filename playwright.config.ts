import { defineConfig, devices } from '@playwright/test';

// The smoke test runs the whole local stack: the Sanic backend in local mode (port 8000) and the
// Vite dev server (port 5173), which serves the app's scripts and the dev page.
export default defineConfig({
  testDir: 'e2e',
  fullyParallel: false,
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
      command: '.venv/bin/python -m backend',
      url: 'http://localhost:8000/healthz',
      env: { LOCAL_MODE: '1' },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'pnpm exec vite',
      url: 'http://localhost:5173/dev/',
      reuseExistingServer: !process.env.CI,
    },
  ],
});
