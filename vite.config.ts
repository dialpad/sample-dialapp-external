import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vitest/config';

// The backend renders the page HTML. In production it reads dist/.vite/manifest.json for the
// built entry; in local mode it points script tags at this dev server.
export default defineConfig({
  plugins: [vue()],
  server: { port: 5173, strictPort: true },
  build: {
    manifest: true,
    rollupOptions: { input: 'src/main.ts' },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts'],
  },
});
