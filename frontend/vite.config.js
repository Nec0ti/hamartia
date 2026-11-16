import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import net from 'node:net'

const FIREBASE_AUTH_HOSTS = 'https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://www.googleapis.com https://www.google.com'

function socialProxyTarget(value) {
  const target = new URL(value || 'http://127.0.0.1:8765')
  const ip = target.hostname.startsWith('[') && target.hostname.endsWith(']')
    ? target.hostname.slice(1, -1)
    : target.hostname
  const loopback = net.isIP(ip) === 6 ? ip === '::1' : net.isIP(ip) === 4 && ip.startsWith('127.')
  if (target.username || target.password || target.pathname !== '/' || target.search || target.hash
    || (target.protocol !== 'https:' && !(target.protocol === 'http:' && loopback))) {
    throw new Error('HAMARTIA_SOCIAL_API_TARGET must be an HTTPS origin or a numeric loopback HTTP origin.')
  }
  return target.origin
}

function contentSecurityPolicy() {
  return {
    name: 'hamartia-content-security-policy',
    transformIndexHtml(_html, context) {
      const development = Boolean(context.server)
      const policy = [
        "default-src 'self'",
        development ? "script-src 'self' 'unsafe-inline' 'unsafe-eval'" : "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        `connect-src 'self' ${FIREBASE_AUTH_HOSTS}${development ? ' http://127.0.0.1:9099 http://localhost:9099 ws://127.0.0.1:5173 ws://localhost:5173' : ''}`,
        `frame-src 'self' https://*.firebaseapp.com https://*.web.app https://accounts.google.com${development ? ' http://127.0.0.1:9099 http://localhost:9099' : ''}`,
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
      ].join('; ')
      return [{ tag: 'meta', attrs: { 'http-equiv': 'Content-Security-Policy', content: policy }, injectTo: 'head-prepend' }]
    },
  }
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), contentSecurityPolicy()],
  server: {
    port: 5173,
    proxy: {
      '/social': {
        target: socialProxyTarget(process.env.HAMARTIA_SOCIAL_API_TARGET),
        changeOrigin: true,
      },
      // Dev-mode proxy: forward every non-asset request to the FastAPI
      // backend so the React app can run from a single trusted origin.
      // (Static assets are served by Vite itself and never reach this hook.)
      '*': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
