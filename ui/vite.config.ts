import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import eslint from 'vite-plugin-eslint'
import svgr from 'vite-plugin-svgr'
import viteTsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  base: '/',
  build: {
    modulePreload: {
      resolveDependencies: () => {
        return []
      },
    },
    outDir: './build',
    rollupOptions: {
      output: {
        sourcemap: false,
        manualChunks: {
          plotly: ['react-plotly.js'],
        },
      },
    },
  },
  plugins: [
    react(),
    viteTsconfigPaths(),
    svgr({ include: '**/*.svg?react' }),
    eslint({ exclude: ['/virtual:/**', 'node_modules/**'] }),
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
