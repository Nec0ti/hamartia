const assert = require('node:assert/strict')
const test = require('node:test')
const { handleSocialDocumentWindowOpen, isAllowedSocialDocumentUrl } = require('../socialDocs.cjs')

test('only the four exact English and Turkish social legal document URLs may open externally', () => {
  for (const url of [
    'https://nec0ti.github.io/hamartia/user-agreement-v0.1-draft.html',
    'https://nec0ti.github.io/hamartia/tr/user-agreement-v0.1-draft.html',
    'https://nec0ti.github.io/hamartia/privacy-and-consent/',
    'https://nec0ti.github.io/hamartia/tr/privacy-and-consent/',
  ]) assert.equal(isAllowedSocialDocumentUrl(url), true, url)

  for (const url of [
    'https://attacker.example/hamartia/privacy-and-consent/',
    'https://nec0ti.github.io/hamartia/other-page/',
    'https://nec0ti.github.io/hamartia/privacy-and-consent/?redirect=https://attacker.example',
    'https://nec0ti.github.io/hamartia/privacy-and-consent/#external',
    'http://nec0ti.github.io/hamartia/privacy-and-consent/',
    'https://nec0ti.github.io.attacker.example/hamartia/privacy-and-consent/',
  ]) assert.equal(isAllowedSocialDocumentUrl(url), false, url)
})

test('Electron denies every new window and opens only allowlisted legal documents externally', async () => {
  const opened = []
  const shell = { openExternal: async (url) => opened.push(url) }
  const allowed = 'https://nec0ti.github.io/hamartia/user-agreement-v0.1-draft.html'
  const attacker = 'https://attacker.example/hamartia/user-agreement-v0.1-draft.html'
  assert.deepEqual(handleSocialDocumentWindowOpen({ url: allowed }, shell), { action: 'deny' })
  assert.deepEqual(handleSocialDocumentWindowOpen({ url: attacker }, shell), { action: 'deny' })
  await new Promise((resolve) => setImmediate(resolve))
  assert.deepEqual(opened, [allowed])
})
