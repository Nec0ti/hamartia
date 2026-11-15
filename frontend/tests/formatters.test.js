import assert from 'node:assert/strict'
import test from 'node:test'
import { netScore, netScoreWithRule, previewXp, levelForXp, xpProgress, xpToNextLevel, fmtDate, fmtInt, fmtNet, fmtPercent, labelOr, localDateToday, subjectLabel } from '../src/utils/formatters.js'

test('net score applies the YKS quarter penalty', () => {
  assert.equal(netScore(3, 2), 2.5)
  assert.equal(netScore(0, 0), 0)
})

test('rational scoring previews match independent three-rule goldens', () => {
  const counts = [12, 4, 4]
  assert.equal(netScoreWithRule(...counts, { correct_points: '1/1', wrong_penalty: '1/4', blank_points: '0/1' }), 11)
  assert.equal(netScoreWithRule(...counts, { correct_points: '1/1', wrong_penalty: '0/1', blank_points: '0/1' }), 12)
  assert.equal(netScoreWithRule(...counts, { correct_points: '1/1', wrong_penalty: '1/2', blank_points: '0/1' }), 10)
})

test('XP preview truncates the same way as the backend', () => {
  assert.equal(previewXp(3, 2, 1), 10)
  assert.equal(previewXp(0, 0, 0), 0)
})

test('level threshold matches the backend ladder', () => {
  assert.equal(levelForXp(499), 1)
  assert.equal(levelForXp(500), 2)
})

test('level progress resets at thresholds and stays within the bar', () => {
  assert.equal(xpProgress(0, 1), 0)
  assert.equal(xpProgress(499, 1), 0.998)
  assert.equal(xpProgress(500, 2), 0)
  assert.equal(xpProgress(750, 2), 0.5)
  assert.equal(xpProgress(1000, 3), 0)
  assert.equal(xpProgress(1499, 3), 0.998)
  assert.equal(xpProgress(1500, 4), 0)
  assert.equal(xpToNextLevel(1), 500)
  assert.equal(xpToNextLevel(2), 1000)
})

test('display formatters follow the selected locale without changing values', () => {
  assert.equal(fmtInt(1234, 'en-US'), '1,234')
  assert.equal(fmtInt(1234, 'tr-TR'), '1.234')
  assert.equal(fmtNet(1.25, 'en-US'), '1.25')
  assert.equal(fmtNet(1.25, 'tr-TR'), '1,25')
  assert.equal(fmtNet(0, 'tr-TR'), '0,0')
  assert.equal(fmtPercent(80, 'en-US'), '80.0')
  assert.equal(fmtPercent(81.818, 'tr-TR'), '81,8')
})

test('subject display fallback can follow the selected language', () => {
  assert.equal(subjectLabel('', 'Unlabelled'), 'Unlabelled')
  assert.equal(subjectLabel('', 'Etiketsiz'), 'Etiketsiz')
  assert.equal(subjectLabel('Matematik', 'Unlabelled'), 'Matematik')
})

test('date display follows the selected locale and stays on the calendar date', () => {
  assert.equal(fmtDate('2026-11-14', 'en-US'), 'Nov 14, 2026')
  assert.equal(fmtDate('2026-11-14', 'tr-TR'), '14 Kas 2026')
  assert.equal(fmtDate('2026-11-14', 'tr-TR', { month: 'numeric', day: 'numeric' }), '14/11')
  assert.equal(fmtDate('invalid', 'en-US'), 'invalid')
})

test('local calendar day follows UTC offsets and midnight without UTC conversion', () => {
  const originalTz = process.env.TZ
  try {
    process.env.TZ = 'Asia/Kathmandu'
    assert.equal(localDateToday(new Date('2026-11-14T18:30:00Z')), '2026-11-15')
    assert.equal(localDateToday(new Date('2026-11-14T22:30:00Z')), '2026-11-15')
    process.env.TZ = 'Etc/GMT+12'
    assert.equal(localDateToday(new Date('2026-11-14T22:30:00Z')), '2026-11-14')
  } finally {
    if (originalTz === undefined) delete process.env.TZ
    else process.env.TZ = originalTz
  }
})

test('missing saved labels use caller-provided English or Turkish fallback', () => {
  assert.equal(labelOr('', 'Subject not specified'), 'Subject not specified')
  assert.equal(labelOr('   ', 'Konu belirtilmedi'), 'Konu belirtilmedi')
  assert.equal(labelOr('Matematik', 'Ders belirtilmedi'), 'Matematik')
})
