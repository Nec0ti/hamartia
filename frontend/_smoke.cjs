const assert = require('node:assert/strict')
const { spawn } = require('node:child_process')
const fs = require('node:fs/promises')
const os = require('node:os')
const path = require('node:path')
const { chromium } = require('playwright')

const apiUrl = 'http://127.0.0.1:8000'

async function waitForServer(child, url, name) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (child.exitCode !== null) throw new Error(`Server exited early (${child.exitCode})`)
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  throw new Error(`Timed out waiting for ${name}`)
}

async function main() {
  const dataDir = await fs.mkdtemp(path.join(os.tmpdir(), 'hamartia-browser-'))
  const baseUrl = 'http://127.0.0.1:5174'
  const uploads = path.join(dataDir, 'uploads')
  await fs.mkdir(uploads)
  await fs.writeFile(path.join(dataDir, 'questions.json'), JSON.stringify([{
    id: 'q1', image_name: 'q1.png', image_path: 'uploads/q1.png', ocr_text: 'f(x) = 2x + 1',
    subject: 'Matematik', topic: 'Fonksiyon', hamartia_tag: '[Knowledge Gap]',
    created_at: '2026-11-14T09:00:00Z', reviewed_at: '', review_attempts: [],
  }]))
  await fs.writeFile(path.join(uploads, 'q1.png'), Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jL6sAAAAASUVORK5CYII=', 'base64'))
  const python = process.env.HAMARTIA_PYTHON || (process.platform === 'win32' ? 'python' : 'python3')
  const launcher = spawn(python, [path.resolve(__dirname, '../scripts/dev.py')], {
    cwd: path.resolve(__dirname, '..'),
    env: { ...process.env, HAMARTIA_DATA_DIR: dataDir, HAMARTIA_FRONTEND_PORT: '5174', VITE_API_BASE: apiUrl },
    stdio: ['ignore', 'ignore', 'pipe'],
  })
  let serverErrors = ''
  launcher.stderr.setEncoding('utf8').on('data', (chunk) => { serverErrors += chunk })
  let browser
  try {
    await waitForServer(launcher, `${apiUrl}/healthcheck/ready`, 'API')
    await waitForServer(launcher, baseUrl, 'frontend')
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
    await page.getByRole('heading', { name: 'Genel bakış' }).waitFor()
    assert.equal(await page.getByText('Cannot read properties of undefined', { exact: false }).count(), 0)
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    await page.getByRole('heading', { name: 'Şimdi çöz' }).waitFor()
    assert.equal(await page.getByRole('img', { name: 'Matematik · Fonksiyon sorusu' }).count(), 1)
    assert.equal(await page.getByRole('button', { name: 'Doğru çözdüm' }).count(), 1)
    assert.equal(await page.getByRole('button', { name: 'Yanlış çözdüm' }).count(), 1)
    assert.equal(await page.locator('img[alt="Matematik · Fonksiyon sorusu"]').evaluate((img) => img.naturalWidth), 1)
    await page.setViewportSize({ width: 390, height: 844 })
    assert(await page.getByRole('button', { name: 'Çalışma Planı' }).isVisible())
    const pageWidth = await page.evaluate(() => document.documentElement.scrollWidth)
    assert(pageWidth <= 390, `390 px view overflows to ${pageWidth} px`)
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
    await page.getByText('2 farklı soru denedin · 1 doğru, 1 yanlış yanıt').waitFor()
    const captureAndPersistenceMs = Math.round(performance.now() - attempted)
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.getByRole('button', { name: 'Ana Sayfa' }).click()
    const examCrudStarted = performance.now()
    await page.getByRole('button', { name: 'Deneme ekle' }).click()
    await page.getByRole('dialog').locator('select').selectOption('ayt')
    await page.getByLabel('Ders').fill('Matematik')
    await page.getByRole('button', { name: 'Denemeyi kaydet' }).click()
    await page.getByRole('button', { name: /Denemeyi düzenle Matematik/ }).waitFor()
    await page.getByLabel('Deneme türü filtresi').selectOption('ayt')
    await page.getByText('Deneme sayısı · AYT').waitFor()
    await page.getByRole('button', { name: /Denemeyi düzenle Matematik/ }).click()
    await page.getByRole('dialog').locator('select').selectOption('tyt')
    await page.getByLabel('Ders').fill('Geometri')
    await page.getByRole('button', { name: 'Değişiklikleri kaydet' }).click()
    await page.getByLabel('Deneme türü filtresi').selectOption('tyt')
    await page.getByRole('button', { name: /Denemeyi sil Geometri/ }).waitFor()
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: /Denemeyi sil Geometri/ }).click()
    await page.getByText('Henüz deneme kaydı yok.').waitFor()
    const examCrudMs = Math.round(performance.now() - examCrudStarted)
    const questionManageStarted = performance.now()
    await page.getByRole('button', { name: 'Yanlışlarım' }).click()
    const textCard = page.locator(`article[data-question-id="${createdQuestion.id}"]`)
    await textCard.getByRole('button', { name: /Soruyu düzenle/ }).click()
    await textCard.getByLabel('Düzenle · Ders').fill('Edebiyat')
    await textCard.getByLabel('Düzenle · Soru metni').fill('Güncellenmiş soru metni')
    await textCard.getByRole('button', { name: 'Kaydet' }).click()
    const updatedCard = page.locator('article').filter({ hasText: 'Güncellenmiş soru metni' })
    await updatedCard.getByRole('button', { name: /Soruyu sil Edebiyat/ }).waitFor()
    const imageCard = page.locator('article[data-question-id="q1"]')
    page.once('dialog', (dialog) => dialog.accept())
    await imageCard.getByRole('button', { name: /Soruyu sil Matematik/ }).click()
    await imageCard.waitFor({ state: 'detached' })
    const questionManageMs = Math.round(performance.now() - questionManageStarted)
    assert(appRequests.some((request) => request.path === '/questions/q1/attempt' && request.method === 'POST' && request.body.correct === false))
    assert(appRequests.some((request) => request.path === '/questions' && request.method === 'POST'))
    assert(appRequests.some((request) => request.path === `/questions/${createdQuestion.id}/attempt` && request.method === 'POST' && request.body.correct === true))
    assert(appRequests.some((request) => request.path === '/exams' && request.method === 'POST' && request.body.exam_type === 'ayt'))
    assert(appRequests.some((request) => request.path.startsWith('/exams/') && request.method === 'PUT' && request.body.exam_type === 'tyt'))
    assert(appRequests.some((request) => request.path.startsWith('/exams/') && request.method === 'DELETE'))
    assert(appRequests.some((request) => request.path === `/questions/${createdQuestion.id}` && request.method === 'PATCH' && request.body.subject === 'Edebiyat'))
    assert(appRequests.some((request) => request.path === '/questions/q1' && request.method === 'DELETE'))
    assert(!appRequests.some((request) => request.path.includes('/agent') || request.path.endsWith('/analyze')))
    assert.deepEqual(failedResponses, [])
    assert.deepEqual(pageErrors, [])
    assert.deepEqual(consoleErrors, [])
    const saved = JSON.parse(await fs.readFile(path.join(dataDir, 'questions.json'), 'utf8'))
    assert.deepEqual(saved.find((question) => question.id === createdQuestion.id).review_attempts.map((item) => item.correct), [true])
    assert.equal(saved.find((question) => question.id === createdQuestion.id).subject, 'Edebiyat')
    assert.equal(saved.find((question) => question.id === createdQuestion.id).ocr_text, 'Güncellenmiş soru metni')
    assert.equal(saved.some((question) => question.id === 'q1'), false)
    assert.equal(await fs.access(path.join(uploads, 'q1.png')).then(() => true).catch(() => false), false)
    assert.deepEqual(JSON.parse(await fs.readFile(path.join(dataDir, 'exams.json'), 'utf8')), [])
    console.log(JSON.stringify({ benchmark: 'study_plan_and_local_crud_browser_smoke', navigation_ms: navigationMs, capture_and_review_persistence_ms: captureAndPersistenceMs, exam_crud_ms: examCrudMs, question_edit_delete_ms: questionManageMs, ai_included: false }))
  } catch (error) {
    if (serverErrors) process.stderr.write(serverErrors)
    throw error
  } finally {
    await browser?.close()
    if (launcher.exitCode === null) {
      launcher.kill('SIGTERM')
      await new Promise((resolve) => launcher.once('exit', resolve))
    }
    await fs.rm(dataDir, { recursive: true, force: true })
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
