import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import net from 'node:net'

const FIREBASE_AUTH_HOSTS = 'https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://www.googleapis.com https://www.google.com'

export function socialProxyTarget(value) {
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
        `connect-src 'self' ${FIREBASE_AUTH_HOSTS}${devApi}${development ? ' http://127.0.0.1:9099 http://localhost:9099 ws://127.0.0.1:5173 ws://localhost:5173' : ''}`,
        `frame-src 'self' https://*.firebaseapp.com https://*.web.app https://accounts.google.com${development ? ' http://127.0.0.1:9099 http://localhost:9099' : ''}`,
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
      ].join('; ')
      return [{ tag: 'meta', attrs: { 'http-equiv': 'Content-Security-Policy', content: policy }, injectTo: 'head-prepend' }]
    },
  }
}

function desktopSocialConfig(environment) {
  const firebase = {
    apiKey: environment.HAMARTIA_FIREBASE_API_KEY || '',
    authDomain: environment.HAMARTIA_FIREBASE_AUTH_DOMAIN || '',
    projectId: environment.HAMARTIA_FIREBASE_PROJECT_ID || '',
    appId: environment.HAMARTIA_FIREBASE_APP_ID || '',
  }
  const googleOAuthClientId = environment.HAMARTIA_GOOGLE_OAUTH_CLIENT_ID || ''
  const socialApiOrigin = environment.HAMARTIA_SOCIAL_API_ORIGIN || ''
  const agreementVersion = environment.HAMARTIA_SOCIAL_AGREEMENT_VERSION || ''
  const agreementReviewed = environment.HAMARTIA_SOCIAL_AGREEMENT_REVIEWED === 'true'
  const apiOriginIsHttps = (() => {
    try {
      const url = new URL(socialApiOrigin)
      return url.protocol === 'https:' && !url.username && !url.password && url.pathname === '/' && !url.search && !url.hash
    } catch {
      return false
    }
  })()
  const configured = Object.values(firebase).every((value) => value.trim())
    && /^[A-Za-z0-9._-]{10,255}\.apps\.googleusercontent\.com$/.test(googleOAuthClientId)
    && apiOriginIsHttps
    && agreementReviewed
    && /^[A-Za-z0-9._-]{1,40}$/.test(agreementVersion)
  return { configured, firebase, googleOAuthClientId, socialApiOrigin, agreementVersion: configured ? agreementVersion : '' }
}

export function socialBuildConfiguration(environment, developmentServer = false) {
  const firebaseConfigured = [
    'VITE_FIREBASE_API_KEY',
    'VITE_FIREBASE_AUTH_DOMAIN',
    'VITE_FIREBASE_PROJECT_ID',
    'VITE_FIREBASE_APP_ID',
  ].every((key) => Boolean(environment[key]?.trim()))
  const browserEnabled = developmentServer
    && environment.VITE_SOCIAL_ENABLED === 'true'
    && firebaseConfigured
    && Boolean(environment.HAMARTIA_SOCIAL_API_TARGET)
    && environment.VITE_SOCIAL_AGREEMENT_REVIEWED === 'true'
    && /^[A-Za-z0-9._-]{1,40}$/.test(environment.VITE_SOCIAL_AGREEMENT_VERSION || '')
  const desktop = desktopSocialConfig(environment)
  return {
    browserEnabled,
    desktopEnabled: desktop.configured,
    desktopPublicConfig: {
      firebase: desktop.firebase,
      googleOAuthClientId: desktop.googleOAuthClientId,
      socialApiOrigin: desktop.socialApiOrigin,
      agreementVersion: desktop.agreementVersion,
    },
  }
}

function publicConfigAsset(config) {
  return {
    name: 'hamartia-social-public-config',
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'social-public-config.json',
        source: JSON.stringify(config, null, 2),
      })
    },
  }
}

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const socialConfig = socialBuildConfiguration(env, command === 'serve')

  return {
    define: {
      __HAMARTIA_BROWSER_SOCIAL_ENABLED__: JSON.stringify(socialConfig.browserEnabled),
      __HAMARTIA_DESKTOP_SOCIAL_ENABLED__: JSON.stringify(socialConfig.desktopEnabled),
      __HAMARTIA_BROWSER_AGREEMENT_VERSION__: JSON.stringify(env.VITE_SOCIAL_AGREEMENT_REVIEWED === 'true' ? env.VITE_SOCIAL_AGREEMENT_VERSION || '' : ''),
      __HAMARTIA_DESKTOP_AGREEMENT_VERSION__: JSON.stringify(socialConfig.desktopPublicConfig.agreementVersion),
    },
    plugins: [react(), contentSecurityPolicy(command === 'serve', env.VITE_API_BASE), publicConfigAsset(socialConfig.desktopPublicConfig)],
    server: {
      port: 5173,
      proxy: {
        '/social': {
          target: socialProxyTarget(env.HAMARTIA_SOCIAL_API_TARGET),
          changeOrigin: true,
        },
        // Keep the existing local-study API proxy on one same-origin path.
        '*': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
