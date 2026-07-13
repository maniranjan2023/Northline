import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        timeout: 0,
        proxyTimeout: 0,
        configure: (proxy) => {
          proxy.on('error', (err, _req, res) => {
            const refused = err.message.includes('ECONNREFUSED')
            if (res && 'writeHead' in res && !res.headersSent) {
              res.writeHead(502, { 'Content-Type': 'application/json' })
              res.end(
                JSON.stringify({
                  detail: refused
                    ? 'Backend is starting on port 8000. Retrying…'
                    : 'Backend unreachable on port 8000. Run backend/stop.ps1 then backend/start.ps1',
                }),
              )
            }
            if (!refused) {
              console.error('[vite] API proxy error:', err.message)
            }
          })
        },
      },
    },
  },
})
