const path = require('node:path')

function getWindowIconPath({ platform, isPackaged, resourcesPath, desktopDir }) {
  if (platform === 'win32') {
    return isPackaged
      ? path.join(resourcesPath, 'icons', 'hamartia.ico')
      : path.join(desktopDir, 'build', 'icon.ico')
  }
  if (platform === 'linux') {
    return isPackaged
      ? path.join(resourcesPath, 'icons', 'hamartia.png')
      : path.join(desktopDir, 'build', 'icons', '512x512.png')
  }
  return undefined
}

module.exports = { getWindowIconPath }
