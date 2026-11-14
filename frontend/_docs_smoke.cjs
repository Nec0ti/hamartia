const assert = require('node:assert/strict')
const { spawn } = require('node:child_process')
const { createServer } = require('node:net')
const path = require('node:path')
const { chromium } = require('playwright')

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
    browser = await chromium.launch({ headless: true })
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } })
    const externalRequests = []
    page.on('request', request => {
      if (!request.url().startsWith(base)) externalRequests.push(request.url())
    })
    await page.goto(base, { waitUntil: 'networkidle' })
    assert.equal(await page.locator('html').getAttribute('lang'), 'en')
    await page.getByRole('heading', { name: 'Study with a clearer picture.' }).waitFor()
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    await page.getByRole('link', { name: /Türkçe/ }).click()
    assert.equal(await page.locator('html').getAttribute('lang'), 'tr')
    await page.getByRole('heading', { name: 'Daha net bir tabloyla çalış.' }).waitFor()
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    await page.getByRole('link', { name: /English/ }).click()
    assert.equal(new URL(page.url()).pathname, '/')
    assert.deepEqual(externalRequests, [])
    console.log('Docs smoke passed: English default, Turkish navigation, language tags, mobile layout, and no external requests.')
  } finally {
    if (browser) await browser.close()
    server.kill('SIGTERM')
  }
}

main().catch(error => {
  console.error(error)
  process.exitCode = 1
})
