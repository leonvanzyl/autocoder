import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// Backend port - can be overridden via AUTOCODER_UI_PORT or VITE_API_PORT env vars
const apiPort = process.env.AUTOCODER_UI_PORT || process.env.VITE_API_PORT || '8888'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          const norm = id.replace(/\\\\/g, '/')

          if (norm.includes('/react/') || norm.includes('/react-dom/')) return 'vendor-react'
          if (norm.includes('@tanstack/react-query')) return 'vendor-query'
          if (norm.includes('@xterm') || norm.includes('/xterm')) return 'vendor-xterm'
          if (norm.includes('@radix-ui') || norm.includes('lucide-react')) return 'vendor-ui'
          if (norm.includes('canvas-confetti')) return 'vendor-misc'

          return 'vendor'
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${apiPort}`,
        changeOrigin: true,
      },
      '/ws': {
        target: `ws://127.0.0.1:${apiPort}`,
        ws: true,
      },
    },
  },
})
