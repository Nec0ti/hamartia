const path = require('node:path')

function backendInvocation({ isPackaged, resourcesPath, desktopDir, platform, python }, args = []) {
  const pathApi = platform === 'win32' ? path.win32 : path
  if (isPackaged) {
    const executable = `hamartia-backend${platform === 'win32' ? '.exe' : ''}`
    return {
      command: pathApi.join(resourcesPath, 'backend', 'hamartia-backend', executable),
      args,
    }
  }

  return {
    command: python || (platform === 'win32' ? 'python' : 'python3'),
    args: [pathApi.resolve(desktopDir, '../backend/desktop_server.py'), ...args],
  }
}

module.exports = { backendInvocation }
