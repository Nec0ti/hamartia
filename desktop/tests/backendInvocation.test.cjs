const assert = require('node:assert/strict')
const test = require('node:test')
const { backendInvocation } = require('../backendInvocation.cjs')

test('packaged sidecar gets restore arguments without shell parsing', () => {
  assert.deepEqual(backendInvocation({
    isPackaged: true,
    resourcesPath: '/opt/Hamartia/resources',
    desktopDir: '/repo/desktop',
    platform: 'linux',
  }, ['--restore-backup', '/tmp/my backup.zip']), {
    command: '/opt/Hamartia/resources/backend/hamartia-backend/hamartia-backend',
    args: ['--restore-backup', '/tmp/my backup.zip'],
  })
})

test('Windows uses the bundled executable suffix and path separators', () => {
  assert.deepEqual(backendInvocation({
    isPackaged: true,
    resourcesPath: 'C:\\Program Files\\Hamartia\\resources',
    desktopDir: 'C:\\repo\\desktop',
    platform: 'win32',
  }), {
    command: 'C:\\Program Files\\Hamartia\\resources\\backend\\hamartia-backend\\hamartia-backend.exe',
    args: [],
  })
})

test('source mode invokes the Python entry point and passes the archive path as one argument', () => {
  assert.deepEqual(backendInvocation({
    isPackaged: false,
    desktopDir: '/repo/desktop',
    platform: 'linux',
    python: '/venv/bin/python',
  }, ['--restore-backup', '/tmp/my backup.zip']), {
    command: '/venv/bin/python',
    args: ['/repo/backend/desktop_server.py', '--restore-backup', '/tmp/my backup.zip'],
  })
})
