import test from 'node:test'
import assert from 'node:assert/strict'
import { examPayloadFromForm, examResultsForSubject, examSectionTotals, examSubjectOptions } from './examSections.js'

const mock = {
  id: 'mock-1', subject: 'TYT Geneli', net: 40, correct: 45, incorrect: 20, blank: 15,
  sections: [
    { subject: 'Türkçe', correct: 30, incorrect: 5, blank: 5 },
    { subject: 'Matematik', correct: 15, incorrect: 15, blank: 10 },
  ],
}

test('subject options use mock sections and legacy exam subjects', () => {
  assert.deepEqual(examSubjectOptions([mock, { subject: 'Fizik' }]), ['Fizik', 'Matematik', 'Türkçe'])
})

test('subject result projects a section without changing the saved session aggregate', () => {
  const [result] = examResultsForSubject([mock], 'Matematik')
  assert.deepEqual([result.correct, result.incorrect, result.blank, result.net], [15, 15, 10, 11.25])
  assert.equal(result.id, 'mock-1')
  assert.equal(mock.net, 40)
  assert.equal(examResultsForSubject([mock], 'TYT Geneli')[0].net, 40)
})

test('full mock payload totals sections once while branch input stays unchanged', () => {
  const form = { exam_type: 'ayt', subject: '', correct: 0, incorrect: 0, blank: 0, sections: mock.sections }
  assert.deepEqual(examSectionTotals(form.sections), { correct: 45, incorrect: 20, blank: 15 })
  assert.deepEqual(examPayloadFromForm(form), { ...form, subject: 'AYT Geneli', correct: 45, incorrect: 20, blank: 15 })
  const branch = { exam_type: 'branch', subject: 'Fizik', correct: 7, incorrect: 2, blank: 1 }
  assert.equal(examPayloadFromForm(branch), branch)
})
