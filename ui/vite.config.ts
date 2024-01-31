import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import eslint from 'vite-plugin-eslint'
import version from 'vite-plugin-package-version'
import svgr from 'vite-plugin-svgr'
import viteTsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  base: '/',
  build: {
    outDir: './build',
  },
  plugins: [
    react(),
    viteTsconfigPaths(),
    svgr({ include: '**/*.svg?react' }),
    eslint({ exclude: ['/virtual:/**', 'node_modules/**'] }),
    version(),
  ],
  server: {
    open: true,
    port: 3000,
    proxy: {
      '/api': {
        target: 'https://api.dev.insectai.org',
        changeOrigin: true,
      },
    },
  },
})
