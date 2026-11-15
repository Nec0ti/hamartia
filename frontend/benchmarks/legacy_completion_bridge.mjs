import { readFileSync } from 'node:fs'
import { findLegacyFocusedCompletion } from '../src/clock/completePractice.js'

const input = JSON.parse(readFileSync(0, 'utf8'))
const result = findLegacyFocusedCompletion(input.timer, input.sessions)
process.stdout.write(JSON.stringify({ kind: result.kind, row: result.row ?? null }))
