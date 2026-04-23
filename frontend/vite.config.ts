import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    proxy: {
      // In dev, forward /api/* to the local FastAPI server
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // 5-minute timeout — meeting transcription + summarization can take 2-3 min
        proxyTimeout: 300_000,
        timeout: 300_000,
      },
    },
  },
})
