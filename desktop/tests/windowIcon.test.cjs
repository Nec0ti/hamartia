const assert = require('node:assert/strict')
const path = require('node:path')
const test = require('node:test')
const { getWindowIconPath } = require('../windowIcon.cjs')

const desktopDir = '/repo/desktop'
const resourcesPath = '/app/resources'

test('development window uses platform-specific source icon', () => {
  assert.equal(getWindowIconPath({ platform: 'win32', isPackaged: false, desktopDir }), path.join(desktopDir, 'build/icon.ico'))
  assert.equal(getWindowIconPath({ platform: 'linux', isPackaged: false, desktopDir }), path.join(desktopDir, 'build/icons/512x512.png'))
})

test('packaged window uses platform-specific copied resource icon', () => {
  assert.equal(getWindowIconPath({ platform: 'win32', isPackaged: true, resourcesPath, desktopDir }), path.join(resourcesPath, 'icons/hamartia.ico'))
  assert.equal(getWindowIconPath({ platform: 'linux', isPackaged: true, resourcesPath, desktopDir }), path.join(resourcesPath, 'icons/hamartia.png'))
})

test('unsupported platforms do not receive a Windows or Linux window icon', () => {
  assert.equal(getWindowIconPath({ platform: 'darwin', isPackaged: true, resourcesPath, desktopDir }), undefined)
})
