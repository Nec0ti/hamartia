const MAX_CONTEXT_LENGTH = 6000
const REFERENCE_FIELDS = [
  'framework', 'source', 'version', 'grade_year', 'unit_theme',
  'learning_outcome', 'process_component', 'source_url',
]

const text = (value, maxLength = 120) => String(value || '').slice(0, maxLength)

function referenceSummary(reference) {
  const result = { subject: text(reference.subject) }
  for (const field of REFERENCE_FIELDS) {
    result[field] = text(reference[field], field === 'learning_outcome' ? 500 : field === 'source_url' ? 2048 : 200)
  }
  return result
}

export function summarizeStudyAgentContext(insights, sessions) {
  const summary = {
    pending_questions: insights?.pending_questions ?? 0,
    scheduled_questions: insights?.scheduled_questions ?? 0,
    topics: (Array.isArray(insights?.topics) ? insights.topics : []).slice(0, 8).map(({ subject, topic, pending_count, tags }) => ({
      subject: text(subject), topic: text(topic), pending_count: Number(pending_count) || 0,
      tags: Object.fromEntries(Object.entries(tags || {}).slice(0, 8).map(([tag, count]) => [text(tag, 80), Number(count) || 0])),
    })),
    topic_practice: (Array.isArray(sessions) ? sessions : []).slice(0, 8).map(({ subject, topic, session_count, net, accuracy }) => ({
      subject: text(subject), topic: text(topic), session_count: Number(session_count) || 0, net, accuracy,
    })),
    curriculum_references: [],
  }

  while (JSON.stringify(summary).length > MAX_CONTEXT_LENGTH && summary.topic_practice.length) summary.topic_practice.pop()
  while (JSON.stringify(summary).length > MAX_CONTEXT_LENGTH && summary.topics.length) summary.topics.pop()
  for (const reference of (Array.isArray(insights?.curriculum_references) ? insights.curriculum_references : []).slice(0, 8)) {
    const candidate = [...summary.curriculum_references, referenceSummary(reference)]
    if (JSON.stringify({ ...summary, curriculum_references: candidate }).length > MAX_CONTEXT_LENGTH) break
    summary.curriculum_references = candidate
  }
  return JSON.stringify(summary)
}
