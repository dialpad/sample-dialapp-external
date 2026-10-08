import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vitest/config';

// One config for the dev server, the production build and the unit tests.
//
// The server renders the page HTML, not Vite. In production it reads client/dist/.vite/manifest.json
// (written because `build.manifest` is on) to link the built entry; in local mode it points script
// tags at this dev server.
export default defineConfig({
  plugins: [vue()],
  // The server's local-mode CSP and the dev host expect this exact port.
  server: { port: 5173, strictPort: true },
  build: {
    manifest: true,
    // The iframe panel is a single entry module; there is no index.html in this build.
    rollupOptions: { input: 'src/main.ts' },
  },
  // Vitest: components run in jsdom, with the SDK's setup file (a ResizeObserver stub for jsdom
  // and clean-up of every mock host after each test).
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts'],
    setupFiles: ['@dialpad/dialapp-external-sdk/testing/setup'],
  },
});
