import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const backend = process.env.PDP_BACKEND_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    // Same-origin in development: no CORS configuration needed on the API.
    proxy: {
      '/api': backend,
      '/static': backend,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
