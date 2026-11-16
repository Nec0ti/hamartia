import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import net from 'node:net'

export function developmentApiOrigin(value) {
  const configured = value?.trim() || 'http://localhost:8000'
  const url = new URL(configured)
  const host = url.hostname.startsWith('[') && url.hostname.endsWith(']')
    ? url.hostname.slice(1, -1)
    : url.hostname
  const numericLoopback = net.isIP(host) === 6 ? host === '::1' : net.isIP(host) === 4 && host.startsWith('127.')
  const loopbackName = host === 'localhost'
  const validOrigin = !url.username && !url.password && url.pathname === '/' && !url.search && !url.hash
  if (!validOrigin || !(url.protocol === 'https:' || (url.protocol === 'http:' && (numericLoopback || loopbackName)))) {
    throw new Error('VITE_API_BASE must be an HTTPS origin or a loopback HTTP origin in development.')
  }
  return url.origin
}

export function contentSecurityPolicy(development, apiBase) {
  const devApi = development ? ` ${developmentApiOrigin(apiBase)}` : ''
  return {
    name: 'hamartia-content-security-policy',
    transformIndexHtml() {
      const policy = [
        "default-src 'self'",
        development ? "script-src 'self' 'unsafe-inline' 'unsafe-eval'" : "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        `img-src 'self' data: blob:${devApi}`,
        "font-src 'self' data:",
        `connect-src 'self'${devApi}${development ? ' ws://127.0.0.1:5173 ws://localhost:5173' : ''}`,
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
      ].join('; ')
      return [{ tag: 'meta', attrs: { 'http-equiv': 'Content-Security-Policy', content: policy }, injectTo: 'head-prepend' }]
    },
  }
}

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react(), contentSecurityPolicy(command === 'serve', env.VITE_API_BASE)],
    server: {
      port: 5173,
      proxy: {
        // Keep the existing local-study API proxy on one same-origin path.
        '*': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
