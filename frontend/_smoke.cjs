const assert = require('node:assert/strict')
const { spawn } = require('node:child_process')
const fs = require('node:fs/promises')
const os = require('node:os')
const path = require('node:path')
const { chromium } = require('playwright')
const { diagnosticRequests, isSettingsRequestUrl, settingsRoutePattern, withDeadline, withTimeout } = require('./smokeDeadline.cjs')

const apiUrl = 'http://127.0.0.1:8000'

async function waitForServer(child, url, name) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (child.exitCode !== null) throw new Error(`Server exited early (${child.exitCode})`)
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1000) })
      if (response.ok) return
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  throw new Error(`Timed out waiting for ${name}`)
}

function localFetch(url, init = {}) {
  return fetch(url, { ...init, signal: init.signal || AbortSignal.timeout(10_000) })
}

async function main(smokeRun) {
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
  let cleanupPromise
  const cleanupResources = async () => {
    if (!cleanupPromise) {
      cleanupPromise = (async () => {
        if (browser) {
          try {
            await withTimeout(browser.close(), 5000, 'Chromium shutdown')
          } catch {
            if (typeof browser.process !== 'function') throw new Error('Chromium shutdown timed out and its process cannot be reaped.')
            const browserProcess = browser.process()
            if (browserProcess && browserProcess.exitCode === null) {
              const exited = new Promise((resolve) => browserProcess.once('exit', resolve))
              browserProcess.kill('SIGKILL')
              await withTimeout(exited, 2000, 'Chromium forced shutdown')
            }
          }
        }
        if (launcher.exitCode === null) {
          const exited = new Promise((resolve) => launcher.once('exit', resolve))
          launcher.kill('SIGTERM')
          try {
            await withTimeout(exited, 5000, 'Dev server shutdown')
          } catch {
            launcher.kill('SIGKILL')
            await withTimeout(exited, 2000, 'Dev server forced shutdown')
          }
        }
      })()
    }
    return cleanupPromise
  }
  smokeRun.cleanup = cleanupResources
  try {
    await waitForServer(launcher, `${apiUrl}/healthcheck/ready`, 'API')
    await waitForServer(launcher, baseUrl, 'frontend')
    const seedResponse = await localFetch(`${apiUrl}/exams`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date: '2026-11-14', exam_type: 'branch', subject: 'Matematik', duration_minutes: 30, correct: 30, incorrect: 4, blank: 2 }),
    })
    if (!seedResponse.ok) throw new Error(`Locale fixture failed: ${await seedResponse.text()}`)
    const localeExam = await seedResponse.json()
    browser = await chromium.launch({
      timeout: 30_000,
      headless: true,
      ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {}),
    })
    const page = await withTimeout(browser.newPage({ viewport: { width: 1280, height: 900 } }), 30_000, 'Browser page creation')
    const pageErrors = []
    const consoleErrors = []
    const failedResponses = []
    const appRequests = []
    const settingsRouteEvaluations = []
    let createdQuestion
    let linkedQuestion
    let practiceSession
    let localAttemptDay
    page.on('pageerror', (error) => pageErrors.push(error.message))
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push({ text: message.text(), location: message.location() })
    })
    page.on('response', (response) => {
      if (response.status() >= 400) failedResponses.push({ url: response.url(), status: response.status() })
    })
    page.on('request', (request) => {
      if (request.url().startsWith(apiUrl)) {
        const jsonBody = request.headers()['content-type']?.includes('application/json')
        const requestUrl = new URL(request.url())
        appRequests.push({ url: request.url(), origin: requestUrl.origin, path: requestUrl.pathname, query: Object.fromEntries(requestUrl.searchParams), method: request.method(), body: jsonBody ? request.postDataJSON() : null })
      }
    })
    smokeRun.diagnostics = () => {
      const pageUrl = new URL(page.url())
      return `; page origin=${pageUrl.origin}; page path=${pageUrl.pathname}; expected API origin=${apiUrl}; route registered=${settingsRouteRegistered}; route pattern=${settingsRouteMatcher}; recent API requests=${JSON.stringify(diagnosticRequests(appRequests.slice(-8)))}; route matcher evaluations=${JSON.stringify(settingsRouteEvaluations.slice(-20))}; page errors=${JSON.stringify(pageErrors)}`
    }

    let releaseInitialSettingsGet
    let notifyInitialSettingsGet
    const settingsRouteMatcher = settingsRoutePattern(apiUrl)
    const initialSettingsGetIntercepted = new Promise((resolve) => { notifyInitialSettingsGet = resolve })
    const initialSettingsGetGate = new Promise((resolve) => { releaseInitialSettingsGet = resolve })
    let interceptedInitialSettingsGet = false
    let settingsRouteRegistered = false
    await page.route(settingsRouteMatcher, async (route) => {
      const requestUrl = new URL(route.request().url())
      const matched = isSettingsRequestUrl(requestUrl, apiUrl)
      if (settingsRouteEvaluations.length < 40) {
        settingsRouteEvaluations.push({ method: route.request().method(), origin: requestUrl.origin, path: requestUrl.pathname, matched })
      }
      if (!matched) {
        await route.continue()
        return
      }
      if (route.request().method() === 'GET') {
        interceptedInitialSettingsGet = true
        notifyInitialSettingsGet()
        await initialSettingsGetGate
      }
      await route.continue()
    })
    settingsRouteRegistered = true
    const started = performance.now()
    await page.goto(baseUrl, { waitUntil: 'domcontentloaded' })
    assert.equal(await page.locator('html').getAttribute('lang'), 'en')
    await page.getByRole('heading', { name: 'Overview' }).waitFor()
    const brandMark = page.getByRole('img', { name: 'Hamartia' })
    await brandMark.waitFor()
    assert.equal(await brandMark.evaluate((image) => image.naturalWidth > 0), true)
    assert.equal((await page.request.get(`${baseUrl}/hamartia-favicon.svg`)).status(), 200)
    await page.keyboard.press('Tab')
    const keyboardFocus = await page.evaluate(() => {
      const outline = getComputedStyle(document.activeElement)
      return { style: outline.outlineStyle, width: Number.parseFloat(outline.outlineWidth) }
    })
    assert.equal(keyboardFocus.style, 'solid')
    assert(keyboardFocus.width >= 2, `Expected a visible keyboard focus ring, got ${keyboardFocus.width}px`)
    await withTimeout(
      initialSettingsGetIntercepted,
      10_000,
      'Initial GET /settings was not intercepted',
      () => `${smokeRun.diagnostics()}; route handler ran=${interceptedInitialSettingsGet}`,
    )
    await page.getByRole('button', { name: 'Open settings' }).click()
    await page.getByRole('status').getByText('Loading saved settings…').waitFor()
    assert.equal(await page.getByLabel('API key').isDisabled(), true)
    assert.equal(await page.getByRole('button', { name: 'Save', exact: true }).isDisabled(), true)
    releaseInitialSettingsGet()
    await page.getByLabel('API key').waitFor({ state: 'visible' })
    await page.waitForFunction(() => !document.querySelector('#settings-api-key')?.disabled)
    await page.getByRole('button', { name: 'Close settings' }).click()
    await page.unroute(settingsRouteMatcher)
    smokePhase = 'study, profile, and local API browser flow'
    await page.waitForLoadState('networkidle')
    await page.waitForFunction(() => localStorage.getItem('hamartia.language') === 'en')
    assert.equal(/\b(?:navigation|settings|dashboard|exams|questions|study|cosmos|common)\.[a-z]/i.test(await page.locator('body').innerText()), false)
    await page.getByRole('cell', { name: 'Nov 14, 2026', exact: true }).waitFor()
    await page.getByRole('img', { name: 'Net trend · All subjects' }).waitFor()
    await page.getByRole('img', { name: 'Performance radar chart: speed, focus, precision, and stamina' }).waitFor()
    await page.getByText('11/14', { exact: true }).waitFor()
    await page.evaluate(() => localStorage.setItem('hamartia.language', 'fr'))
    await page.reload({ waitUntil: 'networkidle' })
    assert.equal(await page.locator('html').getAttribute('lang'), 'en')
    await page.waitForFunction(() => localStorage.getItem('hamartia.language') === 'en')
    await page.getByRole('heading', { name: 'Overview' }).waitFor()
    await page.getByRole('button', { name: 'My Mistakes' }).click()
    await page.getByRole('heading', { name: 'Missed questions' }).waitFor()
    await page.getByRole('button', { name: 'Dashboard' }).click()
    await page.getByRole('heading', { name: 'Overview' }).waitFor()
    await page.getByRole('button', { name: 'Open settings' }).click()
    await page.getByLabel('Language').selectOption('tr')
    await page.waitForFunction(() => document.documentElement.lang === 'tr' && localStorage.getItem('hamartia.language') === 'tr')
    assert.equal(await page.locator('html').getAttribute('lang'), 'tr')
    await page.reload({ waitUntil: 'networkidle' })
    assert.equal(await page.locator('html').getAttribute('lang'), 'tr')
    await page.getByRole('heading', { name: 'Genel bakış' }).waitFor()
    assert.equal(/\b(?:navigation|settings|dashboard|exams|questions|study|cosmos|common)\.[a-z]/i.test(await page.locator('body').innerText()), false)
    await page.getByRole('cell', { name: '14 Kas 2026', exact: true }).waitFor()
    await page.getByRole('img', { name: 'Net değişimi · Tüm dersler' }).waitFor()
    await page.getByRole('img', { name: 'Performans radarı: hız, odak, isabet ve dayanıklılık' }).waitFor()
    await page.getByText('14/11', { exact: true }).waitFor()
    const deleteFixture = await localFetch(`${apiUrl}/exams/${localeExam.id}`, { method: 'DELETE' })
    assert.equal(deleteFixture.ok, true, `Locale fixture cleanup failed: ${await deleteFixture.text()}`)
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByText('Henüz deneme kaydı yok.').waitFor()
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

    const practiceStarted = performance.now()
    const practiceSection = page.getByRole('region', { name: 'Konu çalışma setleri' })
    await practiceSection.getByLabel('Ders').fill('Matematik')
    await practiceSection.getByLabel('Konu').fill('Fonksiyon')
    await practiceSection.getByRole('spinbutton', { name: 'Doğru', exact: true }).fill('8')
    await practiceSection.getByRole('spinbutton', { name: 'Yanlış', exact: true }).fill('2')
    await practiceSection.getByRole('spinbutton', { name: 'Boş', exact: true }).fill('1')
    await practiceSection.getByLabel('Dakika').fill('25')
    await practiceSection.getByLabel('Saniye').fill('10')
    assert.equal(await practiceSection.locator('form').evaluate((form) => form.checkValidity()), true)
    const [practiceResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/practice' && response.request().method() === 'POST'),
      practiceSection.getByRole('button', { name: 'Seti kaydet' }).click(),
    ])
    if (!practiceResponse.ok()) throw new Error(`Practice save failed ${practiceResponse.status()}: ${await practiceResponse.text()}`)
    practiceSession = await practiceResponse.json()
    await practiceSection.getByText('80,0% cevaplanan doğruluğu').waitFor()
    assert.equal(practiceSession.correct, 8)
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    await page.getByRole('region', { name: 'Konu çalışma setleri' }).getByText('80,0% cevaplanan doğruluğu').waitFor()
    const practiceSessionPersistenceMs = Math.round(performance.now() - practiceStarted)

    const focusStarted = performance.now()
    await page.getByRole('button', { name: 'Odaklı çalış · Matematik / Fonksiyon' }).click()
    const focusSection = page.getByRole('region', { name: 'Odaklı çalışma oturumu' })
    await focusSection.waitFor()
    await focusSection.getByRole('button', { name: 'Bitir ve kaydet' }).click()
    await page.getByRole('alert').getByText('Bitirmek için en az bir sorunun sonucunu işaretle.').waitFor()
    await focusSection.getByRole('button', { name: 'Doğru artır' }).click()
    await focusSection.getByRole('button', { name: 'Boş artır' }).click()
    await focusSection.getByRole('button', { name: 'Yanlış azalt' }).click()
    await focusSection.getByText('Yanlış: 0').waitFor()
    await focusSection.getByRole('button', { name: 'Duraklat' }).click()
    const pausedTime = await focusSection.getByLabel('Geçen süre').textContent()
    await page.waitForTimeout(1050)
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    const resumedSection = page.getByRole('region', { name: 'Odaklı çalışma oturumu' })
    await resumedSection.waitFor()
    assert.equal(await resumedSection.getByLabel('Geçen süre').textContent(), pausedTime)
    await resumedSection.getByRole('button', { name: 'Sürdür' }).click()
    await page.waitForTimeout(1100)
    const elapsedAtFinish = Number((await resumedSection.getByLabel('Geçen süre').textContent()).split(':').at(-1))
    let failFocusedClockClear = true
    await page.route(`${apiUrl}/clock`, async (route) => {
      const request = route.request()
      if (request.method() === 'PATCH' && request.postDataJSON()?.active_timer === null && failFocusedClockClear) {
        failFocusedClockClear = false
        await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'intentional focused completion clear failure' }) })
      } else await route.continue()
    })
    const [focusResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/practice' && response.request().method() === 'POST'),
      resumedSection.getByRole('button', { name: 'Bitir ve kaydet' }).click(),
    ])
    if (!focusResponse.ok()) throw new Error(`Focused practice save failed ${focusResponse.status()}: ${await focusResponse.text()}`)
    await page.waitForResponse((response) => new URL(response.url()).pathname === '/clock' && response.request().method() === 'PATCH' && response.status() === 503)
    assert.equal(await resumedSection.count(), 1, 'The focused draft must remain available after clock clear fails')
    assert.equal((await (await localFetch(`${apiUrl}/practice`)).json()).filter((item) => item.subject === 'Matematik' && item.topic === 'Fonksiyon').length, 2)
    const [retryPracticeResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/practice' && response.request().method() === 'POST'),
      resumedSection.getByRole('button', { name: 'Bitir ve kaydet' }).click(),
    ])
    assert.equal(retryPracticeResponse.status(), 201)
    practiceSession = await focusResponse.json()
    await resumedSection.waitFor({ state: 'detached' })
    assert.equal((await retryPracticeResponse.json()).id, practiceSession.id, 'Retry must return the already-created practice record')
    await page.unroute(`${apiUrl}/clock`)
    assert.equal(practiceSession.subject, 'Matematik')
    assert.equal(practiceSession.topic, 'Fonksiyon')
    assert.deepEqual([practiceSession.correct, practiceSession.incorrect, practiceSession.blank], [1, 0, 1])
    assert(practiceSession.duration_seconds >= elapsedAtFinish)
    await practiceSection.getByText('81,8% cevaplanan doğruluğu').waitFor()

    for (let index = 1; index <= 6; index += 1) {
      const response = await page.context().request.post(`${apiUrl}/practice`, { data: {
        date: `2026-11-0${index}`, subject: 'Matematik', topic: 'Fonksiyon',
        correct: 1, incorrect: 0, blank: 0, duration_minutes: 2, duration_seconds: index,
      } })
      assert.equal(response.status(), 201)
    }
    const blankResponse = await page.context().request.post(`${apiUrl}/practice`, { data: {
      date: '2026-11-14', subject: 'Biyoloji', topic: 'Hücre',
      correct: 0, incorrect: 0, blank: 4, duration_minutes: 1, duration_seconds: 0,
    } })
    assert.equal(blankResponse.status(), 201)
    const chartStarted = performance.now()
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    const netChart = page.getByRole('img', { name: 'Matematik · Fonksiyon net değişimi' })
    const accuracyChart = page.getByRole('img', { name: 'Matematik · Fonksiyon doğruluk değişimi' })
    await netChart.waitFor()
    await accuracyChart.waitFor()
    assert.equal(await netChart.locator('.recharts-line-curve').count(), 1)
    assert.equal(await accuracyChart.locator('.recharts-line-curve').count(), 1)
    const blankAccuracy = page.getByRole('img', { name: 'Biyoloji · Hücre doğruluk değişimi' })
    await blankAccuracy.waitFor()
    await page.getByText('Cevaplanan soru yok').first().waitFor()
    assert.equal(await blankAccuracy.locator('.recharts-line-curve').count(), 0)
    await page.getByText('88,2% cevaplanan doğruluğu').waitFor()
    assert.equal(await page.locator('details > summary').filter({ hasText: 'Önceki setler (2)' }).count(), 1)
    const chartPageWidth = await page.evaluate(() => document.documentElement.scrollWidth)
    assert(chartPageWidth <= 390, `390 px chart view overflows to ${chartPageWidth} px`)
    const oldHistory = page.locator('details').filter({ has: page.locator('summary', { hasText: 'Önceki setler (2)' }) })
    if (!await oldHistory.evaluate((element) => element.open)) await oldHistory.locator('summary').click()
    await page.getByRole('button', { name: 'Seti düzenle 1 Kas 2026 Fonksiyon' }).click()
    await practiceSection.locator('form').getByRole('spinbutton', { name: 'Doğru', exact: true }).fill('10')
    await practiceSection.getByRole('button', { name: 'Değişiklikleri kaydet' }).click()
    await practiceSection.getByText('92,3% cevaplanan doğruluğu').waitFor()
    if (!await oldHistory.evaluate((element) => element.open)) await oldHistory.locator('summary').click()
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: 'Seti sil 2 Kas 2026 Fonksiyon' }).click()
    await page.locator('details > summary').filter({ hasText: 'Önceki setler (1)' }).waitFor()
    const practiceTrendAndHistoryMs = Math.round(performance.now() - chartStarted)
    const focusedSessionMs = Math.round(performance.now() - focusStarted)

    const attempted = performance.now()
    const [wrongAttemptResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/questions/q1/attempt' && response.request().method() === 'POST'),
      page.getByRole('button', { name: 'Yanlış çözdüm' }).click(),
    ])
    assert.equal((await wrongAttemptResponse.json()).review_attempts.at(-1).correct, false)
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    assert.equal((await (await localFetch(`${apiUrl}/questions/q1`)).json()).review_attempts.at(-1).correct, false)
    assert.equal(await page.getByRole('region', { name: 'Odaklı çalışma oturumu' }).count(), 0)
    await page.getByRole('button', { name: 'Yanlışlarım' }).click()
    await page.getByLabel('Ders').fill('Türkçe')
    await page.getByLabel('Konu').fill('Paragraf')
    await page.getByLabel('Soru metni veya kendi notun (görsel yoksa zorunlu)').fill('Metin tabanlı deneme sorusu')
    await page.getByText('İsteğe bağlı program referansı', { exact: true }).click()
    await page.getByLabel('Program çerçevesi').fill('Synthetic study framework')
    await page.getByLabel('Kaynak adı').fill('Browser fixture')
    await page.getByLabel('Sürüm / yıl').fill('Test version')
    await page.getByLabel('Sınıf / yıl').fill('Year 2')
    await page.getByLabel('Ünite / tema').fill('Made-up patterns')
    await page.getByLabel('Kendi kısa öğrenme çıktısı notun veya başka sözcüklerle anlatımın').fill('Identify a made-up pattern')
    await page.getByLabel('Süreç bileşeni').fill('Explain reasoning')
    await page.getByLabel('İsteğe bağlı kaynak adresi (otomatik alınmaz veya doğrulanmaz)').fill('https://example.invalid/reference')
    const [createdQuestionResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/questions' && response.request().method() === 'POST'),
      page.getByRole('button', { name: 'Soruyu kaydet' }).click(),
    ])
    createdQuestion = await createdQuestionResponse.json()
    await page.getByRole('img', { name: 'Görseli olmayan metin sorusu' }).waitFor()
    assert.equal(createdQuestion.image_path, '')
    assert.equal(createdQuestion.ocr_text, 'Metin tabanlı deneme sorusu')
    assert.equal(createdQuestion.curriculum_reference.framework, 'Synthetic study framework')
    assert.equal(createdQuestion.curriculum_reference.learning_outcome, 'Identify a made-up pattern')

    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    const savedTextQuestion = page.locator('article').filter({ has: page.getByRole('img', { name: 'Görseli olmayan metin sorusu' }) })
    await savedTextQuestion.waitFor()
    localAttemptDay = await page.evaluate(() => {
      const now = new Date()
      return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
    })
    const [correctAttemptResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === `/questions/${createdQuestion.id}/attempt` && response.request().method() === 'POST'),
      savedTextQuestion.getByRole('button', { name: 'Doğru çözdüm' }).click(),
    ])
    const persistedAttempt = (await correctAttemptResponse.json()).review_attempts.at(-1)
    assert.equal(persistedAttempt.correct, true)
    assert.equal(persistedAttempt.attempt_day, localAttemptDay)
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    assert.equal((await (await localFetch(`${apiUrl}/questions/${createdQuestion.id}`)).json()).review_attempts.at(-1).correct, true)
    const captureAndPersistenceMs = Math.round(performance.now() - attempted)
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.getByRole('button', { name: 'Ana Sayfa' }).click()
    const examCrudStarted = performance.now()
    await page.getByRole('button', { name: 'Deneme ekle' }).click()
    await page.getByRole('dialog').locator('select').first().selectOption('branch')
    await page.getByLabel('Ders', { exact: true }).fill('Matematik')
    await page.getByRole('button', { name: 'Denemeyi kaydet' }).click()
    await page.getByRole('button', { name: /Denemeyi düzenle Matematik/ }).waitFor()
    await page.locator('tbody tr').filter({ hasText: 'Matematik' }).dblclick()
    await page.getByLabel('Sınavdaki soru no').fill('2')
    await page.getByLabel('Çözüm sırası').fill('1')
    await page.getByLabel('Soruda harcanan saniye').fill('32')
    await page.getByLabel('Soru metni veya kendi notun (görsel yoksa zorunlu)').fill('Denemeye bağlı yanlış soru')
    const [linkedQuestionResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/questions' && response.request().method() === 'POST'),
      page.getByRole('button', { name: 'Soruyu kaydet' }).click(),
    ])
    linkedQuestion = await linkedQuestionResponse.json()
    await page.getByText('Deneme sorusu 2 · çözüm sırası 1 · 32 sn').waitFor()
    assert.equal(linkedQuestion.exam_id.length > 0, true)
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Yanlışlarım' }).click()
    await page.getByText('Deneme sorusu 2 · çözüm sırası 1 · 32 sn').waitFor()
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    await page.getByRole('region', { name: 'Denemelerde çözüm sırası' }).getByText('Erken sıra').waitFor()
    await page.getByRole('region', { name: 'Denemelerde çözüm sırası' }).getByText('Medyan 32 sn').waitFor()
    await page.getByRole('button', { name: 'Ana Sayfa' }).click()
    await page.getByLabel('Deneme türü filtresi').selectOption('branch')
    await page.getByText('Deneme sayısı · Branş').waitFor()
    await page.getByRole('button', { name: /Denemeyi düzenle Matematik/ }).click()
    await page.getByRole('dialog').locator('select').first().selectOption('branch')
    await page.getByLabel('Ders', { exact: true }).fill('Geometri')
    await page.getByRole('button', { name: 'Değişiklikleri kaydet' }).click()
    await page.getByLabel('Deneme türü filtresi').selectOption('branch')
    await page.getByRole('button', { name: /Denemeyi sil Geometri/ }).waitFor()
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: /Denemeyi sil Geometri/ }).click()
    await page.getByText('Henüz deneme kaydı yok.').waitFor()

    await page.getByLabel('Deneme türü filtresi').selectOption('all')
    await page.getByRole('button', { name: 'Deneme ekle' }).click()
    await page.getByRole('dialog').locator('select').first().selectOption('tyt')
    await page.getByRole('button', { name: 'Ders ekle' }).click()
    await page.getByRole('button', { name: 'Ders ekle' }).click()
    await page.getByLabel('Ders adı 1').fill('Türkçe')
    await page.getByLabel('1. ders Doğru').fill('30')
    await page.getByLabel('1. ders Yanlış').fill('5')
    await page.getByLabel('1. ders Boş').fill('5')
    await page.getByLabel('Ders adı 2').fill('Matematik')
    await page.getByLabel('2. ders Doğru').fill('25')
    await page.getByLabel('2. ders Yanlış').fill('8')
    await page.getByLabel('2. ders Boş').fill('7')
    const [tytResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/exams' && response.request().method() === 'POST'),
      page.getByRole('button', { name: 'Denemeyi kaydet' }).click(),
    ])
    const tytExam = await tytResponse.json()
    assert.deepEqual([tytExam.subject, tytExam.correct, tytExam.incorrect, tytExam.blank], ['TYT Geneli', 55, 13, 12])
    assert.equal(tytExam.sections.length, 2)
    await page.getByRole('button', { name: /Denemeyi düzenle TYT Geneli/ }).waitFor()
    await page.reload({ waitUntil: 'networkidle' })
    const tytDetails = page.locator('details').filter({ has: page.locator('summary', { hasText: 'TYT Geneli · 2 ders' }) })
    await tytDetails.locator('summary').click()
    await tytDetails.getByText('Türkçe: 30 D / 5 Y / 5 B').waitFor()
    await tytDetails.getByRole('button', { name: /Yanlış ekle Türkçe/ }).click()
    await page.getByText(/Bağlı deneme: .*Türkçe \(TYT\)/).waitFor()
    await page.getByText('Bu bölümde 40 soru var.').waitFor()
    await page.getByLabel('Sınavdaki soru no').fill('40')
    await page.getByLabel('Çözüm sırası').fill('40')
    await page.getByLabel('Soruda harcanan saniye').fill('51')
    await page.getByLabel('Soru metni veya kendi notun (görsel yoksa zorunlu)').fill('TYT Türkçe bölüm sorusu')
    const [sectionQuestionResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/questions' && response.request().method() === 'POST'),
      page.getByRole('button', { name: 'Soruyu kaydet' }).click(),
    ])
    const sectionQuestion = await sectionQuestionResponse.json()
    assert.deepEqual([sectionQuestion.subject, sectionQuestion.exam_section_total, sectionQuestion.question_number], ['Türkçe', 40, 40])
    await page.getByRole('button', { name: 'Ana Sayfa' }).click()
    await page.getByRole('button', { name: /Denemeyi düzenle TYT Geneli/ }).click()
    await page.getByLabel('1. ders Boş').fill('4')
    const [tytUpdateResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname.startsWith('/exams/') && response.request().method() === 'PUT'),
      page.getByRole('button', { name: 'Değişiklikleri kaydet' }).click(),
    ])
    const editedTyt = await tytUpdateResponse.json()
    assert.deepEqual([editedTyt.correct, editedTyt.incorrect, editedTyt.blank], [55, 13, 11])
    assert.equal(editedTyt.sections.length, 2)
    assert.equal(sectionQuestion.exam_section_total, 40)
    await page.getByLabel('Net değişimi ders filtresi').selectOption('Türkçe')
    await page.getByRole('button', { name: 'Çizgi' }).click()
    const turkishTrend = page.getByRole('img', { name: 'Net değişimi · Türkçe' })
    await turkishTrend.waitFor()
    assert.equal(await page.getByLabel('Net değişimi ders filtresi').inputValue(), 'Türkçe')

    await page.getByLabel('Net değişimi ders filtresi').selectOption('all')
    await page.getByRole('button', { name: 'Deneme ekle' }).click()
    await page.getByRole('dialog').locator('select').first().selectOption('ayt')
    await page.getByRole('button', { name: 'Ders ekle' }).click()
    await page.getByLabel('Ders adı 1').fill('Fizik')
    await page.getByLabel('1. ders Doğru').fill('10')
    await page.getByLabel('1. ders Yanlış').fill('3')
    await page.getByLabel('1. ders Boş').fill('1')
    await page.getByPlaceholder('Dakika').fill('45')
    const [aytResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/exams' && response.request().method() === 'POST'),
      page.getByRole('button', { name: 'Denemeyi kaydet' }).click(),
    ])
    const aytExam = await aytResponse.json()
    assert.deepEqual([aytExam.subject, aytExam.correct, aytExam.incorrect, aytExam.blank], ['AYT Geneli', 10, 3, 1])
    assert.equal(aytExam.sections.length, 1)
    await page.getByRole('button', { name: /Denemeyi sil AYT Geneli/ }).waitFor()
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: /Denemeyi sil AYT Geneli/ }).click()
    await page.getByRole('button', { name: /Denemeyi sil TYT Geneli/ }).waitFor()
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: /Denemeyi sil TYT Geneli/ }).click()
    await page.getByText('Henüz deneme kaydı yok.').waitFor()

    // Exercise the versioned custom scoring UI in Turkish, persist a sectioned
    // exam with the selected rule, then prove the Dashboard filter separates
    // it from an otherwise identical legacy YKS exam.
    await page.getByRole('button', { name: 'Puanlama profilleri' }).click()
    const [profileResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/exam-profiles' && response.request().method() === 'POST'),
      (async () => {
        const dialog = page.getByRole('dialog')
        await dialog.getByLabel('Görünen ad').fill('Custom Half Rule')
        await dialog.getByLabel('Ülke / bağlam etiketi').fill('Fixture')
        await dialog.getByLabel('Doğru yanıt puanı').fill('1')
        await dialog.getByLabel('Yanlış yanıt cezası').fill('1/2')
        await dialog.getByLabel('Boş yanıt puanı').fill('0')
        await dialog.getByRole('button', { name: 'Profil oluştur' }).click()
      })(),
    ])
    assert.equal(profileResponse.status(), 201)
    const customProfile = await profileResponse.json()
    await page.getByRole('dialog').getByRole('button', { name: 'Vazgeç' }).click()
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    const profiledPracticeForm = page.getByRole('region', { name: 'Konu çalışma setleri' })
    await profiledPracticeForm.getByLabel('Ders').fill('Matematik')
    await profiledPracticeForm.getByLabel('Konu').fill('Fonksiyon')
    await profiledPracticeForm.getByLabel('Puanlama profili', { exact: true }).selectOption(`${customProfile.profile_id}@1`)
    await profiledPracticeForm.getByRole('spinbutton', { name: 'Doğru', exact: true }).fill('8')
    await profiledPracticeForm.getByRole('spinbutton', { name: 'Yanlış', exact: true }).fill('2')
    await profiledPracticeForm.getByRole('spinbutton', { name: 'Boş', exact: true }).fill('1')
    const [profiledPracticeResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/practice' && response.request().method() === 'POST'),
      profiledPracticeForm.getByRole('button', { name: 'Seti kaydet' }).click(),
    ])
    const profiledPractice = await profiledPracticeResponse.json()
    assert.deepEqual([profiledPractice.net, profiledPractice.scoring_profile.profile_id, profiledPractice.scoring_profile.version], [7, customProfile.profile_id, 1])
    const customPracticeGroup = page.locator('article').filter({ hasText: 'Custom Half Rule · v1' })
    await customPracticeGroup.waitFor()
    await customPracticeGroup.getByRole('button', { name: /Seti düzenle/ }).first().click()
    await profiledPracticeForm.getByRole('spinbutton', { name: 'Doğru', exact: true }).fill('9')
    const [editedPracticeResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === `/practice/${profiledPractice.id}` && response.request().method() === 'PUT'),
      profiledPracticeForm.getByRole('button', { name: 'Değişiklikleri kaydet' }).click(),
    ])
    const editedProfiledPractice = await editedPracticeResponse.json()
    assert.deepEqual([editedProfiledPractice.net, editedProfiledPractice.scoring_profile.version], [8, 1])
    const profileFocusQuestionResponse = await page.context().request.post(`${apiUrl}/questions`, { multipart: {
      ocr_text: 'Synthetic unattempted focus fixture', subject: 'Matematik', topic: 'Fonksiyon',
      curriculum_reference_json: '{}',
    } })
    assert.equal(profileFocusQuestionResponse.status(), 201)
    const profileFocusQuestion = await profileFocusQuestionResponse.json()
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    const refreshedProfilePracticeForm = page.getByRole('region', { name: 'Konu çalışma setleri' })
    await refreshedProfilePracticeForm.getByLabel('Puanlama profili', { exact: true }).selectOption(`${customProfile.profile_id}@1`)
    await page.getByRole('button', { name: 'Odaklı çalış · Matematik / Fonksiyon' }).click()
    const profiledFocusSection = page.getByRole('region', { name: 'Odaklı çalışma oturumu' })
    await profiledFocusSection.getByText('Kaydedilen kural: Custom Half Rule · v1').waitFor()
    await profiledFocusSection.getByRole('button', { name: 'Doğru artır' }).click()
    const [profiledFocusResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/practice' && response.request().method() === 'POST'),
      profiledFocusSection.getByRole('button', { name: 'Bitir ve kaydet' }).click(),
    ])
    const profiledFocusSession = await profiledFocusResponse.json()
    assert.deepEqual([profiledFocusSession.net, profiledFocusSession.scoring_profile.profile_id, profiledFocusSession.scoring_profile.version], [1, customProfile.profile_id, 1])
    const profileFocusQuestionDelete = await page.context().request.delete(`${apiUrl}/questions/${profileFocusQuestion.id}`)
    assert.equal(profileFocusQuestionDelete.status(), 200)
    await page.getByRole('button', { name: 'Ana Sayfa' }).click()
    await page.getByRole('button', { name: 'Deneme ekle' }).click()
    await page.getByRole('dialog').locator('select').first().selectOption('tyt')
    await page.getByLabel('Puanlama profili', { exact: true }).selectOption(`${customProfile.profile_id}@1`)
    await page.getByRole('button', { name: 'Ders ekle' }).click()
    await page.getByLabel('Ders adı 1').fill('Profile Fixture')
    await page.getByLabel('1. ders Doğru').fill('12')
    await page.getByLabel('1. ders Yanlış').fill('4')
    await page.getByLabel('1. ders Boş').fill('4')
    await page.getByText('10,00', { exact: true }).waitFor()
    const [profiledExamResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/exams' && response.request().method() === 'POST'),
      page.getByRole('button', { name: 'Denemeyi kaydet' }).click(),
    ])
    const profiledExam = await profiledExamResponse.json()
    assert.deepEqual([profiledExam.net, profiledExam.correct, profiledExam.incorrect, profiledExam.blank], [10, 12, 4, 4])
    assert.equal(profiledExam.scoring_profile.profile_id, customProfile.profile_id)
    assert.equal(profiledExam.scoring_profile.version, 1)
    const legacyProfileControl = await page.context().request.post(`${apiUrl}/exams`, { data: {
      date: '2026-11-15', exam_type: 'branch', subject: 'Legacy Control',
      correct: 12, incorrect: 4, blank: 4, duration_minutes: 30,
    } })
    assert.equal(legacyProfileControl.status(), 201)
    const legacyProfileExam = await legacyProfileControl.json()
    assert.equal(legacyProfileExam.net, 11)
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByLabel('Geçmişi puanlama profili sürümüne göre filtrele', { exact: true }).selectOption(`${customProfile.profile_id}@1`)
    assert.equal(await page.locator('tbody tr').count(), 1)
    await page.getByRole('cell', { name: '10,00', exact: true }).waitFor()
    await page.getByLabel('Geçmişi puanlama profili sürümüne göre filtrele', { exact: true }).selectOption('legacy-yks@1')
    assert.equal(await page.locator('tbody tr').count(), 1)
    await page.getByRole('cell', { name: '11,00', exact: true }).waitFor()
    await page.getByRole('button', { name: 'Puanlama profilleri' }).click()
    const [profileVersionResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === `/exam-profiles/${customProfile.profile_id}` && response.request().method() === 'PUT'),
      (async () => {
        const dialog = page.getByRole('dialog')
        await dialog.getByLabel('Özel profili düzenle').selectOption(customProfile.profile_id)
        await dialog.getByLabel('Yanlış yanıt cezası').fill('1')
        await dialog.getByRole('button', { name: 'Yeni sürüm olarak kaydet' }).click()
      })(),
    ])
    assert.equal(profileVersionResponse.status(), 200)
    assert.equal((await profileVersionResponse.json()).version, 2)
    await page.getByRole('dialog').getByRole('button', { name: 'Vazgeç' }).click()
    await page.getByLabel('Geçmişi puanlama profili sürümüne göre filtrele', { exact: true }).selectOption(`${customProfile.profile_id}@1`)
    await page.getByRole('cell', { name: '10,00', exact: true }).waitFor()
    await page.getByRole('button', { name: 'Deneme ekle' }).click()
    await page.getByLabel('Puanlama profili', { exact: true }).selectOption(`${customProfile.profile_id}@2`)
    await page.getByLabel('Ders', { exact: true }).fill('Version 2 Fixture')
    await page.getByLabel('Doğru', { exact: true }).fill('12')
    await page.getByLabel('Yanlış', { exact: true }).fill('4')
    await page.getByLabel('Boş', { exact: true }).fill('4')
    const [v2ExamResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/exams' && response.request().method() === 'POST'),
      page.getByRole('button', { name: 'Denemeyi kaydet' }).click(),
    ])
    const v2Exam = await v2ExamResponse.json()
    assert.deepEqual([v2Exam.scoring_profile.version, v2Exam.net], [2, 8])
    await page.getByLabel('Geçmişi puanlama profili sürümüne göre filtrele', { exact: true }).selectOption(`${customProfile.profile_id}@2`)
    assert.equal(await page.locator('tbody tr').count(), 1)
    await page.getByRole('cell', { name: '8,00', exact: true }).waitFor()
    await page.getByRole('button', { name: 'Deneme ekle' }).click()
    await page.getByLabel('Puanlama profili', { exact: true }).selectOption(`${customProfile.profile_id}@1`)
    await page.getByLabel('Ders', { exact: true }).fill('Blank Zero V1 Fixture')
    await page.getByLabel('Doğru', { exact: true }).fill('0')
    await page.getByLabel('Yanlış', { exact: true }).fill('0')
    await page.getByLabel('Boş', { exact: true }).fill('4')
    const [blankZeroExamResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/exams' && response.request().method() === 'POST'),
      page.getByRole('button', { name: 'Denemeyi kaydet' }).click(),
    ])
    const blankZeroExam = await blankZeroExamResponse.json()
    assert.deepEqual([blankZeroExam.net, blankZeroExam.blank, blankZeroExam.scoring_profile.version], [0, 4, 1])
    await page.getByLabel('Geçmişi puanlama profili sürümüne göre filtrele', { exact: true }).selectOption(`${customProfile.profile_id}@1`)
    assert.equal(await page.locator('tbody tr').count(), 2)
    await page.getByRole('cell', { name: '10,00', exact: true }).waitFor()
    await page.getByRole('cell', { name: '0,0', exact: true }).waitFor()
    await page.getByText('Ortalama net').locator('xpath=../..').getByText('5,00', { exact: true }).waitFor()

    // Exact red-team regression: correct=1, wrong=0, blank=1; four blanks
    // produce API net 4, XP 0, and must contribute to the Dashboard average.
    await page.getByRole('button', { name: 'Puanlama profilleri' }).click()
    const [blankProfileResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/exam-profiles' && response.request().method() === 'POST'),
      (async () => {
        const dialog = page.getByRole('dialog')
        await dialog.getByLabel('Görünen ad').fill('Blank Credit UI')
        await dialog.getByLabel('Ülke / bağlam etiketi').fill('Fixture')
        await dialog.getByLabel('Doğru yanıt puanı').fill('1')
        await dialog.getByLabel('Yanlış yanıt cezası').fill('0')
        await dialog.getByLabel('Boş yanıt puanı').fill('1')
        await dialog.getByRole('button', { name: 'Profil oluştur' }).click()
      })(),
    ])
    const blankProfile = await blankProfileResponse.json()
    await page.getByRole('dialog').getByRole('button', { name: 'Vazgeç' }).click()
    await page.getByRole('button', { name: 'Deneme ekle' }).click()
    await page.getByLabel('Puanlama profili', { exact: true }).selectOption(`${blankProfile.profile_id}@1`)
    await page.getByLabel('Ders', { exact: true }).fill('All Blank UI')
    await page.getByLabel('Doğru', { exact: true }).fill('0')
    await page.getByLabel('Yanlış', { exact: true }).fill('0')
    await page.getByLabel('Boş', { exact: true }).fill('4')
    await page.getByText('4,00', { exact: true }).waitFor()
    const [blankExamResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/exams' && response.request().method() === 'POST'),
      page.getByRole('button', { name: 'Denemeyi kaydet' }).click(),
    ])
    const blankExam = await blankExamResponse.json()
    assert.deepEqual([blankExam.net, blankExam.xp, blankExam.blank], [4, 0, 4])
    await page.getByLabel('Geçmişi puanlama profili sürümüne göre filtrele', { exact: true }).selectOption(`${blankProfile.profile_id}@1`)
    assert.equal(await page.locator('tbody tr').count(), 1)
    await page.getByRole('cell', { name: '4,00', exact: true }).waitFor()
    await page.getByText('Ortalama net').locator('xpath=../..').getByText('4,00', { exact: true }).waitFor()

    await page.context().request.delete(`${apiUrl}/exams/${profiledExam.id}`)
    await page.context().request.delete(`${apiUrl}/exams/${v2Exam.id}`)
    await page.context().request.delete(`${apiUrl}/exams/${blankZeroExam.id}`)
    await page.context().request.delete(`${apiUrl}/exams/${blankExam.id}`)
    await page.context().request.delete(`${apiUrl}/exams/${legacyProfileExam.id}`)

    const examCrudMs = Math.round(performance.now() - examCrudStarted)
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    const orderSection = page.getByRole('region', { name: 'Denemelerde çözüm sırası' })
    await orderSection.getByText('Sıra ve süre özeti için deneme geçmişinde bir satıra çift tıkla').waitFor()
    assert.equal(await orderSection.getByText('AYT · Geometri', { exact: true }).count(), 0)
    const questionManageStarted = performance.now()
    await page.getByRole('button', { name: 'Yanlışlarım' }).click()
    const textCard = page.locator(`article[data-question-id="${createdQuestion.id}"]`)
    await textCard.getByRole('button', { name: /Soruyu düzenle/ }).click()
    await textCard.getByLabel('Düzenle · Ders').fill('Edebiyat')
    await textCard.getByLabel('Düzenle · Soru metni').fill('Güncellenmiş soru metni')
    await textCard.getByText('İsteğe bağlı program referansı', { exact: true }).click()
    await textCard.getByLabel('Kendi kısa öğrenme çıktısı notun veya başka sözcüklerle anlatımın').fill('Explain a made-up pattern')
    await textCard.getByRole('button', { name: 'Kaydet' }).click()
    const updatedCard = page.locator('article').filter({ hasText: 'Güncellenmiş soru metni' })
    await updatedCard.getByRole('button', { name: /Soruyu sil Edebiyat/ }).waitFor()
    assert.equal((await (await localFetch(`${apiUrl}/questions/${createdQuestion.id}`)).json()).curriculum_reference.learning_outcome, 'Explain a made-up pattern')
    await page.getByLabel('Hatalarda ve program referanslarında ara').fill('Explain a made-up pattern')
    await updatedCard.waitFor()
    assert.equal(await page.locator('article[data-question-id]').count(), 1)
    await page.getByLabel('Hatalarda ve program referanslarında ara').fill('no matching synthetic outcome')
    await page.getByText('Bu aramayla eşleşen kayıtlı soru yok.').waitFor()
    await page.getByLabel('Hatalarda ve program referanslarında ara').fill('')
    const imageCard = page.locator('article[data-question-id="q1"]')
    page.once('dialog', (dialog) => dialog.accept())
    await imageCard.getByRole('button', { name: /Soruyu sil Matematik/ }).click()
    await imageCard.waitFor({ state: 'detached' })
    const questionManageMs = Math.round(performance.now() - questionManageStarted)
    const backupStarted = performance.now()
    await page.getByRole('button', { name: 'Ayarları aç' }).click()
    assert.equal(await page.getByRole('button', { name: 'Yedeği geri yükle' }).count(), 0)
    assert.equal(await page.getByText('python scripts/restore_backup.py hamartia-backup.zip').count(), 1)
    const settingsGet = await page.context().request.get(`${apiUrl}/settings`)
    assert.equal(settingsGet.status(), 200)
    assert.deepEqual(await settingsGet.json(), {
      litellm_base_url: 'http://localhost:4000/v1', model_name: 'ollama/qwen2.5', has_api_key: false,
    })
    const apiKeyInput = page.getByLabel('API anahtarı')
    await apiKeyInput.fill('smoke-secret')
    const [settingsSet] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/settings' && response.request().method() === 'PATCH'),
      page.getByRole('button', { name: 'Kaydet', exact: true }).click(),
    ])
    assert.deepEqual(await settingsSet.json(), {
      litellm_base_url: 'http://localhost:4000/v1', model_name: 'ollama/qwen2.5', has_api_key: true,
    })
    await page.getByText('Ayarlar kaydedildi.').waitFor()
    const settingsKeyPath = path.join(dataDir, 'settings.json')
    assert.equal(JSON.parse(await fs.readFile(settingsKeyPath, 'utf8')).api_key, 'smoke-secret')
    await page.getByLabel('Kayıtlı API anahtarını sil').check()
    const [settingsClear] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/settings' && response.request().method() === 'PATCH'),
      page.getByRole('button', { name: 'Kaydet', exact: true }).click(),
    ])
    assert.equal((await settingsClear.json()).has_api_key, false)
    assert.equal(JSON.parse(await fs.readFile(settingsKeyPath, 'utf8')).api_key, '')
    const settingsKeyManagementMs = Math.round(performance.now() - backupStarted)
    assert.match(await page.getByRole('link', { name: 'Yedeği indir' }).getAttribute('href'), /\/backup$/)
    const [backupDownload] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('link', { name: 'Yedeği indir' }).click(),
    ])
    assert.equal(backupDownload.suggestedFilename(), 'hamartia-backup.zip')
    assert.deepEqual((await fs.readFile(await backupDownload.path())).subarray(0, 2), Buffer.from('PK'))
    const backupDownloadMs = Math.round(performance.now() - backupStarted - settingsKeyManagementMs)
    await page.addInitScript((backendUrl) => {
      const profileKey = 'hamartia.smoke.chatgpt'
      window.hamartiaDesktop = {
        restoreBackup: async () => ({ status: 'cancelled' }),
        chatgpt: {
          status: async () => JSON.parse(localStorage.getItem(profileKey) || '{"connected":false}'),
          signIn: async () => {
            const profile = { connected: true, email: 'student@example.test', planUse: true }
            localStorage.setItem(profileKey, JSON.stringify(profile))
            return profile
          },
          signOut: async () => {
            const profile = { connected: false, savedAccount: true, email: 'student@example.test', revocationConfirmed: false }
            localStorage.setItem(profileKey, JSON.stringify(profile))
            return profile
          },
          forgetAccount: async () => {
            const profile = { connected: false }
            localStorage.setItem(profileKey, JSON.stringify(profile))
            return profile
          },
          recoverUnreadableCredentials: async (confirmed) => {
            window.__credentialRecoveryConfirmed = confirmed
            const profile = { connected: false, savedAccount: false, recoveredUnreadableCredentials: true, revocationConfirmed: false }
            localStorage.setItem(profileKey, JSON.stringify(profile))
            return profile
          },
          models: async () => [{ slug: 'mock-model', display_name: 'Mock model' }],
          openUsage: async () => {},
          onDelta: (callback) => {
            window.__mockAgentDelta = callback
            return () => { window.__mockAgentDelta = null }
          },
          chat: async (payload) => {
            window.__mockAgentPayload = payload
            if (payload.message === 'cancel me') return new Promise((resolve) => { window.__mockCancel = resolve })
            if (payload.workflow === 'practice-entry') {
              const fields = ['date', 'subject', 'topic', 'correct', 'incorrect', 'blank', 'duration_minutes', 'duration_seconds']
              const evidence_claims = payload.messages.flatMap((message) => [...message.matchAll(/(?:^|,\s*)(date|subject|topic|correct|incorrect|blank|duration_minutes|duration_seconds):\s*([^,]+)/g)]
                .filter((match) => fields.includes(match[1]))
                .map((match) => ({ field: match[1], quote: `${match[1]}: ${match[2].trim()}` })))
              const response = await localFetch(`${backendUrl}/practice/agent-draft`, {
                method: 'POST', headers: { 'content-type': 'application/json' },
                body: JSON.stringify({ messages: payload.messages, language: payload.language, evidence_claims,
                  scoring_profile_id: payload.scoring_profile_id, scoring_profile_version: payload.scoring_profile_version }),
              })
              const responseBody = await response.text()
              window.__practiceDraftHttp = { status: response.status, body: responseBody }
              if (!response.ok) return { status: 'failed', detail: responseBody }
              const draft = JSON.parse(responseBody)
              window.__practiceDraftResponse = draft
              if (payload.language === 'en' && payload.messages.length === 1 && payload.messages[0].startsWith('date: 2026-11-15')) {
                if (JSON.stringify(draft.missing) !== JSON.stringify(['topic'])) throw new Error(`Expected only the topic field to be missing; got ${JSON.stringify(draft.missing)}`)
                if (JSON.stringify(draft.questions) !== JSON.stringify(['Which topic did you practice?'])) throw new Error(`Unexpected practice clarification: ${JSON.stringify(draft.questions)}`)
              }
              return { status: 'completed', draft }
            }
            window.__mockAgentDelta?.({ requestId: payload.requestId, delta: 'A mocked study response.' })
            return { status: 'completed' }
          },
          cancel: async () => {
            window.__mockCancel?.({ status: 'cancelled' })
            return { cancelled: true }
          },
        },
      }
    }, apiUrl)
    await page.evaluate(() => localStorage.setItem('hamartia.language', 'en'))
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Study Agent' }).click()
    await page.getByRole('heading', { name: 'Study Agent' }).waitFor()
    await page.evaluate(() => {
      window.__rawProposalVisible = false
      const inspect = () => { if (document.body.innerText.includes('{"fields"')) window.__rawProposalVisible = true }
      new MutationObserver(inspect).observe(document.body, { childList: true, subtree: true, characterData: true })
      inspect()
    })
    await page.getByRole('button', { name: 'Continue with ChatGPT' }).click()
    await page.getByText('student@example.test').waitFor()
    const sendButton = page.getByRole('button', { name: 'Send to OpenAI' })
    await page.getByLabel('Your question').fill('What should I review next?')
    await page.getByText(/up to 8 topic-practice aggregates/).waitFor()
    assert.equal(await sendButton.isDisabled(), true)
    await page.getByRole('checkbox').check()
    await sendButton.click()
    await page.getByText('A mocked study response.').waitFor()
    assert.deepEqual(await page.evaluate(() => ({ ...window.__mockAgentPayload, requestId: undefined })), {
      message: 'What should I review next?', model: 'mock-model', language: 'en', workflow: 'chat', messages: [], consent: true, requestId: undefined,
    })
    await page.getByLabel('Study Agent mode').selectOption('practice-entry')
    await page.getByLabel('Scoring profile', { exact: true }).selectOption(`${customProfile.profile_id}@1`)
    const practiceEntry = 'date: 2026-11-15, subject: Mathematics, correct: 7, incorrect: 2, blank: 1, duration_minutes: 18, duration_seconds: 0'
    await page.getByLabel('Describe the practice set you completed').fill(practiceEntry)
    await page.getByRole('checkbox').check()
    await page.getByRole('button', { name: 'Send to OpenAI' }).click()
    try {
      await page.getByText('Which topic did you practice?').waitFor()
    } catch (error) {
      const state = await page.evaluate(() => ({
        language: localStorage.getItem('hamartia.language'),
        payload: window.__mockAgentPayload,
        draftHttp: window.__practiceDraftHttp,
        draft: window.__practiceDraftResponse,
        liveText: [...document.querySelectorAll('[aria-live]')].map((element) => element.innerText),
        bodyText: document.body.innerText.slice(-1200),
      }))
      console.error('Practice clarification smoke state:', JSON.stringify({ ...state, pageErrors, failedResponses, appRequests }))
      throw error
    }
    assert.equal(await page.evaluate(() => window.__rawProposalVisible), false)
    const noPrematureRecord = await (await localFetch(`${apiUrl}/practice`)).json()
    assert.equal(noPrematureRecord.some((session) => session.subject === 'Mathematics' && session.topic === 'Functions'), false)
    await page.getByLabel('Describe the practice set you completed').fill('topic: Functions')
    await page.getByRole('checkbox').check()
    await page.getByRole('button', { name: 'Send to OpenAI' }).click()
    await page.getByRole('heading', { name: 'Proposed practice set' }).waitFor()
    await page.getByText(/“correct: 7”/).waitFor()
    assert.equal(await page.evaluate(() => window.__rawProposalVisible), false)
    page.on('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: 'Approve this preview and save' }).click()
    await page.getByText('Practice set saved. You can start another entry.').waitFor()
    assert.deepEqual((await (await localFetch(`${apiUrl}/practice`)).json()).find((item) => item.date === '2026-11-15' && item.subject === 'Mathematics' && item.topic === 'Functions').scoring_profile,
      { ...customProfile, scoring_rule: { correct_points: '1/1', wrong_penalty: '1/2', blank_points: '0/1' } })
    assert.deepEqual(await page.evaluate(() => ({ ...window.__mockAgentPayload, requestId: undefined })), {
      message: 'topic: Functions',
      model: 'mock-model', language: 'en', workflow: 'practice-entry', messages: [practiceEntry, 'topic: Functions'], consent: true,
      scoring_profile_id: customProfile.profile_id, scoring_profile_version: 1, requestId: undefined,
    })
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Study Agent' }).click()
    await page.getByText('student@example.test').waitFor()
    assert.equal(await page.getByText('A mocked study response.').count(), 0)
    await page.getByLabel('Your question').fill('cancel me')
    await page.getByRole('checkbox').check()
    await page.getByRole('button', { name: 'Send to OpenAI' }).click()
    await page.getByRole('button', { name: 'Cancel request' }).waitFor()
    await page.getByRole('button', { name: 'Cancel request' }).click()
    await page.getByText('Request cancelled.').waitFor()
    await page.getByRole('button', { name: 'Sign out' }).click()
    await page.getByText(/OpenAI did not confirm remote revocation/).waitFor()
    await page.getByRole('button', { name: 'Use a different account' }).click()
    await page.getByText(/The local account link was removed/).waitFor()
    await page.evaluate(() => localStorage.setItem('hamartia.smoke.chatgpt', JSON.stringify({ connected: false, recoveryRequired: true })))
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Study Agent' }).click()
    await page.getByText(/cannot confirm whether OpenAI still has an active session/).waitFor()
    await page.getByRole('button', { name: 'Remove unreadable local connection' }).click()
    await page.getByText(/Remote revocation was not confirmed/).waitFor()
    assert.equal(await page.evaluate(() => window.__credentialRecoveryConfirmed), true)
    await page.evaluate(() => localStorage.setItem('hamartia.language', 'tr'))
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Çalışma Asistanı' }).click()
    await page.getByRole('heading', { name: 'Çalışma Asistanı' }).waitFor()
    await page.getByRole('button', { name: 'ChatGPT ile devam et' }).click()
    await page.getByText(/Bu istek için yazdığım sorunun/).waitFor()
    await page.getByText(/en fazla 8 konu çalışma özeti/).waitFor()
    const missingLabelForm = new FormData()
    missingLabelForm.set('ocr_text', 'Synthetic unlabelled question')
    const missingLabelResponse = await localFetch(`${apiUrl}/questions`, { method: 'POST', body: missingLabelForm })
    assert.equal(missingLabelResponse.status, 201)
    const missingLabelQuestion = await missingLabelResponse.json()
    await page.evaluate(() => localStorage.setItem('hamartia.language', 'en'))
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Study Plan' }).click()
    await page.getByText('Subject not specified', { exact: true }).first().waitFor()
    await page.getByText('Topic not specified', { exact: true }).first().waitFor()
    const unclassifiedEnglishCard = page.locator('article').filter({ has: page.getByRole('heading', { name: 'Topic not specified', exact: true }) }).first()
    await unclassifiedEnglishCard.getByText('Add a subject and topic to this question before starting focused practice.').waitFor()
    assert.equal(await unclassifiedEnglishCard.getByRole('button', { name: /Start focused practice/ }).count(), 0)
    await page.getByRole('button', { name: 'Cosmos' }).click()
    await page.getByText('Subject not specified', { exact: true }).first().waitFor()
    await page.getByText('Topic not specified', { exact: true }).first().waitFor()
    await page.evaluate(() => localStorage.setItem('hamartia.language', 'tr'))
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    await page.getByText('Ders belirtilmedi', { exact: true }).first().waitFor()
    await page.getByText('Konu belirtilmedi', { exact: true }).first().waitFor()
    const unclassifiedTurkishCard = page.locator('article').filter({ has: page.getByRole('heading', { name: 'Konu belirtilmedi', exact: true }) }).first()
    await unclassifiedTurkishCard.getByText('Odaklı çalışmayı başlatmak için önce bu soruya ders ve konu ekle.').waitFor()
    assert.equal(await unclassifiedTurkishCard.getByRole('button', { name: /Odaklı çalış/ }).count(), 0)
    await page.getByRole('button', { name: 'Cosmos' }).click()
    await page.getByText('Ders belirtilmedi', { exact: true }).first().waitFor()
    await page.getByText('Konu belirtilmedi', { exact: true }).first().waitFor()
    const missingLabelDelete = await localFetch(`${apiUrl}/questions/${missingLabelQuestion.id}`, { method: 'DELETE' })
    assert.equal(missingLabelDelete.ok, true)

    // A legacy practice draft is removed only after the durable clock PATCH succeeds.
    await page.evaluate(() => {
      localStorage.setItem('hamartia.language', 'en')
      localStorage.setItem('hamartia.active-practice-session', JSON.stringify({
        date: '2026-11-15', subject: 'Synthetic Math', topic: 'Migration check',
        correct: 2, incorrect: 1, blank: 0, elapsed_seconds: 9, running_since: Date.now() - 2_000,
      }))
    })
    await page.route(`${apiUrl}/clock`, async (route) => {
      if (route.request().method() === 'PATCH') {
        await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'intentional persistence failure' }) })
      } else await route.continue()
    })
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Clock' }).click()
    await page.getByRole('region', { name: 'Clock' }).getByText('Clock state could not be saved or loaded. Your previous saved state remains available.').waitFor()
    assert.ok(await page.evaluate(() => localStorage.getItem('hamartia.active-practice-session')))
    failedResponses.splice(0, failedResponses.length, ...failedResponses.filter((item) => !(new URL(item.url).pathname === '/clock' && item.status === 503)))
    const expectedConsoleErrors = consoleErrors.filter((item) => !(item.location.url === `${apiUrl}/clock` && item.text.includes('503 (Service Unavailable)')))
    consoleErrors.splice(0, consoleErrors.length, ...expectedConsoleErrors)
    await page.unroute(`${apiUrl}/clock`)
    await page.getByRole('region', { name: 'Clock' }).getByRole('button', { name: 'Retry loading' }).click()
    await page.getByLabel('Elapsed time').waitFor()
    await page.waitForFunction(() => localStorage.getItem('hamartia.active-practice-session') === null)
    const migratedClock = JSON.parse(await fs.readFile(path.join(dataDir, 'clock.json'), 'utf8'))
    assert.equal(migratedClock.active_timer.kind, 'practice')
    assert.equal(migratedClock.active_timer.practice_draft.topic, 'Migration check')
    assert.equal(migratedClock.active_timer.status, 'running')
    await page.getByRole('button', { name: 'Study Plan' }).click()
    const migratedPractice = page.getByRole('region', { name: 'Focused practice session' })
    await migratedPractice.waitFor()
    await migratedPractice.getByText('Focused practice · Synthetic Math / Migration check').waitFor()
    await migratedPractice.getByRole('button', { name: 'Cancel session' }).click()
    await page.getByRole('button', { name: 'Clock' }).click()
    await page.getByRole('button', { name: 'Countdown' }).click()
    await page.getByLabel('Minutes').fill('0')
    await page.getByLabel('Seconds').fill('3')
    const [clockStart] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/clock' && response.request().method() === 'PATCH'),
      page.getByRole('button', { name: 'Start', exact: true }).click(),
    ])
    assert.equal(clockStart.ok(), true)
    const [clockPause] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/clock'
        && response.request().method() === 'PATCH'
        && response.request().postDataJSON()?.active_timer?.status === 'paused'),
      page.getByRole('button', { name: 'Pause' }).click(),
    ])
    assert.equal(clockPause.ok(), true)
    assert.equal((await clockPause.json()).active_timer.status, 'paused')
    const pausedClock = JSON.parse(await fs.readFile(path.join(dataDir, 'clock.json'), 'utf8'))
    assert.equal(pausedClock.active_timer.status, 'paused')
    assert(pausedClock.active_timer.remaining_ms > 0 && pausedClock.active_timer.remaining_ms <= 3_000)
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Clock' }).click()
    await page.getByText('Paused', { exact: true }).waitFor()
    const [timerReset] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/clock' && response.request().method() === 'PATCH' && response.request().postDataJSON()?.active_timer?.status === 'paused'),
      page.getByRole('button', { name: 'Reset' }).click(),
    ])
    assert.equal(timerReset.ok(), true)
    const [timerCleared] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/clock' && response.request().method() === 'PATCH' && response.request().postDataJSON()?.active_timer === null),
      page.getByRole('button', { name: 'Stop and clear timer' }).click(),
    ])
    assert.equal(timerCleared.ok(), true)
    const futureReminder = await page.evaluate(() => {
      const date = new Date(Date.now() + 5 * 60_000)
      date.setSeconds(0, 0)
      return {
        date: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`,
        time: `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`,
      }
    })
    await page.getByLabel('Reminder label').fill('Synthetic reminder')
    await page.getByLabel('Time', { exact: true }).fill(futureReminder.time)
    await page.getByLabel('Date', { exact: true }).fill(futureReminder.date)
    const [reminderSave] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/clock' && response.request().method() === 'PATCH' && response.request().postDataJSON()?.alarms?.some((alarm) => alarm.label === 'Synthetic reminder')),
      page.getByRole('button', { name: 'Save reminder' }).click(),
    ])
    assert.equal(reminderSave.ok(), true)
    await page.getByText('Synthetic reminder', { exact: true }).waitFor()
    const savedClock = JSON.parse(await fs.readFile(path.join(dataDir, 'clock.json'), 'utf8'))
    assert.equal(savedClock.alarms.length, 1)
    assert.equal(savedClock.alarms[0].kind, 'once')
    assert.equal(savedClock.alarms[0].enabled, true)
    const dueAt = Date.now() + 5_000
    const dueAlarm = {
      id: 'smoke-due-away', label: 'Synthetic due while away', kind: 'once', local_time: '', weekdays: [],
      one_off_at_ms: dueAt, next_at_ms: dueAt, enabled: true, overdue_at_ms: null, last_fired_at_ms: null,
    }
    const seededClock = await page.request.patch(`${apiUrl}/clock`, { data: { ...savedClock, alarms: [...savedClock.alarms, dueAlarm] } })
    assert.equal(seededClock.status(), 200)
    let failDueAlarmWrite = true
    await page.route(`${apiUrl}/clock`, async (route) => {
      if (route.request().method() === 'PATCH') {
        const alarm = route.request().postDataJSON()?.alarms?.find((item) => item.id === dueAlarm.id)
        if (alarm?.overdue_at_ms === dueAt && failDueAlarmWrite) {
          failDueAlarmWrite = false
          await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'intentional due alarm persistence failure' }) })
          return
        }
      }
      await route.continue()
    })
    const dueAlarmWriteMatch = (response) => new URL(response.url()).pathname === '/clock'
      && response.request().method() === 'PATCH'
      && response.request().postDataJSON()?.alarms?.some((alarm) => alarm.id === dueAlarm.id && alarm.overdue_at_ms === dueAt)
    const failedDueAlarmWrite = page.waitForResponse((response) => dueAlarmWriteMatch(response) && response.status() === 503)
    const retriedDueAlarmWrite = page.waitForResponse((response) => dueAlarmWriteMatch(response) && response.status() === 200)
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Study Plan' }).click()
    await failedDueAlarmWrite
    await retriedDueAlarmWrite
    await page.unroute(`${apiUrl}/clock`)
    const dueDeadline = Date.now() + 8_000
    let dueState
    while (Date.now() < dueDeadline) {
      dueState = await (await localFetch(`${apiUrl}/clock`)).json()
      if (dueState.alarms.find((alarm) => alarm.id === dueAlarm.id)?.overdue_at_ms) break
      await new Promise((resolve) => setTimeout(resolve, 100))
    }
    assert.equal(dueState.alarms.find((alarm) => alarm.id === dueAlarm.id)?.overdue_at_ms, dueAt,
      'The always-mounted scheduler should persist a due alarm while the Clock tab is unmounted')
    await page.getByRole('button', { name: 'Clock' }).click()
    await page.getByText('Synthetic due while away', { exact: true }).waitFor()
    await page.getByText(/Overdue since/).waitFor()

    // A failed initial clock GET must not turn the empty placeholder into a writable state.
    const patchesBeforeUnavailableClock = appRequests.filter((request) => request.path === '/clock' && request.method === 'PATCH').length
    await page.route(`${apiUrl}/clock`, async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'intentional initial clock read failure' }) })
      } else await route.continue()
    })
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Clock' }).click()
    await page.getByRole('region', { name: 'Clock' }).getByText('Clock state could not be saved or loaded. Your previous saved state remains available.').waitFor()
    assert.equal(await page.getByRole('button', { name: 'Start', exact: true }).isDisabled(), true)
    assert.equal(appRequests.filter((request) => request.path === '/clock' && request.method === 'PATCH').length, patchesBeforeUnavailableClock)
    await page.unroute(`${apiUrl}/clock`)
    await page.getByRole('region', { name: 'Clock' }).getByRole('button', { name: 'Retry loading' }).click()
    await page.getByRole('button', { name: 'Start', exact: true }).waitFor({ state: 'visible' })
    await page.waitForFunction(() => Array.from(document.querySelectorAll('button')).some((button) => button.innerText.trim() === 'Start' && !button.disabled))
    assert.equal(await page.getByRole('button', { name: 'Start', exact: true }).isDisabled(), false)
    await page.evaluate(() => localStorage.setItem('hamartia.language', 'tr'))
    await page.reload({ waitUntil: 'networkidle' })
    const evidenceSuggestionResponse = await page.context().request.post(`${apiUrl}/questions`, { multipart: {
      ocr_text: 'Synthetic evidence suggestion fixture', subject: 'Fizik', topic: 'Mercekler',
      curriculum_reference_json: '{}',
    } })
    assert.equal(evidenceSuggestionResponse.status(), 201)
    const evidenceSuggestionQuestion = await evidenceSuggestionResponse.json()
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    let evidenceRegion = page.getByRole('region', { name: 'Önerilen bir konu üzerine düşün' })
    await evidenceRegion.waitFor()
    await evidenceRegion.getByLabel('Konu önerisi').selectOption({ label: 'Fizik · Mercekler' })
    const evidenceDate = await page.evaluate(() => {
      const now = new Date()
      return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
    })
    await evidenceRegion.getByLabel('Tarih').fill(evidenceDate)
    await evidenceRegion.getByLabel('Tamamladığın çalışma').fill('Üç yeni mercek sorusu çözdüm')
    await evidenceRegion.getByLabel('Ne gözlemledin?').fill('Işın çizimini önce çizince odağı daha hızlı buldum.')
    await evidenceRegion.getByLabel('Kaynak bağlantısı (isteğe bağlı)').fill('https://0x7f000001/lens-notes')
    const [savedEvidenceResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/learning-evidence' && response.request().method() === 'POST'),
      evidenceRegion.getByRole('button', { name: 'Yansımayı kaydet' }).click(),
    ])
    assert.equal(savedEvidenceResponse.status(), 201)
    let savedEvidence = await savedEvidenceResponse.json()
    const savedEvidenceId = savedEvidence.id
    assert.equal(savedEvidence.subject, 'Fizik')
    assert.equal(savedEvidence.topic, 'Mercekler')
    assert.equal(savedEvidence.date, evidenceDate)
    assert.equal(savedEvidence.activity, 'Üç yeni mercek sorusu çözdüm')
    assert.equal(savedEvidence.reference_url, 'https://0x7f000001/lens-notes')
    await evidenceRegion.getByRole('link', { name: 'Kaynağı aç (127.0.0.1)' }).waitFor()
    await evidenceRegion.getByText('Işın çizimini önce çizince odağı daha hızlı buldum.').waitFor()
    await page.evaluate(() => localStorage.setItem('hamartia.language', 'en'))
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Study Plan' }).click()
    const englishEvidenceRegion = page.getByRole('region', { name: 'Reflect on a suggested topic' })
    await englishEvidenceRegion.getByRole('link', { name: 'Open reference (127.0.0.1)' }).waitFor()
    await page.evaluate(() => localStorage.setItem('hamartia.language', 'tr'))
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    evidenceRegion = page.getByRole('region', { name: 'Önerilen bir konu üzerine düşün' })
    await evidenceRegion.waitFor()
    await evidenceRegion.getByRole('button', { name: 'Üç yeni mercek sorusu çözdüm yansımasını düzenle' }).click()
    await evidenceRegion.getByLabel('Ne gözlemledin?').fill('Yeni örneklerde de odağı daha hızlı buldum.')
    const [updatedEvidenceResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === `/learning-evidence/${savedEvidence.id}` && response.request().method() === 'PUT'),
      evidenceRegion.getByRole('button', { name: 'Değişiklikleri kaydet' }).click(),
    ])
    savedEvidence = await updatedEvidenceResponse.json()
    assert.equal(savedEvidence.observation, 'Yeni örneklerde de odağı daha hızlı buldum.')
    assert.equal(savedEvidence.id, savedEvidenceId)
    assert.deepEqual(Object.keys(savedEvidence).sort(), ['activity', 'created_at', 'date', 'id', 'observation', 'reference_url', 'subject', 'topic'])
    await evidenceRegion.getByRole('button', { name: 'Üç yeni mercek sorusu çözdüm yansımasını sil' }).click()
    await evidenceRegion.getByText('Henüz yansıma kaydedilmedi.').waitFor()
    assert.deepEqual(await (await localFetch(`${apiUrl}/learning-evidence`)).json(), [])
    assert.equal((await page.context().request.delete(`${apiUrl}/questions/${evidenceSuggestionQuestion.id}`)).status(), 200)
    failedResponses.splice(0, failedResponses.length, ...failedResponses.filter((item) => !(new URL(item.url).pathname === '/clock' && item.status === 503)))
    const expectedClockErrors = consoleErrors.filter((item) => item.location.url !== `${apiUrl}/clock` || !item.text.includes('503 (Service Unavailable)'))
    consoleErrors.splice(0, consoleErrors.length, ...expectedClockErrors)
    assert(appRequests.some((request) => request.path === '/questions/q1/attempt' && request.method === 'POST' && request.body.correct === false))
    assert(appRequests.some((request) => request.path === '/questions' && request.method === 'POST'))
    assert(appRequests.some((request) => request.path === `/questions/${createdQuestion.id}/attempt` && request.method === 'POST' && request.body.correct === true))
    assert(appRequests.some((request) => request.path === `/questions/${createdQuestion.id}/attempt` && request.body.attempt_day === localAttemptDay))
    assert(appRequests.some((request) => request.path === '/questions/insights' && request.query.today === localAttemptDay))
    assert(appRequests.some((request) => request.path === '/exams' && request.method === 'POST' && request.body.exam_type === 'ayt'))
    assert(appRequests.some((request) => request.path.startsWith('/exams/') && request.method === 'PUT' && request.body.exam_type === 'tyt'))
    assert(appRequests.some((request) => request.path.startsWith('/exams/') && request.method === 'DELETE'))
    assert(appRequests.some((request) => request.path === `/questions/${createdQuestion.id}` && request.method === 'PATCH' && request.body.subject === 'Edebiyat'))
    assert(appRequests.some((request) => request.path === '/questions/q1' && request.method === 'DELETE'))
    assert(appRequests.some((request) => request.path === '/backup' && request.method === 'GET'))
    assert.equal(appRequests.filter((request) => request.path === '/practice' && request.method === 'POST').length, 5)
    assert(!appRequests.some((request) => request.path === '/study-agent/local'))
    assert.deepEqual(appRequests.filter((request) => request.path.startsWith('/practice/agent-')).map((request) => request.path), ['/practice/agent-draft', '/practice/agent-draft', '/practice/agent-create'])
    const approvedAgentRequest = appRequests.find((request) => request.path === '/practice/agent-create')
    assert.equal(approvedAgentRequest.body.evidence_claims.length, 8)
    assert.equal(approvedAgentRequest.body.approval_id.length, 36)
    assert.equal(approvedAgentRequest.body.preview_digest.length, 64)
    assert(appRequests.some((request) => request.path === '/clock' && request.method === 'GET'))
    assert(appRequests.some((request) => request.path === '/clock' && request.method === 'PATCH'))
    assert(!appRequests.some((request) => !request.path.startsWith('/practice/agent-') && (request.path.includes('/agent') || request.path.endsWith('/analyze'))))
    assert.deepEqual(failedResponses, [])
    assert.deepEqual(pageErrors, [])
    assert.deepEqual(consoleErrors, [])
    const saved = JSON.parse(await fs.readFile(path.join(dataDir, 'questions.json'), 'utf8'))
    const savedPractice = JSON.parse(await fs.readFile(path.join(dataDir, 'practice_sessions.json'), 'utf8'))
    assert(savedPractice.some((session) => session.correct === 8 && session.topic === 'Fonksiyon'))
    assert(savedPractice.some((session) => session.subject === 'Mathematics' && session.topic === 'Functions' && session.correct === 7))
    assert(savedPractice.find((session) => session.id === practiceSession.id).duration_seconds >= elapsedAtFinish)
    assert.equal(savedPractice.filter((session) => session.topic === 'Fonksiyon').length, 9)
    assert.deepEqual(saved.find((question) => question.id === createdQuestion.id).review_attempts.map((item) => item.correct), [true])
    assert.equal(saved.find((question) => question.id === createdQuestion.id).review_attempts[0].attempt_day, localAttemptDay)
    assert.equal(saved.find((question) => question.id === createdQuestion.id).subject, 'Edebiyat')
    assert.equal(saved.find((question) => question.id === createdQuestion.id).ocr_text, 'Güncellenmiş soru metni')
    assert.equal(saved.find((question) => question.id === createdQuestion.id).curriculum_reference.learning_outcome, 'Explain a made-up pattern')
    assert.equal(saved.some((question) => question.id === 'q1'), false)
    assert.equal(saved.some((question) => question.id === profileFocusQuestion.id), false)
    assert.equal(saved.find((question) => question.id === linkedQuestion.id).exam_id.length > 0, true)
    assert.equal(saved.find((question) => question.id === linkedQuestion.id).solve_order, 1)
    assert.equal(await fs.access(path.join(uploads, 'q1.png')).then(() => true).catch(() => false), false)
    assert.deepEqual(JSON.parse(await fs.readFile(path.join(dataDir, 'exams.json'), 'utf8')), [])
    console.log(JSON.stringify({ benchmark: 'study_plan_and_local_crud_browser_smoke', navigation_ms: navigationMs, practice_session_persistence_ms: practiceSessionPersistenceMs, focused_session_ms: focusedSessionMs, practice_trend_and_history_ms: practiceTrendAndHistoryMs, capture_and_review_persistence_ms: captureAndPersistenceMs, exam_crud_ms: examCrudMs, question_edit_delete_ms: questionManageMs, settings_key_management_ms: settingsKeyManagementMs, backup_download_ms: backupDownloadMs, ai_included: false }))
  } catch (error) {
    if (serverErrors) process.stderr.write(serverErrors)
    throw error
  } finally {
    await cleanupResources()
    await fs.rm(path.join(path.dirname(dataDir), `.${path.basename(dataDir)}.lock`), { force: true })
    await fs.rm(dataDir, { recursive: true, force: true })
  }
}

const smokeRun = { cleanup: async () => {}, diagnostics: () => '' }
withDeadline(() => main(smokeRun), 8 * 60 * 1000, () => smokeRun.diagnostics(), (error) => smokeRun.cleanup(error)).catch((error) => {
  console.error(error)
  process.exitCode = 1
})
