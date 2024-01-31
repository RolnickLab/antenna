import react from '@vitejs/plugin-react'
import childProcees from 'child_process'
import { defineConfig } from 'vite'
import eslint from 'vite-plugin-eslint'
import svgr from 'vite-plugin-svgr'
import viteTsconfigPaths from 'vite-tsconfig-paths'

const commitHash = childProcees
  .execSync('git rev-parse --short HEAD')
  .toString()

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
  ],
  define: {
    __COMMIT_HASH__: JSON.stringify(commitHash),
  },
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
