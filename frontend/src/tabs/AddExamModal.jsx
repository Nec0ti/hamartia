import { useState } from 'react'
import { Calculator, X } from 'lucide-react'
import Modal from '../components/Modal.jsx'
import { fmtNet, fmtInt, fmtDuration, previewXp, netScore } from '../utils/formatters'
import { examSectionTotals } from '../utils/examSections.js'

/**
 * Add-Exam modal. Collects date, subject, duration (mins+secs), and the
 * correct/incorrect/blank split. Computes the YKS net score and XP live from
 * the canonical formulas so the user can preview the reward before saving.
 */
export default function AddExamModal({ open, form, setForm, onClose, onSubmit, editing = false }) {
  const [validationError, setValidationError] = useState('')
  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }))

  const fullMock = form.exam_type !== 'branch'
  const sections = form.sections || []
  const totals = fullMock ? examSectionTotals(sections) : form
  const net = netScore(totals.correct, totals.incorrect)
  const xp = previewXp(totals.correct, totals.incorrect, form.duration_minutes)
  const submit = (event) => {
    event.preventDefault()
    setValidationError('')
    if (fullMock) {
      const names = sections.map((section) => section.subject.trim().toLocaleLowerCase())
      if (!sections.length || names.some((name) => !name)) return setValidationError('En az bir ders adı gir.')
      if (new Set(names).size !== names.length) return setValidationError('Ders adları bu oturumda benzersiz olmalı.')
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
      title={editing ? 'Denemeyi düzenle' : 'Deneme ekle'}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-canvas-line bg-canvas-base px-4 py-2 text-sm font-medium text-canvas-muted transition hover:bg-canvas-raise"
          >
            Vazgeç
          </button>
          <button
            type="button"
            onClick={submit}
            className="rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-white shadow-crimson transition hover:opacity-90"
          >
            {editing ? 'Değişiklikleri kaydet' : 'Denemeyi kaydet'}
          </button>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Tarih">
            <input
              type="date"
              value={form.date}
              onChange={(e) => set('date', e.target.value)}
              className={inputCls}
            />
          </Field>
          <Field label="Deneme türü">
            <select value={form.exam_type} onChange={(e) => setForm((current) => ({
              ...current,
              exam_type: e.target.value,
              sections: e.target.value === 'branch' ? [] : current.sections,
              subject: e.target.value === 'branch' && current.exam_type !== 'branch' ? 'Matematik' : current.subject,
            }))} className={inputCls}>
              <option value="tyt">TYT</option>
              <option value="ayt">AYT</option>
              <option value="branch">Branş</option>
            </select>
          </Field>
          {!fullMock && <Field label="Ders">
            <input
              type="text"
              value={form.subject}
              onChange={(e) => set('subject', e.target.value)}
              className={inputCls}
              placeholder="Örn. Matematik"
            />
          </Field>}
        </div>

        {fullMock && (
          <section aria-label="Ders sonuçları" className="space-y-3 rounded-lg border border-canvas-line bg-canvas-base p-3">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-canvas-text">Ders sonuçları</h3>
              <button
                type="button"
                onClick={() => setForm((current) => ({
                  ...current,
                  sections: [...(current.sections || []), { subject: '', correct: 0, incorrect: 0, blank: 0 }],
                }))}
                className="rounded-lg border border-canvas-line px-3 py-2 text-xs text-canvas-text hover:bg-canvas-raise"
              >
                Ders ekle
              </button>
            </div>
            {sections.length === 0 && <p className="text-xs text-canvas-muted">Bu oturuma en az bir ders sonucu ekle.</p>}
            {sections.map((section, index) => (
              <div key={index} className="grid grid-cols-2 gap-2 rounded-lg border border-canvas-line p-3 sm:grid-cols-5">
                <label className="col-span-2 text-xs text-canvas-muted sm:col-span-1">
                  Ders
                  <input aria-label={`Ders adı ${index + 1}`} required value={section.subject} onChange={(e) => updateSection(index, 'subject', e.target.value)} placeholder="Örn. Türkçe" className={inputCls} />
                </label>
                {['correct', 'incorrect', 'blank'].map((key, itemIndex) => (
                  <label key={key} className="text-xs text-canvas-muted">
                    {['Doğru', 'Yanlış', 'Boş'][itemIndex]}
                    <input aria-label={`${['Doğru', 'Yanlış', 'Boş'][itemIndex]} · ${index + 1}. ders`} type="number" min={0} step={1} required value={section[key]} onChange={(e) => updateSection(index, key, Math.max(0, Math.trunc(Number(e.target.value) || 0)))} className={inputCls} />
                  </label>
                ))}
                <button type="button" aria-label={`Dersi kaldır ${section.subject || index + 1}`} onClick={() => setForm((current) => ({ ...current, sections: current.sections.filter((_, i) => i !== index) }))} className="col-span-2 justify-self-end text-xs text-accent sm:col-span-1 sm:self-end">Dersi kaldır</button>
              </div>
            ))}
          </section>
        )}

        <Field label="Süre">
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={0}
              value={form.duration_minutes}
              onChange={(e) => set('duration_minutes', Math.max(0, Number(e.target.value) || 0))}
              className={inputCls}
              placeholder="Dakika"
            />
            <span className="text-canvas-muted">dk</span>
            <span className="text-canvas-muted">:</span>
            <input
              type="number"
              min={0}
              max={59}
              value={form.duration_seconds}
              onChange={(e) => set('duration_seconds', Math.max(0, Number(e.target.value) || 0))}
              className={inputCls}
              placeholder="Saniye"
            />
            <span className="text-canvas-muted">sn</span>
          </div>
        </Field>

        {!fullMock && <div className="grid grid-cols-3 gap-4">
          <NumberField label="Doğru" value={form.correct} onChange={(v) => set('correct', Math.max(0, v))} positive />
          <NumberField label="Yanlış" value={form.incorrect} onChange={(v) => set('incorrect', Math.max(0, v))} positive />
          <NumberField label="Boş" value={form.blank} onChange={(v) => set('blank', Math.max(0, v))} positive />
        </div>}

        {/* Live preview of the canonical formulas. */}
        <div className="rounded-lg border border-canvas-line bg-canvas-base p-4">
          <div className="mb-3 flex items-center gap-2 text-canvas-muted">
            <Calculator size={14} />
            <span className="text-xs font-semibold uppercase tracking-wider">Canlı hesap</span>
          </div>
          <dl className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <dt className="text-canvas-muted">Net</dt>
              <dd className={`font-semibold ${net < 0 ? 'text-accent' : 'text-emerald-400'}`}>
                {fmtNet(net)}
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-canvas-muted">Net formülü</dt>
              <dd className="font-mono text-xs text-canvas-text">
                {totals.correct} − ({totals.incorrect} / 4)
              </dd>
            </div>
            <div className="my-2 border-t border-canvas-line" />
            <div className="flex items-center justify-between">
              <dt className="text-canvas-muted">Kazanılacak XP</dt>
              <dd className="font-semibold text-canvas-cyan">{fmtInt(xp)}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-canvas-muted">XP formülü</dt>
              <dd className="font-mono text-xs text-canvas-text">
                max(0, ⌊({net} · {totals.correct} · 1.5) − ({fmtDuration(form.duration_minutes, form.duration_seconds)} · {totals.incorrect} · 0.25)⌋)
              </dd>
            </div>
          </dl>
        </div>

        {validationError && <p role="alert" className="text-sm text-accent">{validationError}</p>}

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
