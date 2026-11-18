import { useMemo } from 'react'
import { ArrowDownRight, Clock, Pencil, Trash2 } from 'lucide-react'
import { Panel, Header } from '../components/ui.jsx'
import { fmtDate, fmtInt, fmtNet, fmtDuration, subjectLabel, netScoreWithRule } from '../utils/formatters'
import { useI18n } from '../i18n.jsx'

/**
 * Recent-exams table. Each row shows the derived net and XP. Double-clicking
 * the Incorrect cell (or the row) opens the question-upload modal, matching the
 * "double-click Incorrect to upload" behaviour from the spec.
 */
export default function RecentExams({ exams, onDoubleClickIncorrect, onEdit, onDelete, recentError }) {
  const { t, locale } = useI18n()
  const recent = useMemo(() => exams.slice().sort((a, b) => (b.date < a.date ? 1 : -1)), [exams])

  if (recent.length === 0) {
    return (
      <Panel>
        <Header title={t('exams.history')} />
        <p className="py-10 text-center text-sm text-canvas-muted">
          {t('exams.noExams')}
        </p>
      </Panel>
    )
  }

  return (
    <Panel>
      <Header title={t('exams.history')} />
      <div className="overflow-x-auto">
        <table aria-label={t('exams.history')} className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-canvas-line text-xs uppercase tracking-wider text-canvas-muted">
              <th className="py-3 pr-4">{t('exams.date')}</th>
              <th className="py-3 pr-4">{t('exams.subject')}</th>
              <th className="py-3 pr-4">{t('exams.type')}</th>
              <th className="py-3 pr-4">{t('exams.scoringProfile')}</th>
              <th className="py-3 pr-4">{t('exams.correct')}</th>
              <th className="py-3 pr-4">{t('exams.incorrect')}</th>
              <th className="py-3 pr-4">{t('exams.blank')}</th>
              <th className="py-3 pr-4">{t('exams.duration')}</th>
              <th className="py-3 pr-4 text-right">{t('exams.net')}</th>
              <th className="py-3 pr-4 text-right">{t('exams.xp')}</th>
              <th className="py-3 pr-1" />
            </tr>
          </thead>
          <tbody>
            {recent.map((ex) => {
              const net = ex.net
              const xp = ex.xp
              return (
                <tr
                  key={ex.id}
                  onDoubleClick={ex.sections?.length ? undefined : () => onDoubleClickIncorrect(ex)}
                  className={`${ex.sections?.length ? '' : 'cursor-pointer '}transition hover:bg-canvas-raise/50`}
                >
                  <td className="py-3 pr-4 text-canvas-text">{fmtDate(ex.date, locale)}</td>
                  <td className="py-3 pr-4 text-canvas-text">
                    {ex.sections?.length ? (
                      <details>
                        <summary className="cursor-pointer">{subjectLabel(ex.subject, t('common.unlabelled'))} · {t('exams.subjectCount', { count: fmtInt(ex.sections.length, locale) })}</summary>
                        <div className="mt-2 space-y-2 text-xs">
                          {ex.sections.map((section) => (
                            <div key={section.subject} className="flex items-center justify-between gap-2">
                              <span>{section.subject}: {fmtInt(section.correct, locale)} {t('exams.correctShort')} / {fmtInt(section.incorrect, locale)} {t('exams.incorrectShort')} / {fmtInt(section.blank, locale)} {t('exams.blankShort')} · {t('exams.net')} {fmtNet(netScoreWithRule(section.correct, section.incorrect, section.blank, ex.scoring_profile?.scoring_rule), locale)}</span>
                              <button type="button" aria-label={t('exams.addMissedQuestionFor', { subject: section.subject, date: fmtDate(ex.date, locale) })} onClick={() => onDoubleClickIncorrect({ ...ex, ...section })} className="shrink-0 underline">{t('exams.addMissedQuestion')}</button>
                            </div>
                          ))}
                        </div>
                      </details>
                    ) : subjectLabel(ex.subject, t('common.unlabelled'))}
                  </td>
                  <td className="py-3 pr-4 text-canvas-muted">{t(`exams.type.${ex.exam_type || 'branch'}`)}</td>
                  <td className="py-3 pr-4 text-canvas-muted">{ex.scoring_profile?.display_name || 'YKS (legacy)'} · v{ex.scoring_profile?.version || 1}</td>
                  <td className="py-3 pr-4 text-canvas-text">{fmtInt(ex.correct, locale)}</td>
                  <td
                    className="py-3 pr-4 text-canvas-text font-semibold transition hover:underline"
                    title={t('exams.doubleClickToAdd')}
                  >
                      <span className="inline-flex items-center gap-1">
                        {fmtInt(ex.incorrect, locale)}
                        {net < 0 && <ArrowDownRight size={12} />}
                      </span>
                    </td>
                  <td className="py-3 pr-4 text-canvas-muted">{fmtInt(ex.blank, locale)}</td>
                  <td className="py-3 pr-4 text-canvas-muted">
                    <span className="inline-flex items-center gap-1">
                      <Clock size={12} aria-label={t('exams.duration')} />
                      {fmtDuration(ex.duration_minutes, ex.duration_seconds)}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-right">
                    <span
                      className="font-semibold text-canvas-text"
                    >
                      {fmtNet(net, locale)}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-right text-canvas-text">{fmtInt(xp, locale)}</td>
                  <td className="py-3 pr-1 text-right">
                    <div className="inline-flex gap-1">
                      <button
                        type="button"
                        aria-label={t('exams.editNamed', { subject: ex.subject, date: fmtDate(ex.date, locale) })}
                        onClick={() => onEdit(ex)}
                        className="rounded p-1.5 text-canvas-muted hover:bg-canvas-raise hover:text-canvas-text"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        type="button"
                        aria-label={t('exams.deleteNamed', { subject: ex.subject, date: fmtDate(ex.date, locale) })}
                        onClick={() => onDelete(ex)}
                        className="rounded p-1.5 text-canvas-muted hover:bg-canvas-raise hover:text-canvas-text"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {recentError && (
        <div className="mt-3 rounded-lg border border-canvas-line bg-canvas-raise p-3 text-sm text-canvas-text">
          {recentError}
        </div>
      )}
    </Panel>
  )
}
