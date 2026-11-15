import { useCallback, useEffect, useState } from 'react'
import { BookOpenCheck, CheckCircle2, Clock3, FileText, Tags, ThumbsDown, ThumbsUp } from 'lucide-react'
import api, { API_BASE, handleApiError } from '../services/api'
import PracticeSessions from './PracticeSessions.jsx'
import LearningEvidence from './LearningEvidence.jsx'
import { useI18n } from '../i18n.jsx'
import { fmtDate, labelOr, localDateToday } from '../utils/formatters.js'

const newFocusTopic = (topic) => ({ subject: topic.subject, topic: topic.topic, requestedAt: Date.now() })

export default function StudyPlanTab() {
  const { t, locale } = useI18n()
  const [plan, setPlan] = useState(null)
  const [error, setError] = useState('')
  const [feedback, setFeedback] = useState('')
  const [busyId, setBusyId] = useState('')
  const [focusTopic, setFocusTopic] = useState(null)

  const load = useCallback(() => api.questions.insights(localDateToday()).then(setPlan).catch((e) => setError(handleApiError(e, t).detail)), [t])

  useEffect(() => { load() }, [load])

  const recordAttempt = async (question, correct) => {
    setBusyId(question.id)
    setError('')
    setFeedback('')
    try {
      await api.questions.attempt(question.id, correct, localDateToday())
      setFeedback(t(correct ? 'study.selfCheckSavedCorrect' : 'study.selfCheckSavedIncorrect'))
      await load()
    } catch (e) {
      setError(handleApiError(e, t).detail)
    } finally {
      setBusyId('')
    }
  }

  if (error) return <p role="alert" className="rounded-lg border border-canvas-line/50 bg-canvas-panel p-3 text-sm text-canvas-text">{error}</p>
  if (!plan) return <p className="py-20 text-center text-sm text-canvas-muted">{t('study.loading')}</p>

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-canvas-text">{t('study.title')}</h1>
        <p className="mt-1 text-sm text-canvas-muted">{t('study.intro')}</p>
      </header>

      {feedback && <p role="status" aria-live="polite" className="rounded-lg border border-canvas-line bg-canvas-panel px-3 py-2 text-sm text-canvas-text">{feedback}</p>}

      <div className="grid gap-3 sm:grid-cols-4">
        <Stat label={t('study.stat.saved')} value={formatInt(plan.total_questions, locale)} icon={<BookOpenCheck size={18} />} />
        <Stat label={t('study.stat.pending')} value={formatInt(plan.pending_questions, locale)} icon={<CheckCircle2 size={18} />} />
        <Stat label={t('study.stat.scheduled')} value={formatInt(plan.scheduled_questions, locale)} icon={<Clock3 size={18} />} />
        <Stat label={t('study.stat.unclassified')} value={formatInt(plan.unclassified_questions, locale)} icon={<Tags size={18} />} />
      </div>

      <PracticeSessions startTopic={focusTopic} onStartTopicConsumed={() => setFocusTopic(null)} />

      <section aria-label={t('study.today')} className="rounded-xl border border-canvas-line bg-canvas-panel p-4">
        <h2 className="font-semibold text-canvas-text">{t('study.today')}</h2>
        <p className="mt-1 text-sm text-canvas-muted">{t('study.todaySummary', { questions: formatInt(plan.today_questions, locale), correct: formatInt(plan.today_correct, locale), incorrect: formatInt(plan.today_incorrect, locale) })}</p>
      </section>

      <section aria-label={t('study.questionOrder')} className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-canvas-text">{t('study.orderTitle')}</h2>
          <p className="text-sm text-canvas-muted">{t('study.orderIntro')}</p>
        </div>
        {plan.question_order?.length ? plan.question_order.map((group) => (
          <article key={`${group.exam_type}-${group.subject}`} className="rounded-xl border border-canvas-line bg-canvas-panel p-4">
            <h3 className="font-semibold text-canvas-text">{examTypeLabel(group.exam_type, t)} · {group.subject}</h3>
            <p className="text-xs text-canvas-muted">{t('study.errorsFromExams', { count: formatInt(group.exam_count, locale) })}</p>
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              {[["early", t('study.early')], ["middle", t('study.middle')], ["late", t('study.late')]].map(([key, label]) => {
                const stage = group[key]
                const median = stage.median_seconds
                return <div key={key} className="rounded-lg bg-canvas-base p-3 text-sm">
                  <p className="text-canvas-muted">{label}</p>
                  <p className="mt-1 font-semibold text-canvas-text">{t('study.wrongCount', { count: formatInt(stage.wrong_count, locale) })}</p>
                  <p className="text-xs text-canvas-muted">{median == null ? t('study.noTime') : t('study.medianTime', { seconds: formatNumber(median, locale) })}</p>
                </div>
              })}
            </div>
          </article>
        )) : (
          <div className="rounded-xl border border-dashed border-canvas-line p-4 text-sm text-canvas-muted">{t('study.orderEmpty')}</div>
        )}
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-canvas-text">{t('study.solveNow')}</h2>
          <p className="text-sm text-canvas-muted">{t('study.solveIntro')}</p>
        </div>
        {plan.reviews.length === 0 ? (
          <div className="rounded-xl border border-dashed border-canvas-line p-6 text-center text-sm text-canvas-muted">{plan.scheduled_questions ? t('study.scheduledSummary', { count: formatInt(plan.scheduled_questions, locale) }) : t('study.noQuestionsToSolve')}</div>
        ) : plan.reviews.slice(0, 6).map((question) => (
          <article key={question.id} className="grid gap-4 rounded-xl border border-canvas-line bg-canvas-panel p-4 sm:grid-cols-[200px_1fr]">
            {question.has_image ? (
                <img src={`${API_BASE}/questions/${question.id}/image`} alt={t('study.questionImageAlt', { subject: labelOr(question.subject, t('common.subjectNotSpecified')), topic: labelOr(question.topic, t('common.topicNotSpecified')) })} className="max-h-56 w-full rounded-lg bg-canvas-base object-contain" />
            ) : (
              <div role="img" aria-label={t('questions.textQuestionWithoutImage')} className="flex min-h-32 flex-col items-center justify-center gap-2 rounded-lg bg-canvas-base text-sm text-canvas-muted"><FileText size={22} />{t('questions.textQuestion')}</div>
            )}
            <div className="space-y-3">
              <div>
                <p className="text-xs text-canvas-muted">{labelOr(question.subject, t('common.subjectNotSpecified'))} · {labelOr(question.topic, t('common.topicNotSpecified'))}</p>
                <h3 className="font-semibold text-canvas-text">{tagLabel(question.hamartia_tag, t)}</h3>
              </div>
              {question.ocr_text && <p className="whitespace-pre-wrap text-sm text-canvas-muted">{question.ocr_text}</p>}
              <p className="text-xs text-canvas-muted">{question.last_correct === false ? t('study.lastAttemptWrong') : question.streak ? t('study.correctStreak', { count: formatInt(question.streak, locale) }) : t('study.firstReview')}</p>
              <div className="flex flex-wrap gap-2">
                <button type="button" disabled={busyId === question.id} onClick={() => recordAttempt(question, true)} className="inline-flex items-center gap-2 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text hover:bg-canvas-raise disabled:opacity-50"><ThumbsUp size={15} /> {t('study.markCorrect')}</button>
                <button type="button" disabled={busyId === question.id} onClick={() => recordAttempt(question, false)} className="inline-flex items-center gap-2 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text hover:bg-canvas-raise disabled:opacity-50"><ThumbsDown size={15} /> {t('study.markIncorrect')}</button>
              </div>
            </div>
          </article>
        ))}
      </section>

      {plan.scheduled_questions > 0 && <section className="rounded-xl border border-canvas-line bg-canvas-panel p-4 text-sm text-canvas-muted">{t('study.spacedReviewInfo', { count: formatInt(plan.scheduled_questions, locale) })}</section>}

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-canvas-text">{t('study.topicsToReview')}</h2>
          <p className="text-sm text-canvas-muted">{t('study.topicsIntro')}</p>
        </div>
        {plan.topics.length === 0 ? (
          <div className="rounded-xl border border-dashed border-canvas-line p-8 text-center text-sm text-canvas-muted">{plan.total_questions ? t('study.noPendingQuestions') : t('study.addQuestionToStart')}</div>
        ) : plan.topics.slice(0, 8).map((topic, index) => (
          <article key={`${topic.subject}-${topic.topic}`} className="rounded-xl border border-canvas-line bg-canvas-panel p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-canvas-raise text-sm font-semibold text-canvas-text">{index + 1}</span>
                <div>
                  <h3 className="font-semibold text-canvas-text">{labelOr(topic.topic, t('common.topicNotSpecified'))}</h3>
                  <p className="text-sm text-canvas-muted">{labelOr(topic.subject, t('common.subjectNotSpecified'))}</p>
                </div>
              </div>
              <span className="rounded-full border border-canvas-line px-3 py-1 text-xs text-canvas-muted">{t('study.pendingWrongCount', { count: formatInt(topic.pending_count, locale) })}</span>
            </div>
            {topic.subject.trim() && topic.topic.trim() ? (
              <button type="button" onClick={() => setFocusTopic(newFocusTopic(topic))} className="mt-3 rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text hover:bg-canvas-raise">{t('study.focusOnTopic', { subject: topic.subject, topic: topic.topic })}</button>
            ) : (
              <p className="mt-3 text-sm text-canvas-muted">{t('study.focusNeedsLabels')}</p>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(topic.tags).map(([tag, count]) => (
                <span key={tag} className="rounded-md bg-canvas-base px-2 py-1 text-xs text-canvas-muted">{tagLabel(tag, t)}: {formatInt(count, locale)}</span>
              ))}
              {topic.last_seen && <span className="px-2 py-1 text-xs text-canvas-muted">{t('study.lastSeen', { date: fmtDate(topic.last_seen, locale) })}</span>}
            </div>
          </article>
        ))}
      </section>

      <LearningEvidence topics={plan.topics} />
    </div>
  )
}

function Stat({ label, value, icon }) {
  return (
    <article className="flex items-center gap-3 rounded-xl border border-canvas-line bg-canvas-panel p-4">
      <div className="rounded-lg bg-canvas-raise p-2 text-canvas-text">{icon}</div>
      <div><p className="text-xs text-canvas-muted">{label}</p><p className="text-xl font-bold text-canvas-text">{value}</p></div>
    </article>
  )
}

function tagLabel(tag, t) {
  return ({
    '[Knowledge Gap]': t('questions.tag.knowledgeGap'),
    '[Distractor Trap]': t('questions.tag.distractorTrap'),
    '[Reading Slip]': t('questions.tag.readingSlip'),
    '[Time Panic]': t('questions.tag.timePanic'),
  })[tag] || tag
}

function examTypeLabel(type, t) {
  return ({ tyt: 'TYT', ayt: 'AYT', branch: t('common.branchExam') })[type] || type
}

function formatInt(value, locale) {
  return new Intl.NumberFormat(locale).format(value ?? 0)
}

function formatNumber(value, locale) {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(value)
}
