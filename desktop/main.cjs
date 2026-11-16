const { app, BrowserWindow, dialog, ipcMain, safeStorage, shell } = require('electron')
const { randomBytes, randomUUID } = require('node:crypto')
const { spawn } = require('node:child_process')
const fs = require('node:fs')
const net = require('node:net')
const path = require('node:path')
const { backendInvocation } = require('./backendInvocation.cjs')
const { restoreWithRestart } = require('./restoreFlow.cjs')
const { gracefulStop } = require('./shutdownFlow.cjs')
const { createChatGPT } = require('./chatgpt.cjs')
const { registerChatGPTIpc } = require('./chatgptIpc.cjs')
const { createGoogleDesktopOAuth } = require('./googleDesktopOAuth.cjs')
const { createSocialFirebaseAuth } = require('./socialFirebase.cjs')
const { loadSocialPublicConfig } = require('./socialConfig.cjs')
const { handleSocialDocumentWindowOpen } = require('./socialDocs.cjs')
const { registerSocialIpc } = require('./socialIpc.cjs')
const { probeSafeStorage } = require('./safeStorageSmoke.cjs')
const { getWindowIconPath } = require('./windowIcon.cjs')

const HOST = '127.0.0.1'
const CONTROL_TOKEN = randomBytes(32).toString('hex')
const RESTORE_CHANNEL = 'hamartia:restore-backup'
let safeStorageSmokeMetadata = null
const restoreCopy = {
  en: {
    pickerTitle: 'Select a Hamartia backup',
    pickerButton: 'Select backup',
    confirmTitle: 'Restore Hamartia backup?',
    confirmMessage: 'Replace the current study data with this backup?',
    confirmDetail: 'Hamartia first preserves a snapshot of the current data folder.',
    cancel: 'Cancel',
    restore: 'Restore',
  },
  tr: {
    pickerTitle: 'Hamartia yedeği seç',
    pickerButton: 'Yedeği seç',
    confirmTitle: 'Hamartia yedeği geri yüklensin mi?',
    confirmMessage: 'Mevcut çalışma verileri bu yedekle değiştirilsin mi?',
    confirmDetail: 'Hamartia önce mevcut veri klasörünün bir kopyasını saklar.',
    cancel: 'Vazgeç',
    restore: 'Geri yükle',
  },
}
let backend
let backendUrl
let stoppingBackend = false
let chatgpt
const socialPublicConfig = loadSocialPublicConfig({
  isPackaged: app.isPackaged,
  resourcesPath: process.resourcesPath,
  desktopDir: __dirname,
})
const socialOAuth = createGoogleDesktopOAuth({
  clientId: socialPublicConfig.googleOAuthClientId,
  shell,
})
const socialAuth = createSocialFirebaseAuth({
  environment: {
    HAMARTIA_FIREBASE_API_KEY: socialPublicConfig.firebase?.apiKey,
    HAMARTIA_FIREBASE_AUTH_DOMAIN: socialPublicConfig.firebase?.authDomain,
    HAMARTIA_FIREBASE_PROJECT_ID: socialPublicConfig.firebase?.projectId,
    HAMARTIA_FIREBASE_APP_ID: socialPublicConfig.firebase?.appId,
  },
  oauth: socialOAuth,
})

registerSocialIpc({
  ipcMain,
  auth: socialAuth,
  getBackendUrl: () => backendUrl,
  apiOrigin: socialPublicConfig.socialApiOrigin,
  agreementVersion: socialPublicConfig.agreementVersion,
  allowLoopbackHttp: !app.isPackaged,
})

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

function backendEnvironment(port) {
  const env = {
    ...process.env,
    HAMARTIA_HOST: HOST,
    HAMARTIA_PORT: String(port),
    HAMARTIA_DATA_DIR: path.join(app.getPath('userData'), 'data'),
    HAMARTIA_CONTROL_TOKEN: CONTROL_TOKEN,
  }
  if (!app.isPackaged) env.HAMARTIA_STATIC_DIR = path.resolve(__dirname, '../frontend/dist')
  return env
}

function spawnBackend(args, port) {
  const command = backendInvocation({
    isPackaged: app.isPackaged,
    resourcesPath: process.resourcesPath,
    desktopDir: __dirname,
    platform: process.platform,
    python: process.env.HAMARTIA_PYTHON,
  }, args)
  return spawn(command.command, command.args, {
    cwd: path.resolve(__dirname, '..'),
    env: backendEnvironment(port),
    stdio: 'ignore',
    windowsHide: true,
  })
}

function startBackend(port) {
  return spawnBackend([], port)
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

  const icon = getWindowIconPath({
    platform: process.platform,
    isPackaged: app.isPackaged,
    resourcesPath: process.resourcesPath,
    desktopDir: __dirname,
  })
  const window = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 760,
    minHeight: 600,
    autoHideMenuBar: true,
    ...(icon ? { icon } : {}),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  })

  window.webContents.setWindowOpenHandler((details) => handleSocialDocumentWindowOpen(details, shell))
  window.webContents.on('will-navigate', (event, url) => {
    if (new URL(url).origin !== backendUrl) event.preventDefault()
  })
  await window.loadURL(backendUrl)
  await writeSmokeReadiness(window)
}

async function writeSmokeReadiness(window) {
  const markerPath = process.env.HAMARTIA_ELECTRON_SMOKE_MARKER
  if (!markerPath) return
  let result
  try {
    result = await window.webContents.executeJavaScript(`(async () => {
      const deadline = Date.now() + 20_000
      let last = {}
      while (Date.now() < deadline) {
        let healthStatus = null
        try {
          const health = await fetch('/healthcheck/ready', { signal: AbortSignal.timeout(1000) })
          healthStatus = health.status
        } catch {}
        const headings = [...document.querySelectorAll('h1, h2, h3, h4')].map((item) => item.textContent.trim())
        last = {
          origin: location.origin,
          backendUrl: location.origin,
          language: document.documentElement.lang,
          overviewVisible: headings.includes('Overview'),
          headings,
          healthStatus,
        }
        if (last.language === 'en' && last.overviewVisible && last.healthStatus === 200) return last
        await new Promise((resolve) => setTimeout(resolve, 250))
      }
      throw new Error('Timed out waiting for English Overview and HTTP 200 readiness: ' + JSON.stringify(last))
    })()`)
    if (safeStorageSmokeMetadata) result.safeStorage = safeStorageSmokeMetadata
  } catch (error) {
    result = { error: error.message }
  }
  fs.writeFileSync(markerPath, JSON.stringify(result), 'utf8')
  setImmediate(() => app.quit())
}

function waitForExit(child, timeoutMs = 0) {
  return new Promise((resolve, reject) => {
    if (child.exitCode !== null) return resolve(child.exitCode)
    const timer = timeoutMs > 0 ? setTimeout(() => {
      cleanup()
      reject(new Error('The backend process did not exit in time'))
    }, timeoutMs) : null
    const onExit = (code) => {
      cleanup()
      resolve(code)
    }
    const onError = (error) => {
      cleanup()
      reject(error)
    }
    const cleanup = () => {
      if (timer) clearTimeout(timer)
      child.removeListener('exit', onExit)
      child.removeListener('error', onError)
    }
    child.once('exit', onExit)
    child.once('error', onError)
  })
}

async function stopBackend() {
  const child = backend
  if (!child || child.exitCode !== null) return
  await gracefulStop({
    requestShutdown: async () => fetch(`${backendUrl}/desktop/shutdown`, {
      method: 'POST',
      headers: { 'X-Hamartia-Control-Token': CONTROL_TOKEN },
      signal: AbortSignal.timeout(10_000),
    }),
    waitForExit: () => waitForExit(child),
  })
  if (backend === child) backend = null
}

async function restartBackend(port) {
  if (backend && backend.exitCode === null) {
    try {
      await waitUntilReady(backend, backendUrl)
      return
    } catch (error) {
      if (backend.exitCode === null) throw error
    }
  }
  backend = startBackend(port)
  await waitUntilReady(backend, backendUrl)
}

registerChatGPTIpc({ ipcMain, shell, getBackendUrl: () => backendUrl, chatgpt: { status: (...args) => chatgpt.status(...args), signIn: (...args) => chatgpt.signIn(...args), signOut: (...args) => chatgpt.signOut(...args), forgetAccount: (...args) => chatgpt.forgetAccount(...args), models: (...args) => chatgpt.models(...args), chat: (...args) => chatgpt.chat(...args), cancel: (...args) => chatgpt.cancel(...args) } })

ipcMain.handle(RESTORE_CHANNEL, async (event, language) => {
  try {
    if (!backendUrl || event.senderFrame?.parent !== null || new URL(event.senderFrame.url).origin !== backendUrl) return { status: 'failed' }
  } catch {
    return { status: 'failed' }
  }
  const locale = language === 'tr' ? 'tr' : 'en'
  const copy = restoreCopy[locale]
  const window = BrowserWindow.fromWebContents(event.sender)
  const selected = await dialog.showOpenDialog(window, {
    title: copy.pickerTitle,
    buttonLabel: copy.pickerButton,
    properties: ['openFile'],
    filters: [{ name: 'ZIP backup', extensions: ['zip'] }],
  })
  if (selected.canceled || selected.filePaths.length !== 1) return { status: 'cancelled' }

  const archivePath = selected.filePaths[0]
  if (path.extname(archivePath).toLowerCase() !== '.zip') return { status: 'failed' }
  const confirmation = await dialog.showMessageBox(window, {
    type: 'warning',
    title: copy.confirmTitle,
    message: copy.confirmMessage,
    detail: copy.confirmDetail,
    buttons: [copy.cancel, copy.restore],
    defaultId: 0,
    cancelId: 0,
    noLink: true,
  })
  if (confirmation.response !== 1) return { status: 'cancelled' }

  const port = Number(new URL(backendUrl).port)
  const status = await restoreWithRestart({
    stop: stopBackend,
    restore: async () => {
      const child = spawnBackend(['--restore-backup', archivePath], port)
      return (await waitForExit(child)) === 0 ? 'success' : 'failed'
    },
    restart: () => restartBackend(port),
  })

  if (status !== 'restartFailed') {
    setTimeout(() => {
      if (!event.sender.isDestroyed()) event.sender.reload()
    }, 3000).unref()
  }
  return { status }
})

if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  if (process.env.HAMARTIA_ELECTRON_SMOKE_USER_DATA) {
    app.setPath('userData', process.env.HAMARTIA_ELECTRON_SMOKE_USER_DATA)
  }
  app.on('second-instance', () => {
    const window = BrowserWindow.getAllWindows()[0]
    if (!window) return
    if (window.isMinimized()) window.restore()
    window.focus()
  })

  app.whenReady().then(async () => {
    try {
      chatgpt = createChatGPT({ app, safeStorage, shell, getBackendUrl: () => backendUrl })
      if (process.env.HAMARTIA_ELECTRON_SMOKE_MARKER) {
        try {
          safeStorageSmokeMetadata = await probeSafeStorage({
            safeStorage,
            chatgpt,
            mode: process.env.HAMARTIA_ELECTRON_SMOKE_STORAGE_MODE || 'protected',
            expectedBackend: process.env.HAMARTIA_ELECTRON_SMOKE_EXPECT_BACKEND,
          })
        } catch (error) {
          fs.writeFileSync(process.env.HAMARTIA_ELECTRON_SMOKE_MARKER, JSON.stringify({ error: error.message }), 'utf8')
          app.quit()
          return
        }
      }
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
  socialOAuth.cancel()
  if (!backend || backend.exitCode !== null) return
  event.preventDefault()
  if (stoppingBackend) return
  stoppingBackend = true
  const child = backend
  gracefulStop({
    requestShutdown: async () => fetch(`${backendUrl}/desktop/shutdown`, {
      method: 'POST',
      headers: { 'X-Hamartia-Control-Token': CONTROL_TOKEN },
      signal: AbortSignal.timeout(10_000),
    }),
    waitForExit: () => waitForExit(child, 30_000),
  }).then(() => app.quit()).catch(() => {
    // Forced termination is only a last resort when the user is closing the app.
    if (child.exitCode === null) child.kill()
    app.exit(1)
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
