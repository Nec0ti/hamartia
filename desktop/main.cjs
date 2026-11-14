const { app, BrowserWindow, dialog } = require('electron')
const { spawn } = require('node:child_process')
const net = require('node:net')
const path = require('node:path')

const HOST = '127.0.0.1'
let backend
let backendUrl
let stoppingBackend = false

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(0, HOST, () => {
      const { port } = server.address()
      server.close((error) => error ? reject(error) : resolve(port))
    })
  })
}

function startBackend(port) {
  const env = {
    ...process.env,
    HAMARTIA_HOST: HOST,
    HAMARTIA_PORT: String(port),
    HAMARTIA_DATA_DIR: path.join(app.getPath('userData'), 'data'),
  }

  if (app.isPackaged) {
    const executable = path.join(
      process.resourcesPath,
      'backend',
      'hamartia-backend',
      `hamartia-backend${process.platform === 'win32' ? '.exe' : ''}`,
    )
    return spawn(executable, [], { env, stdio: 'ignore', windowsHide: true })
  }

  env.HAMARTIA_STATIC_DIR = path.resolve(__dirname, '../frontend/dist')
  const python = process.env.HAMARTIA_PYTHON || (process.platform === 'win32' ? 'python' : 'python3')
  return spawn(python, [path.resolve(__dirname, '../backend/desktop_server.py')], {
    cwd: path.resolve(__dirname, '..'),
    env,
    stdio: 'ignore',
    windowsHide: true,
  })
}

async function waitUntilReady(child, url) {
  const deadline = Date.now() + 30_000
  let spawnError
  child.once('error', (error) => { spawnError = error })

  while (Date.now() < deadline) {
    if (spawnError) throw spawnError
    if (child.exitCode !== null) throw new Error(`Backend exited with code ${child.exitCode}`)
    try {
      const response = await fetch(`${url}/healthcheck/ready`, { signal: AbortSignal.timeout(1000) })
      if (response.ok) return
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 200))
  }

  throw new Error('Timed out waiting for the local backend')
}

async function openWindow() {
  if (!backendUrl || (backend && backend.exitCode !== null)) {
    const port = await freePort()
    backendUrl = `http://${HOST}:${port}`
    backend = startBackend(port)
    await waitUntilReady(backend, backendUrl)
  }

  const window = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 760,
    minHeight: 600,
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  window.webContents.on('will-navigate', (event, url) => {
    if (new URL(url).origin !== backendUrl) event.preventDefault()
  })
  await window.loadURL(backendUrl)
}

if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => {
    const window = BrowserWindow.getAllWindows()[0]
    if (!window) return
    if (window.isMinimized()) window.restore()
    window.focus()
  })

  app.whenReady().then(async () => {
    try {
      await openWindow()
    } catch (error) {
      dialog.showErrorBox('Hamartia could not start', error.message)
      app.quit()
    }
  })
}

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0 && backendUrl) {
    openWindow().catch((error) => dialog.showErrorBox('Hamartia could not start', error.message))
  }
})

app.on('before-quit', (event) => {
  if (!backend || backend.exitCode !== null) return
  event.preventDefault()
  if (stoppingBackend) return
  stoppingBackend = true
  backend.kill()
  backend.once('exit', () => app.quit())
  setTimeout(() => app.exit(1), 3000).unref()
})

process.on('exit', () => backend?.kill())

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
