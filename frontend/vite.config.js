import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-Server auf 5173; /api wird zur Flask-App (Port 5001) geproxyt.
// Dadurch ist alles same-origin -> kein CORS, Session-Cookie funktioniert.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:5001', changeOrigin: true },
    },
  },
})
