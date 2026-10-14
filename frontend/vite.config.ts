import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Loopback by default; `BIND_ADDR=0.0.0.0 make frontend` opens it to the LAN.
    host: process.env.BIND_ADDR || '127.0.0.1',
    port: 5173,
    proxy: {
      '/v1': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8100',
        changeOrigin: true,
        // X-Forwarded-Host keeps the UI's host visible to the backend's
        // cross-site check (changeOrigin rewrites Host).
        xfwd: true,
      },
    },
  },
  preview: {
    proxy: {
      '/v1': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8100',
        changeOrigin: true,
        // X-Forwarded-Host keeps the UI's host visible to the backend's
        // cross-site check (changeOrigin rewrites Host).
        xfwd: true,
      },
    },
  },
})
