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

export function examResultsForSubject(exams, subject = 'all') {
  return exams.flatMap((exam) => {
    if (subject === 'all') return [exam]
    const section = exam.sections?.find((item) => item.subject === subject)
    if (section) return [{ ...exam, ...section, net: section.correct - section.incorrect / 4 }]
    return exam.subject === subject ? [exam] : []
  })
}
