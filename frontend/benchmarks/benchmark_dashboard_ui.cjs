const assert = require('node:assert/strict')
const { spawn } = require('node:child_process')
const fs = require('node:fs/promises')
const os = require('node:os')
const path = require('node:path')
const { performance } = require('node:perf_hooks')
const { chromium } = require('playwright')
const { dashboardExamHistory } = require('../smokeFixtures.cjs')
const { withTimeout, withDeadline } = require('../smokeDeadline.cjs')

const API_URL = 'http://127.0.0.1:8000'
const FRONTEND_PORT = process.env.HAMARTIA_BENCH_FRONTEND_PORT || '5174'
const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`
const EXAM_COUNT = 512
const REPEATS = 3

async function waitForServer(child, url, name) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (child.exitCode !== null) throw new Error(`${name} exited early (${child.exitCode})`)
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1000) })
      if (response.ok) return
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  throw new Error(`Timed out waiting for ${name}`)
}

function formatNet(value) {
  const rounded = Math.round(value * 100) / 100
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: rounded === 0 ? 1 : 2,
    maximumFractionDigits: 2,
  }).format(rounded)
}

function expectedRows(exams) {
  const dateFormat = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeZone: 'UTC' })
  let priorNet = null
  return exams.map((exam) => {
    const net = exam.correct - exam.incorrect / 4
    const change = priorNet === null ? 'No previous exam' : `${net - priorNet > 0 ? '+' : ''}${formatNet(net - priorNet)}`
    priorNet = net
    return [
      dateFormat.format(new Date(`${exam.date}T00:00:00Z`)),
      exam.subject,
      formatNet(net),
      change,
    ]
  })
}

async function rowsFor(page, id) {
  return page.locator(`#${id} tbody tr`).evaluateAll((rows) => rows.map((row) => [...row.cells].map((cell) => cell.textContent.trim())))
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b)
  return sorted[Math.floor(sorted.length / 2)]
}

async function benchmarkRun(browser, exams, index) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const page = await context.newPage()
  const scriptRequests = []
  const apiPaths = []
  const externalOrigins = []
  const pageErrors = []
  const consoleErrors = []
  const frontendOrigin = new URL(FRONTEND_URL).origin
  const apiOrigin = new URL(API_URL).origin
  const allowedOrigins = new Set([frontendOrigin, apiOrigin])

  page.on('request', (request) => {
    let url
    try { url = new URL(request.url()) } catch { return }
    if (!allowedOrigins.has(url.origin)) externalOrigins.push(url.origin)
    if (url.origin === apiOrigin) apiPaths.push(url.pathname)
    if (url.origin === frontendOrigin && request.resourceType() === 'script') {
      scriptRequests.push({ request, requestedAt: performance.now() })
    }
  })
  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  await page.route('**/*', async (route) => {
    const { origin } = new URL(route.request().url())
    if (allowedOrigins.has(origin)) await route.fallback()
    else await route.abort()
  })

  const readyStarted = performance.now()
  await page.goto(FRONTEND_URL, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'Overview' }).waitFor()
  const trendTable = page.locator('#exam-net-trend-data')
  const changeTable = page.locator('#exam-net-change-data')
  try {
    await trendTable.waitFor({ timeout: 10_000 })
    await changeTable.waitFor({ timeout: 10_000 })
  } catch (error) {
    const response = await fetch(`${API_URL}/exams`)
    process.stderr.write(JSON.stringify({
      debug: 'dashboard chart tables were not rendered',
      api_status: response.status,
      api_exam_count: response.ok ? (await response.json()).length : null,
      body: await page.locator('body').innerText(),
      pageErrors,
      consoleErrors,
    }, null, 2) + '\n')
    throw error
  }
  const dashboardReadyMs = Math.round(performance.now() - readyStarted)

  const expected = expectedRows(exams)
  const trendRows = await rowsFor(page, 'exam-net-trend-data')
  const changeRows = await rowsFor(page, 'exam-net-change-data')
  assert.equal(trendRows.length, EXAM_COUNT, `repeat ${index + 1}: net trend covers all seeded exams`)
  assert.equal(changeRows.length, EXAM_COUNT, `repeat ${index + 1}: net change covers all seeded exams`)
  assert.deepEqual(trendRows, expected, 'net trend summary contains every expected net and previous-exam change')
  assert.deepEqual(changeRows, expected, 'each chart summary matches the independent net and previous-exam oracle')
  assert.equal(await page.getByRole('img', { name: 'Net trend · All subjects' }).count(), 1)
  assert.equal(await page.getByRole('img', { name: 'Change since previous exam · All subjects' }).count(), 1)

  const initialScripts = scriptRequests.map(({ request }) => request.url())
  assert.equal(initialScripts.some((url) => /\/src\/tabs\/(StudyAgentTab|ClockTab)\.jsx/.test(url)), false,
    'non-dashboard tabs must remain absent from initial module requests')
  const scriptCountBeforeSelection = scriptRequests.length
  const tabStarted = performance.now()
  await page.getByRole('button', { name: 'Study Agent' }).click()
  await page.getByRole('heading', { name: 'Study Agent' }).waitFor()
  await page.waitForLoadState('networkidle')
  const selectedTabReadyMs = Math.round(performance.now() - tabStarted)
  const selectedScripts = scriptRequests.slice(scriptCountBeforeSelection)
  const agentModule = selectedScripts.find(({ request }) => /\/src\/tabs\/StudyAgentTab\.jsx/.test(request.url()))
  assert(agentModule, 'selecting Study Agent requests its deferred module')
  const agentModuleResponse = await agentModule.request.response()
  assert(agentModuleResponse?.ok(), 'Study Agent lazy module response succeeds')
  const moduleTransferBytes = (await agentModuleResponse.body()).byteLength
  assert(moduleTransferBytes > 0)
  const initialModuleBytes = (await Promise.all(scriptRequests.slice(0, scriptCountBeforeSelection).map(async ({ request }) => {
    const response = await request.response()
    return response?.ok() ? (await response.body()).byteLength : 0
  }))).reduce((sum, bytes) => sum + bytes, 0)
  assert.deepEqual(externalOrigins, [], 'the benchmark makes no external requests')
  assert.equal(apiPaths.some((pathname) => pathname.includes('analyze') || pathname.includes('agent-') || pathname.includes('study-agent')), false,
    'selecting a tab does not dispatch an AI/provider request')
  assert.deepEqual(pageErrors, [])
  assert.deepEqual(consoleErrors, [])

  await context.close()
  return {
    repeat: index + 1,
    exam_count: EXAM_COUNT,
    trend_summary_rows: trendRows.length,
    change_summary_rows: changeRows.length,
    initial_dashboard_module_requests: initialScripts.length,
    initial_dashboard_module_bytes: initialModuleBytes,
    deferred_module_requests_after_selection: selectedScripts.length,
    study_agent_module_bytes: moduleTransferBytes,
    dashboard_to_chart_summary_ms: dashboardReadyMs,
    tab_selection_to_render_ms: selectedTabReadyMs,
    ai_included: false,
    provider_calls: 0,
  }
}

async function main(run) {
  const dataDir = await fs.mkdtemp(path.join(os.tmpdir(), 'hamartia-dashboard-benchmark-'))
  const exams = dashboardExamHistory(EXAM_COUNT)
  await fs.writeFile(path.join(dataDir, 'onboarding.json'), JSON.stringify({
    tutorial_completed: true,
    tutorial_skipped: false,
    survey_completed: true,
    profile: { nickname: null, age_years: null, grade_year: null, curriculum: null, study_preferences: null, study_goals: null, avatar_preset: null },
  }))
  await fs.writeFile(path.join(dataDir, 'exams.json'), JSON.stringify(exams))

  const python = process.env.HAMARTIA_PYTHON || (process.platform === 'win32' ? 'python' : 'python3')
  const launcher = spawn(python, [path.resolve(__dirname, '../../scripts/dev.py')], {
    cwd: path.resolve(__dirname, '../..'),
    env: { ...process.env, HAMARTIA_DATA_DIR: dataDir, HAMARTIA_FRONTEND_PORT: FRONTEND_PORT, VITE_API_BASE: API_URL },
    stdio: ['ignore', 'ignore', 'pipe'],
  })
  let serverErrors = ''
  launcher.stderr.setEncoding('utf8').on('data', (chunk) => { serverErrors += chunk })
  let browser
  let cleanupPromise
  const cleanup = async () => {
    if (!cleanupPromise) cleanupPromise = (async () => {
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
        try { await withTimeout(exited, 5000, 'Dev server shutdown') } catch {
          launcher.kill('SIGKILL')
          await withTimeout(exited, 2000, 'Dev server forced shutdown')
        }
      }
      await fs.rm(path.join(path.dirname(dataDir), `.${path.basename(dataDir)}.lock`), { force: true })
      await fs.rm(dataDir, { recursive: true, force: true })
    })()
    return cleanupPromise
  }
  run.cleanup = cleanup

  try {
    await waitForServer(launcher, `${API_URL}/healthcheck/ready`, 'API')
    await waitForServer(launcher, FRONTEND_URL, 'frontend')
    browser = await chromium.launch({
      timeout: 30_000,
      headless: true,
      ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {}),
    })
    const repeats = []
    for (let index = 0; index < REPEATS; index += 1) repeats.push(await benchmarkRun(browser, exams, index))
    const summary = (key) => {
      const values = repeats.map((repeat) => repeat[key])
      return { values, median: median(values), min: Math.min(...values), max: Math.max(...values) }
    }
    console.log(JSON.stringify({
      benchmark: 'dashboard_large_history_and_lazy_tab',
      browser: 'Playwright Chromium headless',
      environment: 'Vite development server; module body bytes are development responses, not production bundle sizes',
      repeats,
      timing_summary_ms: {
        dashboard_to_chart_summary: summary('dashboard_to_chart_summary_ms'),
        study_agent_selection_to_render: summary('tab_selection_to_render_ms'),
      },
      chart_rows_verified_per_repeat: EXAM_COUNT,
      ai_included: false,
      provider_calls: 0,
      external_network_allowed: false,
      timing_thresholds_used: false,
    }, null, 2))
  } catch (error) {
    if (serverErrors) process.stderr.write(serverErrors)
    throw error
  } finally {
    await cleanup()
  }
}

const run = { cleanup: async () => {} }
withDeadline(() => main(run), 8 * 60 * 1000, () => '', (error) => run.cleanup(error)).catch((error) => {
  console.error(error)
  process.exitCode = 1
})
