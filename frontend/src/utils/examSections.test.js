import test from 'node:test'
import assert from 'node:assert/strict'
import { averageRecordedNet, examChartLabel, examChartSummaryRows, examNetChanges, examPayloadFromForm, examResultsForSubject, examScoringProfileKey, examSectionTotals, examSubjectOptions, examTypeDisplay, filterExamsByScoringProfile, orderExamTimeline } from './examSections.js'

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

test('custom mock payload uses the user format name and displays it without an official claim', () => {
  const form = { exam_type: 'custom', format_name: 'Personal assessment', subject: '', correct: 0, incorrect: 0, blank: 0,
    sections: [{ subject: 'Reading', correct: 4, incorrect: 1, blank: 2 }] }
  assert.deepEqual(examPayloadFromForm(form), { ...form, subject: 'Personal assessment', correct: 4, incorrect: 1, blank: 2 })
  assert.equal(examTypeDisplay({ exam_type: 'custom', format_name: 'Personal assessment' }, (key) => key === 'exams.type.custom' ? 'Custom mock' : key), 'Custom mock: Personal assessment')
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

test('every all-blank recorded exam contributes to its profile average, including zero score', () => {
  const exams = [
    { id: 'answered', correct: 12, incorrect: 4, blank: 4, net: 10 },
    { id: 'blank-credit', correct: 0, incorrect: 0, blank: 4, net: 4 },
    { id: 'blank-zero-credit', correct: 0, incorrect: 0, blank: 4, net: 0 },
    { id: 'empty', correct: 0, incorrect: 0, blank: 0, net: 0 },
  ]
  assert.equal(averageRecordedNet(exams), 14 / 3)
  assert.equal(averageRecordedNet([{ correct: 0, incorrect: 0, blank: 0, net: 0 }]), 0)
})

test('net change is chronological, profile-ready, and never invents a single-record improvement', () => {
  const changes = examNetChanges([
    { id: 'later', date: '2026-03-02', created_at: '2026-03-02T10:00:00Z', net: 0 },
    { id: 'same-day-later', date: '2026-03-01', created_at: '2026-03-01T11:00:00Z', net: 12 },
    { id: 'first', date: '2026-03-01', created_at: '2026-03-01T10:00:00Z', net: 10 },
  ])
  assert.deepEqual(changes.map(({ id, change }) => [id, change]), [
    ['first', null], ['same-day-later', 2], ['later', -12],
  ])
  assert.deepEqual(examNetChanges([{ id: 'only', date: '2026-03-01', net: 4 }]).map((item) => item.change), [null])
  assert.deepEqual(examNetChanges([]), [])
})

test('zero and negative exam results remain in net-change history partitioned by scoring version', () => {
  const records = [
    { id: 'one', date: '2026-03-01', net: 2, scoring_profile: { profile_id: 'custom', version: 1 } },
    { id: 'two', date: '2026-03-02', net: 0, scoring_profile: { profile_id: 'custom', version: 1 } },
    { id: 'three', date: '2026-03-03', net: -1, scoring_profile: { profile_id: 'custom', version: 1 } },
    { id: 'other-version', date: '2026-03-04', net: 20, scoring_profile: { profile_id: 'custom', version: 2 } },
  ]
  assert.deepEqual(examNetChanges(filterExamsByScoringProfile(records, 'custom@1')).map(({ net, change }) => [net, change]), [
    [2, null], [0, -2], [-1, -1],
  ])
  assert.deepEqual(examNetChanges(filterExamsByScoringProfile(records, 'custom@2')).map(({ net, change }) => [net, change]), [[20, null]])
})

test('same-day exam labels distinguish each result and localize its sequence', () => {
  const timeline = orderExamTimeline([
    { id: 'second', date: '2026-03-01', created_at: '2026-03-01T11:00:00Z', subject: 'Math' },
    { id: 'first', date: '2026-03-01', created_at: '2026-03-01T10:00:00Z', subject: 'Math' },
    { id: 'next-day', date: '2026-03-02', created_at: '2026-03-02T10:00:00Z', subject: 'Math' },
  ])
  assert.deepEqual(timeline.map(({ id, same_day_index, same_day_total }) => [id, same_day_index, same_day_total]), [
    ['first', 1, 2], ['second', 2, 2], ['next-day', 1, 1],
  ])
  const labels = { en: (number) => `Exam ${number}`, tr: (number) => `${number}. deneme` }
  assert.equal(examChartLabel(timeline[0], '3/1', (_key, values) => labels.en(values.number)), '3/1 · Exam 1')
  assert.equal(examChartLabel(timeline[1], '1.03', (_key, values) => labels.tr(values.number)), '1.03 · 2. deneme')
  assert.equal(examChartLabel(timeline[2], '3/2', () => 'unused'), '3/2')
})

test('accessible exam chart rows include date, identity, net, and change in both locales', () => {
  const timeline = examNetChanges([
    { id: 'first', date: '2026-03-01', created_at: '2026-03-01T10:00:00Z', subject: 'Math', net: 10 },
    { id: 'second', date: '2026-03-01', created_at: '2026-03-01T11:00:00Z', subject: 'Math', net: 12 },
  ])
  const translate = (locale) => (key, values) => key === 'dashboard.examSequence'
    ? (locale === 'en' ? `Exam ${values.number}` : `${values.number}. deneme`)
    : 'No previous exam'
  const english = examChartSummaryRows(timeline, 'en-US', translate('en'))
  const turkish = examChartSummaryRows(timeline, 'tr-TR', translate('tr'))
  assert.equal(english[0].date, 'Mar 1, 2026 · Exam 1')
  assert.deepEqual([english[0].subject, english[0].net, english[0].change], ['Math', '10.00', 'No previous exam'])
  assert.equal(english[1].date, 'Mar 1, 2026 · Exam 2')
  assert.deepEqual([english[1].subject, english[1].net, english[1].change], ['Math', '12.00', '+2.00'])
  assert.equal(turkish[0].date, '1 Mar 2026 · 1. deneme')
  assert.deepEqual([turkish[1].subject, turkish[1].net, turkish[1].change], ['Math', '12,00', '+2,00'])
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
