const assert = require('node:assert/strict')
const test = require('node:test')
const { EMPTY_SOCIAL_CONFIG, loadSocialPublicConfig, validateSocialPublicConfig } = require('../socialConfig.cjs')

const CONFIG = {
  firebase: {
    apiKey: 'public-api-key',
    authDomain: 'social-test.firebaseapp.com',
    projectId: 'social-test',
    appId: '1:123:web:abc',
  },
  googleOAuthClientId: '1234567890-test.apps.googleusercontent.com',
  socialApiOrigin: 'https://social.example.test',
  agreementVersion: 'v1-reviewed-test',
}

test('desktop public social config requires complete Firebase, OAuth, and HTTPS API settings', () => {
  assert.deepEqual(validateSocialPublicConfig(null), EMPTY_SOCIAL_CONFIG)
  assert.deepEqual(validateSocialPublicConfig({ ...CONFIG, socialApiOrigin: 'http://social.example.test' }), EMPTY_SOCIAL_CONFIG)
  assert.deepEqual(validateSocialPublicConfig({ ...CONFIG, googleOAuthClientId: '' }), EMPTY_SOCIAL_CONFIG)
  assert.deepEqual(validateSocialPublicConfig({ ...CONFIG, firebase: { ...CONFIG.firebase, appId: '' } }), EMPTY_SOCIAL_CONFIG)
  assert.deepEqual(validateSocialPublicConfig({ ...CONFIG, agreementVersion: '' }), EMPTY_SOCIAL_CONFIG)
})

test('desktop config loader reads only the generated public resource and ignores unrecognized fields', () => {
  const files = []
  const loaded = loadSocialPublicConfig({
    isPackaged: true,
    resourcesPath: '/app/resources',
    desktopDir: '/checkout/desktop',
    readFile: (file, encoding) => {
      files.push([file, encoding])
      return JSON.stringify({ ...CONFIG, client_secret: 'must be ignored' })
    },
  })
  assert.deepEqual(files, [['/app/resources/social-public-config.json', 'utf8']])
  assert.deepEqual(loaded, CONFIG)
  assert.equal('client_secret' in loaded, false)
})

test('missing generated config disables desktop social instead of falling back to runtime environment', () => {
  const loaded = loadSocialPublicConfig({
    isPackaged: false,
    resourcesPath: '',
    desktopDir: '/checkout/desktop',
    readFile: () => { throw new Error('file missing') },
  })
  assert.deepEqual(loaded, EMPTY_SOCIAL_CONFIG)
})
