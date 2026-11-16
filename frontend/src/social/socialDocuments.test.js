import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.resolve(HERE, '../../..')
const DOCS = path.join(REPO, 'docs')
const EN_AGREEMENT = 'user-agreement-v0.1-draft.html'
const TR_AGREEMENT = path.join('tr', EN_AGREEMENT)

function read(relativePath) {
  return readFileSync(path.join(REPO, relativePath), 'utf8')
}

function resolveLocal(fromFile, href) {
  const current = path.relative(DOCS, fromFile).split(path.sep).join('/')
  const parsed = new URL(href, `https://docs.example.test/hamartia/${current}`)
  if (parsed.origin !== 'https://docs.example.test') return null
  if (!parsed.pathname.startsWith('/hamartia/')) return null
  let target = path.resolve(DOCS, decodeURIComponent(parsed.pathname.slice('/hamartia/'.length)))
  if (parsed.pathname.endsWith('/')) target = path.join(target, 'index.html')
  return target
}

test('the versioned User Agreement and Privacy guide URLs resolve in English and Turkish', () => {
  const agreementPages = [
    ['docs/user-agreement-v0.1-draft.html', 'en', 'https://nec0ti.github.io/hamartia/user-agreement-v0.1-draft.html'],
    ['docs/tr/user-agreement-v0.1-draft.html', 'tr', 'https://nec0ti.github.io/hamartia/tr/user-agreement-v0.1-draft.html'],
  ]
  for (const [relativePath, locale, canonical] of agreementPages) {
    const html = read(relativePath)
    assert.match(html, new RegExp(`<html lang="${locale}">`))
    assert.ok(html.includes(`rel="canonical" href="${canonical}"`))
    assert.match(html, /DRAFT — NOT APPROVED|TASLAK — ONAYLANMADI/)
  }
  for (const relativePath of ['docs/privacy-and-consent/index.html', 'docs/tr/privacy-and-consent/index.html']) {
    assert.ok(read(relativePath).includes('user-agreement-v0.1-draft.html'))
  }
  const modal = read('frontend/src/components/SocialProfileModal.jsx')
  for (const url of [
    'https://nec0ti.github.io/hamartia/user-agreement-v0.1-draft.html',
    'https://nec0ti.github.io/hamartia/tr/user-agreement-v0.1-draft.html',
    'https://nec0ti.github.io/hamartia/privacy-and-consent/',
    'https://nec0ti.github.io/hamartia/tr/privacy-and-consent/',
  ]) assert.ok(modal.includes(url), `UI link missing ${url}`)
})

test('each agreement page language switch, privacy guide, stylesheet, and icons resolve locally', () => {
  const pages = [
    ['docs/user-agreement-v0.1-draft.html', 'tr/user-agreement-v0.1-draft.html'],
    ['docs/tr/user-agreement-v0.1-draft.html', '../user-agreement-v0.1-draft.html'],
  ]
  for (const [relativePath, languageSwitch] of pages) {
    const absolutePath = path.join(REPO, relativePath)
    const html = read(relativePath)
    assert.ok(html.includes(`href="${languageSwitch}"`))
    for (const href of [...html.matchAll(/(?:href|src)="([^"]+)"/g)].map((match) => match[1])) {
      if (/^(?:https?:|#)/.test(href)) continue
      const target = resolveLocal(absolutePath, href)
      assert.ok(target && existsSync(target), `${relativePath}: broken local link ${href}`)
      assert.ok(target.startsWith(DOCS + path.sep), `${relativePath}: link escapes docs root ${href}`)
    }
  }
  assert.equal(path.basename(path.join(DOCS, EN_AGREEMENT)), EN_AGREEMENT)
  assert.equal(path.join('tr', EN_AGREEMENT), TR_AGREEMENT)
})
