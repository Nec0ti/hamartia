import assert from 'node:assert/strict'
import test from 'node:test'
import { contentSecurityPolicy, socialBuildConfiguration, socialProxyTarget } from '../../vite.config.js'

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

test('browser and desktop social flags are independent and default disabled', () => {
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
  assert.equal(socialBuildConfiguration(BROWSER).browserEnabled, true)
  assert.equal(socialBuildConfiguration(BROWSER).desktopEnabled, false)
  assert.equal(socialBuildConfiguration(DESKTOP).browserEnabled, false)
  assert.equal(socialBuildConfiguration(DESKTOP).desktopEnabled, true)
  assert.equal(socialBuildConfiguration({ ...DESKTOP, HAMARTIA_SOCIAL_AGREEMENT_REVIEWED: 'false' }).desktopEnabled, false)
  assert.equal(socialBuildConfiguration({ ...DESKTOP, HAMARTIA_SOCIAL_AGREEMENT_VERSION: '' }).desktopEnabled, false)
  assert.equal(socialBuildConfiguration({ ...BROWSER, VITE_SOCIAL_AGREEMENT_REVIEWED: 'false' }).browserEnabled, false)
  assert.equal(socialBuildConfiguration({ ...DESKTOP, HAMARTIA_SOCIAL_API_ORIGIN: 'http://social.example.test' }).desktopEnabled, false)
  assert.equal(socialBuildConfiguration({ ...BROWSER, VITE_SOCIAL_ENABLED: 'false' }).browserEnabled, false)
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

test('production CSP is strict and injected before scripts; dev CSP adds only emulator/HMR allowances', () => {
  const production = contentSecurityPolicy(false).transformIndexHtml()[0]
  assert.equal(production.injectTo, 'head-prepend')
  assert.match(production.attrs.content, /script-src 'self'/)
  assert.doesNotMatch(production.attrs.content, /unsafe-eval/)
  assert.match(production.attrs.content, /object-src 'none'/)
  assert.match(production.attrs.content, /base-uri 'self'/)
  const development = contentSecurityPolicy(true).transformIndexHtml()[0].attrs.content
  assert.match(development, /127\.0\.0\.1:9099/)
  assert.match(development, /ws:\/\/127\.0\.0\.1:5173/)
})
