const assert = require('node:assert/strict')
const { spawn } = require('node:child_process')
const { createServer } = require('node:net')
const path = require('node:path')
const { chromium } = require('playwright')

const pages = [
  '', 'system-architecture/', 'purpose-and-scope/', 'study-workflows/', 'cosmos-and-progression/', 'mistakes-and-review/',
  'exam-formats-and-maarif/', 'install/', 'study-agent/', 'privacy-and-consent/',
  'backup-and-restore/', 'clock-and-reminders/', 'accessibility-and-language/',
  'learning-evidence/', 'faq/', 'troubleshooting/', 'contributing/',
]

async function freePort() {
  const server = createServer()
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const { port } = server.address()
  await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()))
  return port
}

async function waitForServer(url, server) {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    if (server.exitCode !== null) throw new Error(`Docs server exited with ${server.exitCode}`)
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error('Docs server did not become ready')
}

async function main() {
  const port = await freePort()
  const root = path.resolve(__dirname, '..')
  const server = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1', '--directory', path.join(root, 'docs')], { stdio: 'ignore' })
  let browser
  try {
    const base = `http://127.0.0.1:${port}/`
    await waitForServer(base, server)
    browser = await chromium.launch({
      headless: true,
      ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {}),
    })
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } })
    const localeSnapshots = { en: [], tr: [] }
    const externalRequests = []
    page.on('request', request => {
      if (!request.url().startsWith(base)) externalRequests.push(request.url())
    })

    for (const lang of ['en', 'tr']) {
      const prefix = lang === 'tr' ? 'tr/' : ''
      for (let index = 0; index < pages.length; index += 1) {
        const route = `${prefix}${pages[index]}`
        await page.goto(new URL(route, base).href, { waitUntil: 'networkidle' })
        assert.equal(await page.locator('html').getAttribute('lang'), lang, `${route} language`)
        assert.equal(await page.locator('main#content h1').count(), 1, `${route} has exactly one H1`)
        assert.equal(await page.locator('.sidebar [aria-current="page"]').count(), 1, `${route} has one active nav item`)
        assert.equal(await page.locator('.sidebar li').count(), pages.length, `${route} nav parity`)
        assert.equal(await page.locator('.sidebar details').count(), 3, `${route} has grouped navigation`)
        assert.equal(await page.locator('.sidebar details[open] [aria-current="page"]').count(), 1, `${route} expands the active group`)
        assert.equal(await page.locator('.sidebar .nav-group:first-of-type li:first-child a').getAttribute('href'), index === 0 ? './' : '../', `${route} starts with Getting Started`)
        assert.equal(await page.locator('main#content h1 + .page-description').count(), 1, `${route} places a subtitle after the page title`)
        assert.equal(await page.locator('.page-toc a').count(), await page.locator('main article h2').count(), `${route} has an in-page link for each section`)
        assert.equal(await page.locator('.product-nav a').count(), 3, `${route} has product navigation`)
        assert.equal(await page.locator('.product-nav a').first().innerText(), lang === 'en' ? 'User Manual' : 'Kullanım kılavuzu', `${route} has the active manual tab`)
        assert.equal(await page.locator('.edition').innerText(), lang === 'en' ? 'Desktop package · v0.1.0' : 'Masaüstü paketi · v0.1.0', `${route} shows the packaged app version`)
        assert.equal(await page.locator('.site-footer a[href$="/issues/new"]').count(), 1, `${route} has a feedback link`)
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${route} overflows at 390px`)
        assert.equal(await page.locator('main article h2').count() >= 1, true, `${route} contains article sections`)

        if (route.includes('cosmos-and-progression/')) {
          const article = await page.locator('main article').innerText()
          assert.match(article, lang === 'en' ? /XP, level, streak, and orbit position do not establish knowledge, mastery/ : /XP, seviye, seri ve yörünge konumu bilgiyi, ustalığı/)
        }
        if (route.includes('mistakes-and-review/')) {
          const article = await page.locator('main article').innerText()
          for (const label of lang === 'en'
            ? ['Knowledge gap', 'Distractor trap', 'Misread the question', 'Time pressure']
            : ['Konu eksiği', 'Çeldirici tuzağı', 'Soruyu yanlış okuma', 'Zaman baskısı']) {
            assert.equal(article.includes(label), true, `${route} missing visible UI label ${label}`)
          }
        }
        if (route.includes('learning-evidence/')) {
          const article = await page.locator('main article').innerText()
          for (const phrase of lang === 'en'
            ? ['activity you completed', 'your own report', 'pass hostname syntax checks', 'host as your browser parses it', 'does not fetch links']
            : ['tamamladığın çalışmayı', 'kendi beyanındır', 'ana bilgisayar adı sözdizimi denetimini', 'tarayıcının yorumladığı ana bilgisayar adını', 'bağlantıları getirmez']) {
            assert.equal(article.toLowerCase().includes(phrase.toLowerCase()), true, `${route} missing learning evidence boundary: ${phrase}`)
          }
        }
        if (route.includes('study-agent/')) {
          const article = await page.locator('main article').innerText()
          for (const phrase of lang === 'en'
            ? ['OpenAI-compatible server (local or remote)', 'remote host', 'http://localhost:11434/v1/', 'qwen3:8b', 'http://localhost:1234/v1', 'configured or last-used port', '/v1/models', 'remote operator']
            : ['OpenAI uyumlu sunucu (yerel veya uzak)', 'uzaktaki bir sunucuyu', 'http://localhost:11434/v1/', 'qwen3:8b', 'http://localhost:1234/v1', 'yapılandırılan veya son kullanılan port', '/v1/models', 'uzak işletmeci']) {
            assert.equal(article.toLowerCase().includes(phrase.toLowerCase()), true, `${route} missing local/remote endpoint setup clarity: ${phrase}`)
          }
          for (const phrase of lang === 'en'
            ? ['sectioned TYT/AYT exam', 'section count', '1–6 explicitly named sections', 'profile is selected on this device before provider dispatch', 'transcript and signed continuation state are not persisted']
            : ['Bölümlü TYT/AYT denemesi', 'bölüm sayısını', '1–6 bölümle', 'puanlama profili sağlayıcıya gönderilmeden önce bu cihazda seçilir', 'konuşma ve imzalı devam durumu saklanmaz']) {
            assert.equal(article.toLowerCase().includes(phrase.toLowerCase()), true, `${route} missing sectioned-exam flow contract: ${phrase}`)
          }
          for (const href of [
            'https://docs.ollama.com/api/openai-compatibility', 'https://ollama.com/library/qwen3',
            'https://lmstudio.ai/docs/developer/openai-compat', 'https://lmstudio.ai/docs/developer/openai-compat/models',
            'https://lmstudio.ai/docs/cli/serve/server-start',
          ]) assert.equal(await page.locator(`a[href="${href}"]`).count(), 1, `${route} missing official provider source ${href}`)
        }
        if (route.includes('privacy-and-consent/')) {
          const article = await page.locator('main article').innerText()
          for (const phrase of lang === 'en'
            ? ['Sectioned TYT/AYT exam capture', 'student transcript', 'profile ID, rules, and snapshot stay host-side', 'not conversational facts', 'not persisted']
            : ['Bölümlü TYT/AYT denemesi kaydı', 'öğrenci konuşmasını', 'kimlik, kurallar ve anlık görüntü ana bilgisayarda kalır', 'konuşma bilgisi sayılmaz', 'saklanmaz']) {
            assert.equal(article.toLowerCase().includes(phrase.toLowerCase()), true, `${route} missing sectioned-exam privacy boundary: ${phrase}`)
          }
          for (const phrase of lang === 'en'
            ? ['Student profile', 'age in whole years', 'stay out of Study Agent and question-analysis', 'official alignment']
            : ['Öğrenci profili', 'tam yıl olarak yaş', 'Çalışma Asistanı veya soru analizi isteklerine dahil edilmez', 'resmî uyum']) {
            assert.equal(article.toLowerCase().includes(phrase.toLowerCase()), true, `${route} missing local-profile privacy boundary: ${phrase}`)
          }
        }
        if (pages[index] === '') {
          const article = await page.locator('main article').innerText()
          for (const phrase of lang === 'en'
            ? ['first launch', 'English is selected by default', 'short walkthrough', 'optional survey', 'replay the walkthrough']
            : ['İlk açılışta', 'varsayılan dil İngilizcedir', 'kısa tanıtım', 'isteğe bağlı anket', 'tanıtımı yeniden aç']) {
            assert.equal(article.toLowerCase().includes(phrase.toLowerCase()), true, `${route} missing first-run onboarding guidance: ${phrase}`)
          }
        }

        const languageLink = page.locator('.header-actions .language-link')
        const target = new URL(await languageLink.getAttribute('href'), page.url())
        assert.equal(target.pathname, lang === 'en'
          ? `/tr/${pages[index]}`
          : `/${pages[index]}`, `${route} language counterpart`)

        const sectionIds = await page.locator('main article h2').evaluateAll(nodes => nodes.map(node => node.id))
        const tocIds = await page.locator('.page-toc a').evaluateAll(nodes => nodes.map(node => new URL(node.href).hash.slice(1)))
        assert.deepEqual(tocIds, sectionIds, `${route} contents match section anchors`)
        localeSnapshots[lang].push({ route, sectionIds })

        const hrefs = await page.locator('a[href]').evaluateAll(nodes => nodes.map(node => node.href))
        for (const href of hrefs) {
          const url = new URL(href)
          if (url.origin !== new URL(base).origin) continue
          const response = await fetch(url.href)
          assert.equal(response.ok, true, `${route} broken internal link ${url.pathname}`)
        }
      }

    }

    for (let index = 0; index < pages.length; index += 1) {
      assert.deepEqual(localeSnapshots.en[index].sectionIds, localeSnapshots.tr[index].sectionIds,
        `${pages[index]} heading/anchor parity`)
    }

    await page.goto(base, { waitUntil: 'networkidle' })
    await page.keyboard.press('Tab')
    assert.equal(await page.evaluate(() => document.activeElement.classList.contains('skip-link')), true, 'first keyboard stop is Skip to content')
    await page.getByRole('link', { name: 'Skip to content' }).click()
    assert.equal(new URL(page.url()).hash, '#content')
    assert.deepEqual(externalRequests, [], 'page load must not make external requests')
    console.log(`Docs browser smoke passed: ${pages.length * 2} pages, reciprocal locale links, section parity, internal links, 390px layout, and keyboard skip link.`)
  } finally {
    if (browser) await browser.close()
    server.kill('SIGTERM')
  }
}

main().catch(error => {
  console.error(error)
  process.exitCode = 1
})
