import assert from 'node:assert/strict'
import test from 'node:test'
import { questionOrderGroupKey } from './questionOrder.js'

test('custom question-order groups with the same subject keep distinct stable identities', () => {
  const first = questionOrderGroupKey({ exam_type: 'custom', format_name: 'Practice A', subject: 'Math' })
  const second = questionOrderGroupKey({ exam_type: 'custom', format_name: 'Practice B', subject: 'Math' })

  assert.notEqual(first, second)
  assert.equal(first, questionOrderGroupKey({ exam_type: 'custom', format_name: 'Practice A', subject: 'Math' }))
})

test('legacy groups without format names still receive a stable identity', () => {
  assert.equal(
    questionOrderGroupKey({ exam_type: 'tyt', subject: 'Math' }),
    questionOrderGroupKey({ exam_type: 'tyt', subject: 'Math' }),
  )
})
