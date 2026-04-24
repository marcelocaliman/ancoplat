import react from '@vitejs/plugin-react'
import path from 'node:path'
import { defineConfig } from 'vite'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: '127.0.0.1',
    proxy: {
      // Proxy /api para o backend em localhost:8000; evita CORS em dev.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules')) {
            if (id.includes('plotly.js') || id.includes('react-plotly'))
              return 'plotly-vendor'
            if (id.includes('@radix-ui')) return 'radix-vendor'
            if (
              id.includes('react-hook-form') ||
              id.includes('@hookform') ||
              id.includes('/zod/')
            )
              return 'form-vendor'
            if (id.includes('@tanstack') || id.includes('/axios/'))
              return 'query-vendor'
            if (id.includes('/react/') || id.includes('react-dom') || id.includes('react-router'))
              return 'react-vendor'
          }
          return undefined
        },
      },
    },
  },
})
