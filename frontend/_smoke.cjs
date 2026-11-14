const assert = require('node:assert/strict')
const { spawn } = require('node:child_process')
const fs = require('node:fs/promises')
const os = require('node:os')
const path = require('node:path')
const { chromium } = require('playwright')

const baseUrl = 'http://127.0.0.1:5174'
const apiUrl = 'http://127.0.0.1:8000'

async function waitForServer(child, url) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (child.exitCode !== null) throw new Error(`Server exited early (${child.exitCode})`)
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  throw new Error('Timed out waiting for Vite')
}

async function main() {
  const dataDir = await fs.mkdtemp(path.join(os.tmpdir(), 'hamartia-browser-'))
  const uploads = path.join(dataDir, 'uploads')
  await fs.mkdir(uploads)
  await fs.writeFile(path.join(dataDir, 'questions.json'), JSON.stringify([{
    id: 'q1', image_name: 'q1.png', image_path: 'uploads/q1.png', ocr_text: 'f(x) = 2x + 1',
    subject: 'Matematik', topic: 'Fonksiyon', hamartia_tag: '[Knowledge Gap]',
    created_at: '2026-11-14T09:00:00Z', reviewed_at: '', review_attempts: [],
  }]))
  await fs.writeFile(path.join(uploads, 'q1.png'), Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jL6sAAAAASUVORK5CYII=', 'base64'))
  const python = process.env.HAMARTIA_PYTHON || (process.platform === 'win32' ? 'python' : 'python3')
  const backend = spawn(python, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'], {
    cwd: path.resolve(__dirname, '../backend'),
    env: { ...process.env, HAMARTIA_DATA_DIR: dataDir },
    stdio: ['ignore', 'ignore', 'pipe'],
  })
  const frontend = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5174', '--strictPort'], {
    cwd: __dirname,
    env: { ...process.env, VITE_API_BASE: apiUrl },
    stdio: ['ignore', 'ignore', 'pipe'],
  })
  let serverErrors = ''
  backend.stderr.setEncoding('utf8').on('data', (chunk) => { serverErrors += chunk })
  frontend.stderr.setEncoding('utf8').on('data', (chunk) => { serverErrors += chunk })
  let browser
  try {
    await waitForServer(backend, `${apiUrl}/healthcheck/health`)
    await waitForServer(frontend, baseUrl)
    browser = await chromium.launch({
      headless: true,
      ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {}),
    })
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
    const pageErrors = []
    const consoleErrors = []
    const failedResponses = []
    const appRequests = []
    let createdQuestion
    page.on('pageerror', (error) => pageErrors.push(error.message))
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push({ text: message.text(), location: message.location() })
    })
    page.on('response', (response) => {
      if (response.status() >= 400) failedResponses.push({ url: response.url(), status: response.status() })
      if (new URL(response.url()).pathname === '/questions' && response.request().method() === 'POST') {
        response.json().then((question) => { createdQuestion = question })
      }
    })
    page.on('request', (request) => {
      if (request.url().startsWith(apiUrl)) {
        const jsonBody = request.headers()['content-type']?.includes('application/json')
        appRequests.push({ path: new URL(request.url()).pathname, method: request.method(), body: jsonBody ? request.postDataJSON() : null })
      }
    })

    const started = performance.now()
    await page.goto(baseUrl, { waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    await page.getByRole('heading', { name: 'Şimdi çöz' }).waitFor()
    assert.equal(await page.getByRole('img', { name: 'Matematik · Fonksiyon sorusu' }).count(), 1)
    assert.equal(await page.getByRole('button', { name: 'Doğru çözdüm' }).count(), 1)
    assert.equal(await page.getByRole('button', { name: 'Yanlış çözdüm' }).count(), 1)
    assert.equal(await page.locator('img[alt="Matematik · Fonksiyon sorusu"]').evaluate((img) => img.naturalWidth), 1)
    await page.setViewportSize({ width: 390, height: 844 })
    assert(await page.getByRole('button', { name: 'Çalışma Planı' }).isVisible())
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true)
    const navigationMs = Math.round(performance.now() - started)

    const attempted = performance.now()
    await page.getByRole('button', { name: 'Yanlış çözdüm' }).click()
    await page.getByText('1 soru aralıklı tekrar için ileride açılacak.').waitFor()
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    await page.getByText('1 soru aralıklı tekrar için ileride açılacak.').waitFor()
    await page.getByRole('button', { name: 'Yanlışlarım' }).click()
    await page.getByLabel('Ders').fill('Türkçe')
    await page.getByLabel('Konu').fill('Paragraf')
    await page.locator('textarea').fill('Metin tabanlı deneme sorusu')
    await page.getByRole('button', { name: 'Soruyu kaydet' }).click()
    await page.getByRole('img', { name: 'Görseli olmayan metin sorusu' }).waitFor()
    assert.equal(createdQuestion.image_path, '')
    assert.equal(createdQuestion.ocr_text, 'Metin tabanlı deneme sorusu')

    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    await page.getByRole('img', { name: 'Görseli olmayan metin sorusu' }).waitFor()
    await page.getByRole('button', { name: 'Doğru çözdüm' }).click()
    await page.getByText('2 soru aralıklı tekrar için ileride açılacak.').waitFor()
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    await page.getByText('2 soru aralıklı tekrar için ileride açılacak.').waitFor()
    assert(appRequests.some((request) => request.path === '/questions/q1/attempt' && request.method === 'POST' && request.body.correct === false))
    assert(appRequests.some((request) => request.path === '/questions' && request.method === 'POST'))
    assert(appRequests.some((request) => request.path === `/questions/${createdQuestion.id}/attempt` && request.method === 'POST' && request.body.correct === true))
    assert(!appRequests.some((request) => request.path.includes('/agent') || request.path.endsWith('/analyze')))
    assert.deepEqual(failedResponses, [])
    assert.deepEqual(pageErrors, [])
    assert.deepEqual(consoleErrors, [])
    const captureAndPersistenceMs = Math.round(performance.now() - attempted)
    const saved = JSON.parse(await fs.readFile(path.join(dataDir, 'questions.json'), 'utf8'))
    assert.deepEqual(saved.find((question) => question.id === 'q1').review_attempts.map((item) => item.correct), [false])
    assert.deepEqual(saved.find((question) => question.id === createdQuestion.id).review_attempts.map((item) => item.correct), [true])
    console.log(JSON.stringify({ benchmark: 'study_plan_browser_smoke', navigation_ms: navigationMs, capture_and_review_persistence_ms: captureAndPersistenceMs, ai_included: false }))
  } catch (error) {
    if (serverErrors) process.stderr.write(serverErrors)
    throw error
  } finally {
    await browser?.close()
    backend.kill('SIGTERM')
    frontend.kill('SIGTERM')
    await fs.rm(dataDir, { recursive: true, force: true })
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
