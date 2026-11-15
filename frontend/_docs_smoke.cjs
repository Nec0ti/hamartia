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
    browser = await chromium.launch({
      headless: true,
      ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {}),
    })
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } })
    const externalRequests = []
    page.on('request', request => {
      if (!request.url().startsWith(base)) externalRequests.push(request.url())
    })
    await page.goto(base, { waitUntil: 'networkidle' })
    assert.equal(await page.locator('html').getAttribute('lang'), 'en')
    assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'), 'https://nec0ti.github.io/hamartia/')
    await page.getByRole('heading', { name: 'Study with a clearer picture.' }).waitFor()
    assert.equal(await page.getByRole('link', { name: 'Download Hamartia' }).getAttribute('href'), 'https://github.com/Nec0ti/hamartia/releases/latest')
    await page.getByText(/Windows 10\/11 or Linux x64/).waitFor()
    await page.getByText(/ChatGPT sign-in is available in the packaged desktop app/).waitFor()
    await page.getByRole('heading', { name: 'Check your OpenAI-compatible service.' }).waitFor()
    await page.getByRole('heading', { name: 'Check ChatGPT sign-in and sign-out.' }).waitFor()
    await page.getByRole('heading', { name: 'Learning patterns, with room for the learning process.' }).waitFor()
    await page.getByText(/not an official or verified Maarif alignment system/).waitFor()
    await page.getByText(/The endpoint operator may have its own retention rules/).waitFor()
    await page.getByText(/built-in net calculation uses the YKS wrong-answer penalty/).waitFor()
    await page.getByRole('link', { name: 'MIT license ↗' }).waitFor()
    await page.getByText('Restore backup', { exact: true }).waitFor()
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, await page.evaluate(() => [...document.querySelectorAll('*')].filter(node => node.getBoundingClientRect().right > innerWidth).map(node => `${node.tagName}.${node.className}=${Math.round(node.getBoundingClientRect().right)}`).slice(0, 5).join(', ')))
    await page.getByRole('link', { name: /Türkçe/ }).click()
    assert.equal(await page.locator('html').getAttribute('lang'), 'tr')
    assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'), 'https://nec0ti.github.io/hamartia/tr/')
    await page.getByRole('heading', { name: 'Daha net bir tabloyla çalış.' }).waitFor()
    await page.getByText(/Yanlış sorularını kaydet, hatalarındaki örüntüleri gör/).waitFor()
    assert.equal(await page.getByRole('link', { name: "Hamartia'yı indir" }).getAttribute('href'), 'https://github.com/Nec0ti/hamartia/releases/latest')
    await page.getByText(/Windows 10\/11 veya Linux x64/).waitFor()
    await page.getByText(/ChatGPT ile giriş, masaüstü uygulamasında kullanılabilir/).waitFor()
    await page.getByRole('heading', { name: 'OpenAI uyumlu hizmetini kontrol et.' }).waitFor()
    await page.getByRole('heading', { name: 'ChatGPT giriş ve çıkışını kontrol et.' }).waitFor()
    await page.getByRole('heading', { name: 'Öğrenme örüntüleri ve öğrenme süreci.' }).waitFor()
    await page.getByText(/resmî veya doğrulanmış Maarif eşleştirmesi yapmaz/).waitFor()
    assert.equal(await page.getByText(/Kaynak adresini otomatik olarak alıp doğrulamaz; istersen bağlantıyı kendin açabilirsin/).count() > 0, true)
    await page.getByText(/Yerleşik net hesabı YKS yanlış-ceza kuralını kullanır/).waitFor()
    await page.getByRole('link', { name: 'MIT lisansı ↗' }).waitFor()
    await page.getByText('Yedeği geri yükle', { exact: true }).waitFor()
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, await page.evaluate(() => [...document.querySelectorAll('*')].filter(node => node.getBoundingClientRect().right > innerWidth).map(node => `${node.tagName}.${node.className}=${Math.round(node.getBoundingClientRect().right)}`).slice(0, 5).join(', ')))
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
