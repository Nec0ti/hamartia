import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Dev-mode proxy: forward every non-asset request to the FastAPI
      // backend so the React app can run from a single trusted origin.
      // (Static assets are served by Vite itself and never reach this hook.)
      '*': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
