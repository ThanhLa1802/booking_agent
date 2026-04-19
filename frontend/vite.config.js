import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/api/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    alias: [
      {
        // Redirect ALL MUI icon imports (barrel & sub-path) to a null stub in test env
        find: /^@mui\/icons-material(\/.*)?$/,
        replacement: path.resolve(__dirname, 'src/test/mocks/muiIconMock.jsx'),
      },
    ],
  },
})
