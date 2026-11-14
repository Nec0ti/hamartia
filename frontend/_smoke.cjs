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
    const seedResponse = await fetch(`${apiUrl}/exams`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date: '2026-11-14', exam_type: 'branch', subject: 'Matematik', duration_minutes: 30, correct: 30, incorrect: 4, blank: 2 }),
    })
    if (!seedResponse.ok) throw new Error(`Locale fixture failed: ${await seedResponse.text()}`)
    const localeExam = await seedResponse.json()
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
    let linkedQuestion
    let practiceSession
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
        appRequests.push({ path: new URL(request.url()).pathname, method: request.method(), body: jsonBody ? request.postDataJSON() : null })
      }
    })

    const started = performance.now()
    await page.goto(baseUrl, { waitUntil: 'networkidle' })
    assert.equal(await page.locator('html').getAttribute('lang'), 'en')
    await page.getByRole('heading', { name: 'Overview' }).waitFor()
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
    const deleteFixture = await fetch(`${apiUrl}/exams/${localeExam.id}`, { method: 'DELETE' })
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
    await practiceSection.getByLabel('Doğru').fill('8')
    await practiceSection.getByLabel('Yanlış').fill('2')
    await practiceSection.getByLabel('Boş').fill('1')
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
    const [focusResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/practice' && response.request().method() === 'POST'),
      resumedSection.getByRole('button', { name: 'Bitir ve kaydet' }).click(),
    ])
    if (!focusResponse.ok()) throw new Error(`Focused practice save failed ${focusResponse.status()}: ${await focusResponse.text()}`)
    practiceSession = await focusResponse.json()
    await resumedSection.waitFor({ state: 'detached' })
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
    await practiceSection.locator('form').getByLabel('Doğru').fill('10')
    await practiceSection.getByRole('button', { name: 'Değişiklikleri kaydet' }).click()
    await practiceSection.getByText('92,3% cevaplanan doğruluğu').waitFor()
    if (!await oldHistory.evaluate((element) => element.open)) await oldHistory.locator('summary').click()
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: 'Seti sil 2 Kas 2026 Fonksiyon' }).click()
    await page.locator('details > summary').filter({ hasText: 'Önceki setler (1)' }).waitFor()
    const practiceTrendAndHistoryMs = Math.round(performance.now() - chartStarted)
    const focusedSessionMs = Math.round(performance.now() - focusStarted)

    const attempted = performance.now()
    await page.getByRole('button', { name: 'Yanlış çözdüm' }).click()
    await page.getByText('1 soru aralıklı tekrar için ileride açılacak.').waitFor()
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Çalışma Planı' }).click()
    await page.getByText('1 soru aralıklı tekrar için ileride açılacak.').waitFor()
    assert.equal(await page.getByRole('region', { name: 'Odaklı çalışma oturumu' }).count(), 0)
    await page.getByRole('button', { name: 'Yanlışlarım' }).click()
    await page.getByLabel('Ders').fill('Türkçe')
    await page.getByLabel('Konu').fill('Paragraf')
    await page.locator('textarea').fill('Metin tabanlı deneme sorusu')
    const [createdQuestionResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/questions' && response.request().method() === 'POST'),
      page.getByRole('button', { name: 'Soruyu kaydet' }).click(),
    ])
    createdQuestion = await createdQuestionResponse.json()
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
    await page.getByRole('dialog').locator('select').selectOption('branch')
    await page.getByLabel('Ders', { exact: true }).fill('Matematik')
    await page.getByRole('button', { name: 'Denemeyi kaydet' }).click()
    await page.getByRole('button', { name: /Denemeyi düzenle Matematik/ }).waitFor()
    await page.locator('tbody tr').filter({ hasText: 'Matematik' }).dblclick()
    await page.getByLabel('Sınavdaki soru no').fill('2')
    await page.getByLabel('Çözüm sırası').fill('1')
    await page.getByLabel('Soruda harcanan saniye').fill('32')
    await page.locator('textarea').fill('Denemeye bağlı yanlış soru')
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
    await page.getByRole('dialog').locator('select').selectOption('branch')
    await page.getByLabel('Ders', { exact: true }).fill('Geometri')
    await page.getByRole('button', { name: 'Değişiklikleri kaydet' }).click()
    await page.getByLabel('Deneme türü filtresi').selectOption('branch')
    await page.getByRole('button', { name: /Denemeyi sil Geometri/ }).waitFor()
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: /Denemeyi sil Geometri/ }).click()
    await page.getByText('Henüz deneme kaydı yok.').waitFor()

    await page.getByLabel('Deneme türü filtresi').selectOption('all')
    await page.getByRole('button', { name: 'Deneme ekle' }).click()
    await page.getByRole('dialog').locator('select').selectOption('tyt')
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
    await tytDetails.getByText('Türkçe: 30D / 5Y / 5B').waitFor()
    await tytDetails.getByRole('button', { name: /Yanlış ekle Türkçe/ }).click()
    await page.getByText(/Bağlı deneme: .*Türkçe \(TYT\)/).waitFor()
    await page.getByText('Bu bölümde 40 soru var.').waitFor()
    await page.getByLabel('Sınavdaki soru no').fill('40')
    await page.getByLabel('Çözüm sırası').fill('40')
    await page.getByLabel('Soruda harcanan saniye').fill('51')
    await page.locator('textarea').fill('TYT Türkçe bölüm sorusu')
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
    await page.getByRole('dialog').locator('select').selectOption('ayt')
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
    await textCard.getByRole('button', { name: 'Kaydet' }).click()
    const updatedCard = page.locator('article').filter({ hasText: 'Güncellenmiş soru metni' })
    await updatedCard.getByRole('button', { name: /Soruyu sil Edebiyat/ }).waitFor()
    const imageCard = page.locator('article[data-question-id="q1"]')
    page.once('dialog', (dialog) => dialog.accept())
    await imageCard.getByRole('button', { name: /Soruyu sil Matematik/ }).click()
    await imageCard.waitFor({ state: 'detached' })
    const questionManageMs = Math.round(performance.now() - questionManageStarted)
    const backupStarted = performance.now()
    await page.getByRole('button', { name: 'Ayarları aç' }).click()
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
    await page.getByLabel('Kayıtlı API anahtarını sil').check()
    const [settingsClear] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/settings' && response.request().method() === 'PATCH'),
      page.getByRole('button', { name: 'Kaydet', exact: true }).click(),
    ])
    assert.equal((await settingsClear.json()).has_api_key, false)
    const settingsKeyPath = path.join(dataDir, 'settings.json')
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
    assert(appRequests.some((request) => request.path === '/questions/q1/attempt' && request.method === 'POST' && request.body.correct === false))
    assert(appRequests.some((request) => request.path === '/questions' && request.method === 'POST'))
    assert(appRequests.some((request) => request.path === `/questions/${createdQuestion.id}/attempt` && request.method === 'POST' && request.body.correct === true))
    assert(appRequests.some((request) => request.path === '/exams' && request.method === 'POST' && request.body.exam_type === 'ayt'))
    assert(appRequests.some((request) => request.path.startsWith('/exams/') && request.method === 'PUT' && request.body.exam_type === 'tyt'))
    assert(appRequests.some((request) => request.path.startsWith('/exams/') && request.method === 'DELETE'))
    assert(appRequests.some((request) => request.path === `/questions/${createdQuestion.id}` && request.method === 'PATCH' && request.body.subject === 'Edebiyat'))
    assert(appRequests.some((request) => request.path === '/questions/q1' && request.method === 'DELETE'))
    assert(appRequests.some((request) => request.path === '/backup' && request.method === 'GET'))
    assert.equal(appRequests.filter((request) => request.path === '/practice' && request.method === 'POST').length, 2)
    assert(!appRequests.some((request) => request.path.includes('/agent') || request.path.endsWith('/analyze')))
    assert.deepEqual(failedResponses, [])
    assert.deepEqual(pageErrors, [])
    assert.deepEqual(consoleErrors, [])
    const saved = JSON.parse(await fs.readFile(path.join(dataDir, 'questions.json'), 'utf8'))
    const savedPractice = JSON.parse(await fs.readFile(path.join(dataDir, 'practice_sessions.json'), 'utf8'))
    assert(savedPractice.some((session) => session.correct === 8 && session.topic === 'Fonksiyon'))
    assert(savedPractice.find((session) => session.id === practiceSession.id).duration_seconds >= elapsedAtFinish)
    assert.equal(savedPractice.filter((session) => session.topic === 'Fonksiyon').length, 7)
    assert.deepEqual(saved.find((question) => question.id === createdQuestion.id).review_attempts.map((item) => item.correct), [true])
    assert.equal(saved.find((question) => question.id === createdQuestion.id).subject, 'Edebiyat')
    assert.equal(saved.find((question) => question.id === createdQuestion.id).ocr_text, 'Güncellenmiş soru metni')
    assert.equal(saved.some((question) => question.id === 'q1'), false)
    assert.equal(saved.find((question) => question.id === linkedQuestion.id).exam_id.length > 0, true)
    assert.equal(saved.find((question) => question.id === linkedQuestion.id).solve_order, 1)
    assert.equal(await fs.access(path.join(uploads, 'q1.png')).then(() => true).catch(() => false), false)
    assert.deepEqual(JSON.parse(await fs.readFile(path.join(dataDir, 'exams.json'), 'utf8')), [])
    console.log(JSON.stringify({ benchmark: 'study_plan_and_local_crud_browser_smoke', navigation_ms: navigationMs, practice_session_persistence_ms: practiceSessionPersistenceMs, focused_session_ms: focusedSessionMs, practice_trend_and_history_ms: practiceTrendAndHistoryMs, capture_and_review_persistence_ms: captureAndPersistenceMs, exam_crud_ms: examCrudMs, question_edit_delete_ms: questionManageMs, settings_key_management_ms: settingsKeyManagementMs, backup_download_ms: backupDownloadMs, ai_included: false }))
  } catch (error) {
    if (serverErrors) process.stderr.write(serverErrors)
    throw error
  } finally {
    await browser?.close()
    if (launcher.exitCode === null) {
      launcher.kill('SIGTERM')
      await new Promise((resolve) => launcher.once('exit', resolve))
    }
    await fs.rm(path.join(path.dirname(dataDir), `.${path.basename(dataDir)}.lock`), { force: true })
    await fs.rm(dataDir, { recursive: true, force: true })
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
