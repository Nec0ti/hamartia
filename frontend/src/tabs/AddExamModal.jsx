import { useState } from 'react'
import { Calculator, X } from 'lucide-react'
import Modal from '../components/Modal.jsx'
import { fmtNet, fmtInt, fmtDuration, previewXp, netScore, netScoreWithRule } from '../utils/formatters'
import { examSectionTotals } from '../utils/examSections.js'
import { useI18n } from '../i18n.jsx'

/**
 * Add-Exam modal. Collects date, subject, duration (mins+secs), and the
 * correct/incorrect/blank split. Computes the YKS net score and XP live from
 * the canonical formulas so the user can preview the reward before saving.
 */
export default function AddExamModal({ open, form, setForm, onClose, onSubmit, editing = false, profiles = [] }) {
  const { t, locale } = useI18n()
  const [validationError, setValidationError] = useState('')
  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }))

  const fullMock = form.exam_type !== 'branch'
  const customMock = form.exam_type === 'custom'
  const sections = form.sections || []
  const totals = fullMock ? examSectionTotals(sections) : form
  const selectedProfile = profiles.find((item) => item.profile_id === (form.scoring_profile_id || 'legacy-yks')
    && item.version === (form.scoring_profile_version || 1)) || profiles.find((item) => item.profile_id === 'legacy-yks')
  const rule = selectedProfile?.scoring_rule || { correct_points: '1/1', wrong_penalty: '1/4', blank_points: '0/1' }
  const net = netScoreWithRule(totals.correct, totals.incorrect, totals.blank, rule)
  const xp = previewXp(totals.correct, totals.incorrect, form.duration_minutes)
  const submit = (event) => {
    event.preventDefault()
    setValidationError('')
    if (fullMock) {
      const names = sections.map((section) => section.subject.trim().toLocaleLowerCase())
      if (customMock && !form.format_name.trim()) return setValidationError(t('exams.customNameRequired'))
      if (!sections.length || names.some((name) => !name)) return setValidationError(t('exams.sectionRequired'))
      if (new Set(names).size !== names.length) return setValidationError(t('exams.uniqueSubjects'))
      if (customMock && sections.length > 12) return setValidationError(t('exams.customSectionLimit', { count: 12 }))
    }
    onSubmit(event)
  }

  const updateSection = (index, key, value) => setForm((current) => ({
    ...current,
    sections: current.sections.map((section, i) => i === index ? { ...section, [key]: value } : section),
  }))

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? t('exams.editTitle') : t('exams.addTitle')}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-canvas-line bg-canvas-base px-4 py-2 text-sm font-medium text-canvas-muted transition hover:bg-canvas-raise"
          >
            {t('common.cancel')}
          </button>
          <button
            type="button"
            onClick={submit}
            className="rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-canvas-base shadow-crimson transition hover:opacity-90"
          >
            {editing ? t('exams.saveChanges') : t('exams.saveExam')}
          </button>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t('exams.date')}>
            <input
              type="date"
              value={form.date}
              onChange={(e) => set('date', e.target.value)}
              className={inputCls}
            />
          </Field>
          <Field label={t('exams.examType')}>
            <select value={form.exam_type} onChange={(e) => setForm((current) => ({
              ...current,
              exam_type: e.target.value,
              format_name: e.target.value === 'custom' ? (current.format_name || '') : '',
              sections: e.target.value === 'branch' ? [] : current.sections,
              subject: e.target.value === 'branch' && current.exam_type !== 'branch' ? t('exams.defaultSubject') : current.subject,
            }))} className={inputCls}>
              <option value="tyt">TYT</option>
              <option value="ayt">AYT</option>
              <option value="branch">{t('exams.branch')}</option>
              <option value="custom">{t('exams.type.custom')}</option>
            </select>
          </Field>
          {customMock && <Field label={t('exams.customFormatName')}>
            <input type="text" maxLength={120} required value={form.format_name || ''} onChange={(e) => set('format_name', e.target.value)} placeholder={t('exams.customFormatPlaceholder')} className={inputCls} />
            <p className="mt-1 text-xs text-canvas-muted">{t('exams.customFormatHelp')}</p>
          </Field>}
          {!fullMock && <Field label={t('exams.subject')}>
            <input
              type="text"
              value={form.subject}
              onChange={(e) => set('subject', e.target.value)}
              className={inputCls}
              placeholder={t('exams.subjectPlaceholder')}
            />
          </Field>}
        </div>

        <Field label={t('exams.scoringProfile')}>
          <select aria-label={t('exams.scoringProfile')} value={`${form.scoring_profile_id || 'legacy-yks'}@${form.scoring_profile_version || 1}`} onChange={(event) => {
            const [scoring_profile_id, version] = event.target.value.split('@')
            setForm((current) => ({ ...current, scoring_profile_id, scoring_profile_version: Number(version) }))
          }} className={inputCls}>
            {profiles.map((item) => <option key={`${item.profile_id}@${item.version}`} value={`${item.profile_id}@${item.version}`}>
              {item.display_name} · {item.country_label} · v{item.version}
            </option>)}
          </select>
          <p className="mt-1 text-xs text-canvas-muted">{t('exams.scoringProfileSnapshot')}</p>
        </Field>

        {fullMock && (
          <section aria-label={t('exams.sectionResults')} className="space-y-3 rounded-lg border border-canvas-line bg-canvas-base p-3">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-canvas-text">{t('exams.sectionResults')}</h3>
              <button
                type="button"
                disabled={customMock && sections.length >= 12}
                onClick={() => setForm((current) => ({
                  ...current,
                  sections: [...(current.sections || []), { subject: '', correct: 0, incorrect: 0, blank: 0 }],
                }))}
                className="rounded-lg border border-canvas-line px-3 py-2 text-xs text-canvas-text hover:bg-canvas-raise disabled:opacity-50"
              >
                {customMock ? t('exams.addSection') : t('exams.addSubject')}
              </button>
            </div>
            {customMock && <p className="text-xs text-canvas-muted">{t('exams.customSectionLimit', { count: 12 })}</p>}
            {sections.length === 0 && <p className="text-xs text-canvas-muted">{t('exams.addOneSubject')}</p>}
            {sections.map((section, index) => (
              <div key={index} className="grid grid-cols-2 gap-2 rounded-lg border border-canvas-line p-3 sm:grid-cols-5">
                <label className="col-span-2 text-xs text-canvas-muted sm:col-span-1">
                  {customMock ? t('exams.sectionName') : t('exams.subject')}
                  <input aria-label={t(customMock ? 'exams.sectionNumber' : 'exams.subjectNumber', { number: index + 1 })} required value={section.subject} onChange={(e) => updateSection(index, 'subject', e.target.value)} placeholder={customMock ? '' : t('exams.turkishPlaceholder')} className={inputCls} />
                </label>
                {['correct', 'incorrect', 'blank'].map((key, itemIndex) => (
                  <label key={key} className="text-xs text-canvas-muted">
                    {[t('exams.correct'), t('exams.incorrect'), t('exams.blank')][itemIndex]}
                    <input aria-label={t('exams.resultForSubject', { result: [t('exams.correct'), t('exams.incorrect'), t('exams.blank')][itemIndex], number: index + 1 })} type="number" min={0} step={1} required value={section[key]} onChange={(e) => updateSection(index, key, Math.max(0, Math.trunc(Number(e.target.value) || 0)))} className={inputCls} />
                  </label>
                ))}
                <button type="button" aria-label={t('exams.removeSubjectNamed', { subject: section.subject || index + 1 })} onClick={() => setForm((current) => ({ ...current, sections: current.sections.filter((_, i) => i !== index) }))} className="col-span-2 justify-self-end text-xs text-canvas-text sm:col-span-1 sm:self-end">{t('exams.removeSubject')}</button>
              </div>
            ))}
          </section>
        )}

        <Field label={t('exams.duration')}>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={0}
              value={form.duration_minutes}
              onChange={(e) => set('duration_minutes', Math.max(0, Number(e.target.value) || 0))}
              className={inputCls}
              placeholder={t('exams.minutes')}
            />
            <span className="text-canvas-muted">{t('exams.minutesShort')}</span>
            <span className="text-canvas-muted">:</span>
            <input
              type="number"
              min={0}
              max={59}
              value={form.duration_seconds}
              onChange={(e) => set('duration_seconds', Math.max(0, Number(e.target.value) || 0))}
              className={inputCls}
              placeholder={t('exams.seconds')}
            />
            <span className="text-canvas-muted">{t('exams.secondsShort')}</span>
          </div>
        </Field>

        {!fullMock && <div className="grid grid-cols-3 gap-4">
          <NumberField label={t('exams.correct')} value={form.correct} onChange={(v) => set('correct', Math.max(0, v))} positive />
          <NumberField label={t('exams.incorrect')} value={form.incorrect} onChange={(v) => set('incorrect', Math.max(0, v))} positive />
          <NumberField label={t('exams.blank')} value={form.blank} onChange={(v) => set('blank', Math.max(0, v))} positive />
        </div>}

        {/* Live preview of the canonical formulas. */}
        <div className="rounded-lg border border-canvas-line bg-canvas-base p-4">
          <div className="mb-3 flex items-center gap-2 text-canvas-muted">
            <Calculator size={14} />
            <span className="text-xs font-semibold uppercase tracking-wider">{t('exams.livePreview')}</span>
          </div>
          <dl className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <dt className="text-canvas-muted">{t('exams.net')}</dt>
              <dd className="font-semibold text-canvas-text">
                {fmtNet(net, locale)}
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-canvas-muted">{t('exams.netFormula')}</dt>
              <dd className="font-mono text-xs text-canvas-text">
                {totals.correct} × {rule.correct_points} − {totals.incorrect} × {rule.wrong_penalty} + {totals.blank} × {rule.blank_points}
              </dd>
            </div>
            <div className="my-2 border-t border-canvas-line" />
            <div className="flex items-center justify-between">
              <dt className="text-canvas-muted">{t('exams.xpEarned')}</dt>
              <dd className="font-semibold text-canvas-text">{fmtInt(xp, locale)}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-canvas-muted">{t('exams.xpFormula')}</dt>
              <dd className="font-mono text-xs text-canvas-text">
                max(0, ⌊({fmtNet(netScore(totals.correct, totals.incorrect), locale)} · {fmtInt(totals.correct, locale)} · 1.5) − ({fmtDuration(form.duration_minutes, form.duration_seconds)} · {fmtInt(totals.incorrect, locale)} · 0.25)⌋)
              </dd>
            </div>
            <p className="text-xs text-canvas-muted">{t('exams.xpIndependentOfScoring')}</p>
          </dl>
        </div>

        {validationError && <p role="alert" className="text-sm text-canvas-text">{validationError}</p>}

        <X size={18} className="absolute right-4 top-4 text-canvas-muted" />
      </form>
    </Modal>
  )
}

const inputCls =
  'w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text outline-none transition hover:bg-canvas-raise focus:border-canvas-accent'

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wider text-canvas-muted">
        {label}
      </span>
      {children}
    </label>
  )
}

function NumberField({ label, value, onChange, positive }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wider text-canvas-muted">
        {label}
      </span>
      <input
        type="number"
        min={0}
        value={value}
        onChange={(e) => onChange(Math.max(0, Number(e.target.value) || 0))}
        className={inputCls}
      />
    </label>
  )
}
