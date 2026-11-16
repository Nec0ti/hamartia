import { readFileSync } from 'node:fs'
import { practiceDurationFromElapsedMilliseconds } from '../src/clock/practiceDuration.js'

const elapsedMilliseconds = JSON.parse(readFileSync(0, 'utf8'))
if (!Array.isArray(elapsedMilliseconds) || elapsedMilliseconds.some((value) => !Number.isSafeInteger(value) || value < 0)) {
  throw new TypeError('Expected a JSON array of nonnegative safe-integer millisecond values.')
}
process.stdout.write(JSON.stringify(elapsedMilliseconds.map(practiceDurationFromElapsedMilliseconds)))
