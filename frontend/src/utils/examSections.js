import { netScoreWithRule } from './formatters.js'

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
    subject: `${form.exam_type.toUpperCase()} Geneli`,
    ...examSectionTotals(form.sections),
  }
}

export function examScoringProfileKey(examOrProfile) {
  const profile = examOrProfile?.scoring_profile || examOrProfile
  return `${profile?.profile_id || 'legacy-yks'}@${profile?.version || 1}`
}

export function filterExamsByScoringProfile(exams, profileKey) {
  return exams.filter((exam) => examScoringProfileKey(exam) === profileKey)
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
