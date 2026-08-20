import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The proxy is what fixes the two networking symptoms from the logs:
//
//  * POST to .../-5173.app.github.dev/api/ingest returning 500 -- Vite had no
//    route for /api and no proxy, so it errored on its own.
//  * 401 Unauthorized after restarting uvicorn -- Codespaces resets forwarded
//    port visibility to Private, and its auth proxy rejects cross-port fetches.
//
// Proxying keeps every request on origin 5173. Port 8000 can stay Private, and
// you never hardcode a Codespaces hostname into the frontend again.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // Ingestion polls are short, but keep the socket generous for the upload.
        timeout: 120_000,
      },
    },
  },
});
