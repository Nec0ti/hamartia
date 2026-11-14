const assert = require('node:assert/strict')
const { spawn } = require('node:child_process')
const fsSync = require('node:fs')
const fs = require('node:fs/promises')
const os = require('node:os')
const path = require('node:path')

const unpackedDir = path.resolve(process.argv[2] || '')
const timeoutMs = Number(process.env.HAMARTIA_ELECTRON_SMOKE_TIMEOUT_MS || 90_000)

function executablePath(directory) {
  const names = process.platform === 'win32'
    ? ['Hamartia.exe', 'hamartia-desktop.exe']
    : process.platform === 'linux'
      ? ['hamartia-desktop', 'Hamartia']
      : []
  for (const name of names) {
    const candidate = path.join(directory, name)
    try {
      fsSync.accessSync(candidate, process.platform === 'win32' ? undefined : fsSync.constants.X_OK)
      return candidate
    } catch {}
  }
  throw new Error(`No unpacked Electron executable found in ${directory}`)
}

async function main() {
  assert.ok(process.platform === 'win32' || process.platform === 'linux', 'Run this smoke on native Windows or Linux')
  assert.ok(process.argv[2], 'Usage: node desktop/smoke_electron.cjs <unpacked-directory>')
  await fs.access(path.join(unpackedDir, 'resources', 'app.asar'))
  const executable = executablePath(unpackedDir)
  const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'hamartia-electron-smoke-'))
  const markerPath = path.join(tempDir, 'ready.json')
  const userDataPath = path.join(tempDir, 'user-data')
  let stdout = ''
  let stderr = ''
  const child = spawn(executable, [], {
    cwd: unpackedDir,
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
