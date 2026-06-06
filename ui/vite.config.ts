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

  // Parse a comma-separated list of hostnames into the array Vite expects for
  // `allowedHosts`. Empty/whitespace entries (e.g. a trailing comma) are
  // dropped. Returns undefined when nothing is configured so Vite keeps its
  // default localhost-only behaviour.
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
      // Hosts allowed when serving the dev server (`vite` / `yarn start`)
      // behind a reverse proxy or on a non-localhost hostname (e.g. a
      // Tailscale name). Comma-separated; unset keeps Vite's localhost default.
      allowedHosts: parseAllowedHosts(env.DEV_ALLOWED_HOSTS),
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
      // Hosts allowed when serving the built app with `vite preview` behind a
      // reverse proxy (e.g. a hosted preview deployment). Comma-separated.
      // When unset, Vite's default localhost-only behaviour is preserved, so
      // local development is unaffected.
      allowedHosts: parseAllowedHosts(env.PREVIEW_ALLOWED_HOSTS),
    },
  }
})
