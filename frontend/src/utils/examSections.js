import { fmtDate, fmtNet, netScoreWithRule } from './formatters.js'

export function examSubjectOptions(exams) {
  return Array.from(new Set(exams.flatMap((exam) => (
    exam.sections?.length ? exam.sections.map((section) => section.subject) : [exam.subject]
  )).filter(Boolean))).sort()
}

export function examSectionTotals(sections = []) {
  return sections.reduce((sum, section) => ({
    correct: sum.correct + section.correct,
    incorrect: sum.incorrect + section.incorrect,
    blank: sum.blank + section.blank,
  }), { correct: 0, incorrect: 0, blank: 0 })
}

export function examPayloadFromForm(form) {
  if (!form.sections?.length) return form
  return {
    ...form,
    subject: form.exam_type === 'custom' ? form.format_name.trim() : `${form.exam_type.toUpperCase()} Geneli`,
    ...examSectionTotals(form.sections),
  }
}

export function examTypeDisplay(exam, t) {
  if (exam?.exam_type === 'custom') return `${t('exams.type.custom')}: ${exam.format_name || exam.subject}`
  return t(`exams.type.${exam?.exam_type || 'branch'}`)
}

export function examScoringProfileKey(examOrProfile) {
  const profile = examOrProfile?.scoring_profile || examOrProfile
  return `${profile?.profile_id || 'legacy-yks'}@${profile?.version || 1}`
}

export function filterExamsByScoringProfile(exams, profileKey) {
  return exams.filter((exam) => examScoringProfileKey(exam) === profileKey)
}

export function averageRecordedNet(exams) {
  const recorded = exams.filter((exam) => exam.correct + exam.incorrect + exam.blank > 0)
  return recorded.length ? recorded.reduce((sum, exam) => sum + exam.net, 0) / recorded.length : 0
}

export function examResultsForSubject(exams, subject = 'all') {
  return exams.flatMap((exam) => {
    if (subject === 'all') return [exam]
    const section = exam.sections?.find((item) => item.subject === subject)
    if (section) return [{
      ...exam, ...section,
      net: netScoreWithRule(section.correct, section.incorrect, section.blank, exam.scoring_profile?.scoring_rule),
    }]
    return exam.subject === subject ? [exam] : []
  })
}

export function orderExamTimeline(exams) {
  const ordered = [...exams].sort((a, b) => a.date.localeCompare(b.date)
    || (a.created_at || '').localeCompare(b.created_at || '') || a.id.localeCompare(b.id))
  const totals = new Map()
  for (const exam of ordered) totals.set(exam.date, (totals.get(exam.date) || 0) + 1)
  const positions = new Map()
  return ordered.map((exam) => {
    const same_day_index = (positions.get(exam.date) || 0) + 1
    positions.set(exam.date, same_day_index)
    return { ...exam, same_day_index, same_day_total: totals.get(exam.date) }
  })
}

export function examChartLabel(exam, dateLabel, t) {
  return exam.same_day_total > 1
    ? `${dateLabel} · ${t('dashboard.examSequence', { number: exam.same_day_index })}`
    : dateLabel
}

export function examChartSummaryRows(exams, locale, t) {
  return exams.map((exam) => ({
    id: exam.id,
    date: examChartLabel(exam, fmtDate(exam.date, locale), t),
    subject: exam.subject,
    net: fmtNet(exam.net, locale),
    change: exam.change == null
      ? t('dashboard.noPreviousExam')
      : `${exam.change > 0 ? '+' : ''}${fmtNet(exam.change, locale)}`,
  }))
}

export function examNetChanges(exams) {
  const ordered = orderExamTimeline(exams)
  return ordered.map((exam, index) => ({
    ...exam,
    change: index ? exam.net - ordered[index - 1].net : null,
  }))
}
