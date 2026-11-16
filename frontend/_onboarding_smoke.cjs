const assert = require('node:assert/strict')
const { spawn } = require('node:child_process')
const fs = require('node:fs/promises')
const os = require('node:os')
const path = require('node:path')
const { chromium } = require('playwright')

const api = 'http://127.0.0.1:8000'
const app = 'http://127.0.0.1:5174'

async function waitFor(url, child) {
  for (let i = 0; i < 150; i++) {
    if (child.exitCode !== null) throw new Error(`Dev server exited: ${child.exitCode}`)
    try { if ((await fetch(url, { signal: AbortSignal.timeout(1000) })).ok) return } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  throw new Error(`Timed out waiting for ${url}`)
}

async function main() {
  const dataDir = await fs.mkdtemp(path.join(os.tmpdir(), 'hamartia-onboarding-'))
  const python = process.env.HAMARTIA_PYTHON || 'python3'
  const child = spawn(python, [path.resolve(__dirname, '../scripts/dev.py')], {
    cwd: path.resolve(__dirname, '..'),
    env: { ...process.env, HAMARTIA_DATA_DIR: dataDir, HAMARTIA_FRONTEND_PORT: '5174', VITE_API_BASE: api },
    stdio: ['ignore', 'ignore', 'pipe'],
  })
  let stderr = ''
  child.stderr.setEncoding('utf8').on('data', (part) => { stderr += part })
  let browser
  try {
    await waitFor(`${api}/healthcheck/ready`, child)
    await waitFor(app, child)
    browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {}) })
    const page = await browser.newPage({ viewport: { width: 1000, height: 900 } })
    const requests = []
    const external = []
    const pageErrors = []
    const responseErrors = []
    page.on('pageerror', (error) => pageErrors.push(error.message))
    page.on('response', (response) => { if (response.status() >= 400) responseErrors.push({ url: response.url(), status: response.status() }) })
    page.on('request', (request) => {
      const url = new URL(request.url())
      if (![api, app].includes(url.origin)) external.push(url.origin)
      else if (url.origin === api) requests.push({ path: url.pathname, method: request.method(), body: request.postDataJSON?.() })
    })
    await page.route('**/*', (route) => [api, app].includes(new URL(route.request().url()).origin) ? route.fallback() : route.abort())
    await page.goto(app, { waitUntil: 'domcontentloaded' })
    try { await page.getByRole('heading', { name: 'Choose your language' }).waitFor() } catch (error) {
      throw new Error(`${error.message}; page=${(await page.locator('body').innerText()).slice(0, 1000)}; requests=${JSON.stringify(requests)}; responseErrors=${JSON.stringify(responseErrors)}; pageErrors=${JSON.stringify(pageErrors)}`)
    }
    assert.equal(await page.locator('html').getAttribute('lang'), 'en')
    await page.getByRole('button', { name: 'Next' }).click()
    await page.getByRole('heading', { name: 'A quick tour' }).waitFor()
    assert.equal(await page.evaluate(() => document.activeElement?.textContent?.trim()), 'Next', 'focus should stay on the next-step control')
    for (let i = 0; i < 3; i++) await page.getByRole('button', { name: 'Next' }).click()
    await page.getByRole('button', { name: 'Continue to profile' }).click()
    await page.getByRole('heading', { name: 'Set up your study profile' }).waitFor()
    assert.equal(await page.getByRole('button', { name: 'Comet, unlocks at level 2' }).isDisabled(), true)
    await page.getByLabel('Age in years (optional)').fill('4')
    await page.getByRole('button', { name: 'Save and finish' }).click()
    await page.getByRole('alert').getByText('Enter an age in whole years from 5 to 120.').waitFor()
    await page.getByLabel('Age in years (optional)').fill('17')
    await page.getByLabel('Nickname (optional)').focus()
    await page.keyboard.type('Synthetic student')
    assert.equal(await page.getByLabel('Nickname (optional)').inputValue(), 'Synthetic student', 'keyboard typing should stay in the active field')
    await page.getByLabel('Grade or year (optional)').fill('11')
    await page.getByLabel('Curriculum (optional)').fill('Custom / Türkiye')
    await page.getByLabel('Study preferences (optional)').fill('Short sessions')
    await page.getByLabel('Study goals (optional)').fill('Review algebra')
    await page.getByRole('button', { name: 'Moon' }).click()
    const [saveResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/student-profile' && response.request().method() === 'PUT'),
      page.getByRole('button', { name: 'Save and finish' }).click(),
    ])
    assert.equal(saveResponse.status(), 200)
    const saved = await saveResponse.json()
    assert.deepEqual(saved.profile, { nickname: 'Synthetic student', age_years: 17, grade_year: '11', curriculum: 'Custom / Türkiye', study_preferences: 'Short sessions', study_goals: 'Review algebra', avatar_preset: 'moon' })
    await page.getByRole('heading', { name: 'Overview' }).waitFor()

    await page.getByRole('button', { name: 'Open settings' }).click()
    await page.getByRole('button', { name: 'Replay welcome tour' }).click()
    await page.getByRole('heading', { name: 'A quick tour' }).waitFor()
    await page.getByRole('button', { name: 'Skip tour' }).click()
    await page.getByRole('heading', { name: 'Overview' }).waitFor()
    await page.getByRole('button', { name: 'Open settings' }).click()
    await page.getByRole('button', { name: 'Edit student profile' }).click()
    await page.getByLabel('Nickname (optional)').fill('Edited synthetic')
    const [editResponse] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === '/student-profile' && response.request().method() === 'PUT'),
      page.getByRole('button', { name: 'Save profile' }).click(),
    ])
    assert.equal((await editResponse.json()).profile.nickname, 'Edited synthetic')
    await page.getByRole('button', { name: 'Delete profile and restart welcome setup' }).click()
    await page.getByRole('button', { name: 'Delete', exact: true }).click()
    await page.getByRole('heading', { name: 'Choose your language' }).waitFor()
    await page.locator('#onboarding-language').selectOption('tr')
    await page.getByRole('button', { name: 'İleri' }).click()
    await page.getByRole('heading', { name: 'Kısa bir tanıtım' }).waitFor()
    await page.getByRole('button', { name: 'Tanıtımı atla' }).click()
    await page.getByRole('heading', { name: 'Çalışma profilini oluştur' }).waitFor()
    assert.equal(await page.getByRole('button', { name: 'Kuyruklu yıldız, 2. seviyede açılır' }).isDisabled(), true)
    await page.getByRole('button', { name: 'Şimdilik geç' }).click()
    await page.getByRole('heading', { name: 'Genel bakış' }).waitFor()
    const finalState = await (await fetch(`${api}/student-profile`)).json()
    assert.equal(finalState.tutorial_skipped, true)
    assert.equal(finalState.survey_completed, true)
    assert.equal(finalState.profile.nickname, null)
    assert.deepEqual(external, [])
    assert.equal(requests.some(({ path }) => path.startsWith('/study-agent')), false)
    assert.equal(requests.filter(({ path }) => path === '/student-profile').length >= 7, true)
    assert.equal(await page.locator('html').getAttribute('lang'), 'tr')
    assert.equal(await page.evaluate(() => localStorage.getItem('hamartia.language')), 'tr')
    assert.deepEqual(await page.locator('body').evaluate((body) => body.innerText.match(/(?:onboarding|profile)\.[a-z.]+/g)), null)
    console.log('Onboarding browser smoke passed: EN completion/validation, local save/edit/reset, tutorial revisit/skip, TR skip, and zero provider requests.')
    await browser.close()
    browser = null
    child.kill('SIGTERM')
    await new Promise((resolve) => child.once('exit', resolve))
    await fs.rm(dataDir, { recursive: true, force: true })
  } catch (error) {
    if (browser) await browser.close().catch(() => {})
    if (child.exitCode === null) child.kill('SIGTERM')
    await new Promise((resolve) => child.exitCode !== null ? resolve() : child.once('exit', resolve))
    await fs.rm(dataDir, { recursive: true, force: true })
    throw new Error(`${error.message}${stderr ? `\n${stderr}` : ''}`)
  }
}

main().catch((error) => { console.error(error); process.exitCode = 1 })
