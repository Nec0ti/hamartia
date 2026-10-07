import { useState } from 'react'
import { Calculator, X } from 'lucide-react'
import Modal from '../components/Modal.jsx'
import { fmtNet, fmtInt, fmtDuration, previewXp, netScore } from '../utils/formatters'

/**
 * Add-Exam modal. Collects date, subject, duration (mins+secs), and the
 * correct/incorrect/blank split. Computes the YKS net score and XP live from
 * the canonical formulas so the user can preview the reward before saving.
 */
export default function AddExamModal({ open, form, setForm, onClose, onSubmit }) {
  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }))

  const net = netScore(form.correct, form.incorrect)
  const xp = previewXp(form.correct, form.incorrect, form.duration_minutes)

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add Exam"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-canvas-line bg-canvas-base px-4 py-2 text-sm font-medium text-canvas-muted transition hover:bg-canvas-raise"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onSubmit}
            className="rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-white shadow-crimson transition hover:opacity-90"
          >
            Save Exam
          </button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Date">
            <input
              type="date"
              value={form.date}
              onChange={(e) => set('date', e.target.value)}
              className={inputCls}
            />
          </Field>
          <Field label="Subject">
            <input
              type="text"
              value={form.subject}
              onChange={(e) => set('subject', e.target.value)}
              className={inputCls}
              placeholder="e.g. Math"
            />
          </Field>
        </div>

        <Field label="Duration">
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={0}
              value={form.duration_minutes}
              onChange={(e) => set('duration_minutes', Math.max(0, Number(e.target.value) || 0))}
              className={inputCls}
              placeholder="Minutes"
            />
            <span className="text-canvas-muted">min</span>
            <span className="text-canvas-muted">:</span>
            <input
              type="number"
              min={0}
              value={form.duration_seconds}
              onChange={(e) => set('duration_seconds', Math.max(0, Number(e.target.value) || 0))}
              className={inputCls}
              placeholder="Seconds"
            />
            <span className="text-canvas-muted">sec</span>
          </div>
        </Field>

        <div className="grid grid-cols-3 gap-4">
          <NumberField label="Correct" value={form.correct} onChange={(v) => set('correct', Math.max(0, v))} positive />
          <NumberField label="Incorrect" value={form.incorrect} onChange={(v) => set('incorrect', Math.max(0, v))} positive />
          <NumberField label="Blank" value={form.blank} onChange={(v) => set('blank', Math.max(0, v))} positive />
        </div>

        {/* Live preview of the canonical formulas. */}
        <div className="rounded-lg border border-canvas-line bg-canvas-base p-4">
          <div className="mb-3 flex items-center gap-2 text-canvas-muted">
            <Calculator size={14} />
            <span className="text-xs font-semibold uppercase tracking-wider">Live Preview</span>
          </div>
          <dl className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <dt className="text-canvas-muted">Net score</dt>
              <dd className={`font-semibold ${net < 0 ? 'text-accent' : 'text-emerald-400'}`}>
                {fmtNet(net)}
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-canvas-muted">Formula</dt>
              <dd className="font-mono text-xs text-canvas-text">
                {form.correct} − ({form.incorrect} / 4)
              </dd>
            </div>
            <div className="my-2 border-t border-canvas-line" />
            <div className="flex items-center justify-between">
              <dt className="text-canvas-muted">XP earned</dt>
              <dd className="font-semibold text-canvas-cyan">{fmtInt(xp)}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-canvas-muted">Formula</dt>
              <dd className="font-mono text-xs text-canvas-text">
                max(0, ⌊({net} · {form.correct} · 1.5) − ({fmtDuration(form.duration_minutes, form.duration_seconds)} · {form.incorrect} · 0.25)⌋)
              </dd>
            </div>
          </dl>
        </div>

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
