import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import svgr from 'vite-plugin-svgr'
import viteTsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  base: '/',
  plugins: [react(), viteTsconfigPaths(), svgr({ include: '**/*.svg?react' })],
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
