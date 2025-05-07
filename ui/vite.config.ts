import react from '@vitejs/plugin-react'
import childProcess from 'child_process'
import { defineConfig, loadEnv } from 'vite'
import eslint from 'vite-plugin-eslint'
import svgr from 'vite-plugin-svgr'
import viteTsconfigPaths from 'vite-tsconfig-paths'

let commitHash: string

try {
    commitHash = childProcess
        .execSync('git rev-parse --short HEAD')
        .toString()
} catch (err) {
    commitHash = 'Local docker image - please ensure this is latest version'
}

export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  // Set the third parameter to '' to load all env regardless of the `VITE_` prefix.
  const env = loadEnv(mode, process.cwd(), '')

  return {
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
    assetsInclude: ['**/*.md'],
    define: {
      __COMMIT_HASH__: JSON.stringify(commitHash),
    },
    server: {
      open: true,
      port: 3000,
      proxy: {
        '/api': {
          target: env.API_PROXY_TARGET || 'http://localhost:8000',
          changeOrigin: true,
        },
        '/media': {
          target: env.API_PROXY_TARGET || 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
