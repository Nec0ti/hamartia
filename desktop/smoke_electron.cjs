const assert = require('node:assert/strict')
const { spawn } = require('node:child_process')
const fsSync = require('node:fs')
const fs = require('node:fs/promises')
const os = require('node:os')
const path = require('node:path')

const appTarget = path.resolve(process.argv[2] || '')
const timeoutMs = Number(process.env.HAMARTIA_ELECTRON_SMOKE_TIMEOUT_MS || 90_000)

async function resolveAppTarget(target) {
  const stat = await fs.stat(target)
  if (stat.isFile()) return { executable: target, cwd: path.dirname(target) }
  assert.ok(stat.isDirectory(), `Expected an unpacked directory or executable file: ${target}`)
  await fs.access(path.join(target, 'resources', 'app.asar'))
  const names = process.platform === 'win32'
    ? ['Hamartia.exe', 'hamartia-desktop.exe']
    : process.platform === 'linux'
      ? ['hamartia-desktop', 'Hamartia']
      : []
  for (const name of names) {
    const candidate = path.join(target, name)
    try {
      fsSync.accessSync(candidate, process.platform === 'win32' ? undefined : fsSync.constants.X_OK)
      return { executable: candidate, cwd: target }
    } catch {}
  }
  throw new Error(`No unpacked Electron executable found in ${target}`)
}

async function assertBackendStopped(backendUrl) {
  const deadline = Date.now() + 10_000
  let lastResponse
  while (Date.now() < deadline) {
    try {
      lastResponse = await fetch(`${backendUrl}/healthcheck/ready`, { signal: AbortSignal.timeout(1000) })
    } catch {
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 200))
  }
  throw new Error(`Backend still responds after Electron exit (HTTP ${lastResponse?.status})`)
}

async function main() {
  assert.ok(process.platform === 'win32' || process.platform === 'linux', 'Run this smoke on native Windows or Linux')
  assert.ok(process.argv[2], 'Usage: node desktop/smoke_electron.cjs <unpacked-directory|installed-executable|appimage>')
  const { executable, cwd } = await resolveAppTarget(appTarget)
  const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'hamartia-electron-smoke-'))
  const markerPath = path.join(tempDir, 'ready.json')
  const userDataPath = path.join(tempDir, 'user-data')
  const electronArgs = process.env.HAMARTIA_ELECTRON_SMOKE_PASSWORD_STORE
    ? [`--password-store=${process.env.HAMARTIA_ELECTRON_SMOKE_PASSWORD_STORE}`]
    : []
  let stdout = ''
  let stderr = ''
  const child = spawn(executable, electronArgs, {
    cwd,
    env: {
      ...process.env,
      HAMARTIA_ELECTRON_SMOKE_MARKER: markerPath,
      HAMARTIA_ELECTRON_SMOKE_USER_DATA: userDataPath,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  child.stdout.setEncoding('utf8').on('data', (chunk) => { stdout += chunk })
  child.stderr.setEncoding('utf8').on('data', (chunk) => { stderr += chunk })

  const startedAt = Date.now()
  let readiness
  let exitCode
  let spawnError
  let shutdownTimer
  child.once('error', (error) => { spawnError = error })
  const exited = new Promise((resolve) => child.once('exit', (code) => { exitCode = code; resolve() }))

  try {
    while (Date.now() - startedAt < timeoutMs) {
      if (spawnError) throw spawnError
      try {
        readiness = JSON.parse(await fs.readFile(markerPath, 'utf8'))
        break
      } catch (error) {
        if (error.code !== 'ENOENT') throw error
      }
      if (exitCode !== undefined) throw new Error(`Electron exited before readiness with code ${exitCode}`)
      await new Promise((resolve) => setTimeout(resolve, 200))
    }
    assert.ok(readiness, `Timed out waiting ${timeoutMs}ms for Electron readiness marker`)
    assert.equal(readiness.error, undefined, `Renderer probe failed: ${readiness.error || ''}`)
    assert.equal(readiness.language, 'en', 'The packaged app should start in English')
    assert.equal(readiness.overviewVisible, true, 'The Overview screen should be rendered')
    assert.equal(readiness.healthStatus, 200, 'The same-origin readiness API should return HTTP 200')
    assert.match(readiness.origin, /^http:\/\/127\.0\.0\.1:\d+$/)
    assert.equal(readiness.backendUrl, readiness.origin, 'The marker should identify the backend origin')
    assert.deepEqual(readiness.safeStorage, {
      platform: process.platform,
      backend: process.platform === 'linux' ? process.env.HAMARTIA_ELECTRON_SMOKE_EXPECT_BACKEND : null,
      available: true,
      roundTrip: true,
      protectedStorageAvailable: (process.env.HAMARTIA_ELECTRON_SMOKE_STORAGE_MODE || 'protected') === 'protected',
    }, 'Native safeStorage behavior should match the selected platform and production policy')

    const remaining = timeoutMs - (Date.now() - startedAt)
    await Promise.race([
      exited,
      new Promise((_, reject) => {
        shutdownTimer = setTimeout(() => reject(new Error('Electron did not shut down cleanly after readiness')), remaining)
        shutdownTimer.unref()
      }),
    ])
    clearTimeout(shutdownTimer)
    assert.equal(exitCode, 0, `Electron exited with code ${exitCode}\n${stderr}`)
    await assertBackendStopped(readiness.backendUrl)
    await assert.rejects(fs.access(path.join(userDataPath, 'chatgpt-credentials.bin')), { code: 'ENOENT' })
    await assert.rejects(fs.access(path.join(userDataPath, 'chatgpt-host-id')), { code: 'ENOENT' })
    process.stdout.write(`Electron smoke passed: ${JSON.stringify(readiness)}\n`)
  } catch (error) {
    if (child.exitCode === null) child.kill()
    await Promise.race([exited, new Promise((resolve) => setTimeout(resolve, 5000))])
    throw new Error(`${error.message}\nstdout:\n${stdout}\nstderr:\n${stderr}`)
  } finally {
    clearTimeout(shutdownTimer)
    await fs.rm(tempDir, { recursive: true, force: true })
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`)
  process.exitCode = 1
})
