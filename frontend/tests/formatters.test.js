import assert from 'node:assert/strict'
import test from 'node:test'
import { netScore, previewXp, levelForXp, xpProgress, xpToNextLevel } from '../src/utils/formatters.js'

test('net score applies the YKS quarter penalty', () => {
  assert.equal(netScore(3, 2), 2.5)
  assert.equal(netScore(0, 0), 0)
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
  assert.equal(xpProgress(499, 1), 0)
  assert.equal(xpProgress(750, 2), 0.5)
  assert.equal(xpProgress(1000, 3), 0)
  assert.equal(xpProgress(1500, 3), 1)
  assert.equal(xpToNextLevel(2), 1500)
})
