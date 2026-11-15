import test from 'node:test'
import assert from 'node:assert/strict'
import { examPayloadFromForm, examResultsForSubject, examScoringProfileKey, examSectionTotals, examSubjectOptions, filterExamsByScoringProfile } from './examSections.js'

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

test('profile versions remain isolated in history aggregates', () => {
  const records = [
    { id: 'old', scoring_profile: { profile_id: 'profile-a', version: 1 }, net: 11 },
    { id: 'new', scoring_profile: { profile_id: 'profile-a', version: 2 }, net: 12 },
    { id: 'legacy', net: 10 },
  ]
  assert.equal(examScoringProfileKey(records[2]), 'legacy-yks@1')
  assert.deepEqual(filterExamsByScoringProfile(records, 'profile-a@1').map((exam) => exam.id), ['old'])
  assert.deepEqual(filterExamsByScoringProfile(records, 'profile-a@2').map((exam) => exam.id), ['new'])
})

test('section previews apply the exam snapshot rule and keep exact fractional arithmetic', () => {
  const sectioned = {
    ...mock,
    scoring_profile: { scoring_rule: { correct_points: '1/3', wrong_penalty: '1/6', blank_points: '1/12' } },
    sections: [
      { subject: 'A', correct: 2, incorrect: 1, blank: 1 },
      { subject: 'B', correct: 3, incorrect: 2, blank: 1 },
    ],
  }
  const [result] = examResultsForSubject([sectioned], 'A')
  assert.equal(result.net, 0.5833333333333334)
  assert.equal(sectioned.net, 40)
})
