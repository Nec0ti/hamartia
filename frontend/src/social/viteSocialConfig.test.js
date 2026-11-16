import assert from 'node:assert/strict'
import test from 'node:test'
import { contentSecurityPolicy, developmentApiOrigin, socialBuildConfiguration, socialProxyTarget } from '../../vite.config.js'

const BROWSER = {
  VITE_SOCIAL_ENABLED: 'true',
  VITE_FIREBASE_API_KEY: 'public-key',
  VITE_FIREBASE_AUTH_DOMAIN: 'social-test.firebaseapp.com',
  VITE_FIREBASE_PROJECT_ID: 'social-test',
  VITE_FIREBASE_APP_ID: '1:123:web:abc',
  HAMARTIA_SOCIAL_API_TARGET: 'http://127.0.0.1:8765',
  VITE_SOCIAL_AGREEMENT_REVIEWED: 'true',
  VITE_SOCIAL_AGREEMENT_VERSION: 'v1-reviewed-test',
}

const DESKTOP = {
  HAMARTIA_FIREBASE_API_KEY: 'public-key',
  HAMARTIA_FIREBASE_AUTH_DOMAIN: 'social-test.firebaseapp.com',
  HAMARTIA_FIREBASE_PROJECT_ID: 'social-test',
  HAMARTIA_FIREBASE_APP_ID: '1:123:web:abc',
  HAMARTIA_GOOGLE_OAUTH_CLIENT_ID: '1234567890-test.apps.googleusercontent.com',
  HAMARTIA_SOCIAL_API_ORIGIN: 'https://social.example.test',
  HAMARTIA_SOCIAL_AGREEMENT_REVIEWED: 'true',
  HAMARTIA_SOCIAL_AGREEMENT_VERSION: 'v1-reviewed-test',
}

test('browser social is development-server-only and desktop flags remain independent', () => {
  assert.deepEqual(socialBuildConfiguration({}), {
    browserEnabled: false,
    desktopEnabled: false,
    desktopPublicConfig: {
      firebase: { apiKey: '', authDomain: '', projectId: '', appId: '' },
      googleOAuthClientId: '',
      socialApiOrigin: '',
      agreementVersion: '',
    },
  })
  assert.equal(socialBuildConfiguration(BROWSER).browserEnabled, false, 'production builds never enable the relative dev-proxy client')
  assert.equal(socialBuildConfiguration(BROWSER, true).browserEnabled, true)
  assert.equal(socialBuildConfiguration(BROWSER).desktopEnabled, false)
  assert.equal(socialBuildConfiguration(DESKTOP).browserEnabled, false)
  assert.equal(socialBuildConfiguration(DESKTOP).desktopEnabled, true)
  assert.equal(socialBuildConfiguration({ ...DESKTOP, HAMARTIA_SOCIAL_AGREEMENT_REVIEWED: 'false' }).desktopEnabled, false)
  assert.equal(socialBuildConfiguration({ ...DESKTOP, HAMARTIA_SOCIAL_AGREEMENT_VERSION: '' }).desktopEnabled, false)
  assert.equal(socialBuildConfiguration({ ...BROWSER, VITE_SOCIAL_AGREEMENT_REVIEWED: 'false' }).browserEnabled, false)
  assert.equal(socialBuildConfiguration({ ...DESKTOP, HAMARTIA_SOCIAL_API_ORIGIN: 'http://social.example.test' }).desktopEnabled, false)
  assert.equal(socialBuildConfiguration({ ...BROWSER, VITE_SOCIAL_ENABLED: 'false' }, true).browserEnabled, false)
  assert.equal(socialBuildConfiguration({ ...BROWSER, VITE_SOCIAL_AGREEMENT_REVIEWED: 'false' }, true).browserEnabled, false)
})

test('generated desktop config includes only public client settings and no client secret', () => {
  const config = socialBuildConfiguration(DESKTOP).desktopPublicConfig
  assert.deepEqual(Object.keys(config).sort(), ['agreementVersion', 'firebase', 'googleOAuthClientId', 'socialApiOrigin'])
  assert.equal('clientSecret' in config, false)
  assert.equal('client_secret' in config, false)
  assert.equal(config.googleOAuthClientId, DESKTOP.HAMARTIA_GOOGLE_OAUTH_CLIENT_ID)
  assert.equal(config.agreementVersion, 'v1-reviewed-test')
})

test('Vite social proxy accepts HTTPS or numeric loopback origins and rejects aliases or paths', () => {
  assert.equal(socialProxyTarget(), 'http://127.0.0.1:8765')
  assert.equal(socialProxyTarget('https://social.example.test'), 'https://social.example.test')
  assert.throws(() => socialProxyTarget('http://localhost:8765'), /numeric loopback/)
  assert.throws(() => socialProxyTarget('http://social.example.test'), /numeric loopback/)
  assert.throws(() => socialProxyTarget('http://127.0.0.1:8765/social'), /numeric loopback/)
})

test('production CSP stays strict and dev CSP allows only its validated API origin plus emulator/HMR', () => {
  const production = contentSecurityPolicy(false).transformIndexHtml()[0]
  assert.equal(production.injectTo, 'head-prepend')
  assert.match(production.attrs.content, /script-src 'self'/)
  assert.doesNotMatch(production.attrs.content, /unsafe-eval/)
  assert.match(production.attrs.content, /object-src 'none'/)
  assert.match(production.attrs.content, /base-uri 'self'/)
  const development = contentSecurityPolicy(true, 'http://127.0.0.1:8000').transformIndexHtml()[0].attrs.content
  assert.match(development, /127\.0\.0\.1:9099/)
  assert.match(development, /ws:\/\/127\.0\.0\.1:5173/)
  assert.match(development, /connect-src[^;]*http:\/\/127\.0\.0\.1:8000/)
  const defaultDevelopment = contentSecurityPolicy(true).transformIndexHtml()[0].attrs.content
  assert.match(defaultDevelopment, /connect-src[^;]*http:\/\/localhost:8000/)
  assert.match(defaultDevelopment, /img-src[^;]*http:\/\/localhost:8000/)
  const httpsDevelopment = contentSecurityPolicy(true, 'https://api.example.test').transformIndexHtml()[0].attrs.content
  assert.match(httpsDevelopment, /connect-src[^;]*https:\/\/api\.example\.test/)
  assert.match(httpsDevelopment, /img-src[^;]*https:\/\/api\.example\.test/)
  assert.doesNotMatch(httpsDevelopment, /https:\/\/unrelated\.example\.test/)
  const httpsProduction = contentSecurityPolicy(false, 'https://api.example.test').transformIndexHtml()[0].attrs.content
  assert.doesNotMatch(httpsProduction, /https:\/\/api\.example\.test/)
  assert.doesNotMatch(httpsProduction, /img-src[^;]*https:\/\/api\.example\.test/)
  assert.doesNotMatch(httpsProduction, /localhost:8000/)
  assert.doesNotMatch(production.attrs.content, /127\.0\.0\.1:8000/)
  assert.equal(developmentApiOrigin(), 'http://localhost:8000')
  assert.equal(developmentApiOrigin('https://api.example.test'), 'https://api.example.test')
  assert.throws(() => developmentApiOrigin('http://api.example.test'), /VITE_API_BASE/)
  assert.throws(() => developmentApiOrigin('http://127.0.0.1:8000/social'), /VITE_API_BASE/)
  assert.throws(() => developmentApiOrigin('https://user:password@api.example.test'), /VITE_API_BASE/)
  assert.throws(() => developmentApiOrigin('https://api.example.test?token=value'), /VITE_API_BASE/)
  assert.throws(() => developmentApiOrigin('https://api.example.test#fragment'), /VITE_API_BASE/)
})
