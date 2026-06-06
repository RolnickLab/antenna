import react from '@vitejs/plugin-react'
import childProcess from 'child_process'
import { defineConfig, loadEnv } from 'vite'
import eslint from 'vite-plugin-eslint'
import svgr from 'vite-plugin-svgr'
import viteTsconfigPaths from 'vite-tsconfig-paths'
import { cssVarsPlugin } from './src/nova-ui-kit/plugins/cssVarsPlugin'

let temporaryCommitHash: string
try {
  temporaryCommitHash = childProcess
    .execSync('git rev-parse --short HEAD')
    .toString()
} catch (error) {
  console.warn('Could not obtain git commit hash:', error)
  temporaryCommitHash = 'unknown' // Fallback value if git command fails
}

const commitHash = temporaryCommitHash

export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  // Set the third parameter to '' to load all env regardless of the `VITE_` prefix.
  const env = loadEnv(mode, process.cwd(), '')

  // UI_ALLOWED_HOSTS declares the hostnames both Vite servers accept when the
  // app is reached on a non-localhost host (a reverse proxy, or a Tailscale
  // name): the dev server (`vite` / `yarn start`, via `server.allowedHosts`)
  // and the preview server (`vite preview`, via `preview.allowedHosts`). A
  // container only runs one of those, so a single variable covers both.
  //
  // Parse a comma-separated list into the array Vite expects. Empty/whitespace
  // entries (e.g. a trailing comma) are dropped. Returns undefined when nothing
  // is configured so Vite keeps its default localhost-only behaviour.
  const parseAllowedHosts = (value?: string) => {
    const hosts = value
      ?.split(',')
      .map((host) => host.trim())
      .filter(Boolean)
    return hosts && hosts.length > 0 ? hosts : undefined
  }

  return {
    assetsInclude: ['**/*.md'],
    base: '/',
    build: {
      outDir: './build',
    },
    css: {
      preprocessorOptions: {
        scss: {
          additionalData: `@use '/src/nova-ui-kit/mixins.scss' as *;`,
        },
      },
    },
    define: {
      __COMMIT_HASH__: JSON.stringify(commitHash),
    },
    plugins: [
      cssVarsPlugin(),
      react(),
      viteTsconfigPaths(),
      svgr({ include: '**/*.svg?react' }),
      eslint({ exclude: ['/virtual:/**', 'node_modules/**'] }),
    ],
    server: {
      open: true,
      port: 3000,
      allowedHosts: parseAllowedHosts(env.UI_ALLOWED_HOSTS),
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
    preview: {
      allowedHosts: parseAllowedHosts(env.UI_ALLOWED_HOSTS),
    },
  }
})
