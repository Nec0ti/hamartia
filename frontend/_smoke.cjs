const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push('C:' + m.text()) });
  page.on('pageerror', (e) => errors.push('PAGEERR: ' + e.message));
  try {
    await page.goto('http://127.0.0.1:5173', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);
    const navText = await page.$eval('nav', el => el.textContent.trim().slice(0,120)).catch(() => 'NAV-ERR');
    console.log('NAV TEXT:', navText);
    const gear = await page.$('button[aria-label="Open settings"]');
    console.log('GEAR FOUND:', !!gear);
    if (gear) { await gear.click(); await page.waitForTimeout(600); }
    const modalH2 = await page.$eval('h2:text=Settings', el => el.textContent()).catch(() => 'MODAL-ERR');
    console.log('MODAL H2:', modalH2);
    await page.fill('input[placeholder="http://localhost:4000/v1"]', 'http://localhost:4000/v1');
    await page.fill('input[placeholder="ollama/qwen2.5"]', 'ollama/qwen2.5');
    await page.fill('input[type="password"]', 'sk-local-test-key');
    const saveBtn = await page.$eval('button:has-text("Save")', el => el.textContent.trim()).catch(() => 'SAVE-ERR');
    console.log('SAVE BUTTON:', saveBtn);
    console.log('ERRORS:', errors.length);
    errors.slice(0,10).forEach((e,i) => console.log(i+':', e));
  } catch (e) { console.log('NAV ERROR:', e.message); }
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });
