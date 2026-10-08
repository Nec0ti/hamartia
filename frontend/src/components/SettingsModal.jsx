import { useState } from 'react'
import { Save, X } from 'lucide-react'
import Modal from './Modal.jsx'
import { handleApiError } from '../services/api'

/**
 * Settings modal. Edits the LiteLLM proxy configuration (base URL, model name,
 * optional API key) persisted to backend/data/settings.json. Progression data
 * (XP / level / streak) is intentionally NOT editable here — it lives in
 * backend/data/user.json and is served read-only via /user.
 */
export default function SettingsModal({ open, settings, onSave, onClose }) {
  const [draft, setDraft] = useState(
    settings ?? { litellm_base_url: 'http://localhost:4000/v1', model_name: 'ollama/qwen2.5', api_key: '' },
  )
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        className="absolute right-4 top-4 z-10 w-full max-w-lg rounded-xl border border-canvas-line bg-canvas-panel p-6 shadow-glow"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight text-canvas-text">Settings</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="rounded-md p-1 text-canvas-muted transition hover:bg-canvas-raise hover:text-canvas-text"
          >
            <X size={18} />
          </button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wider text-canvas-muted">
              LiteLLM Base URL
            </label>
            <input
              className={inputCls}
              value={draft.litellm_base_url}
              onChange={(e) => setDraft({ ...draft, litellm_base_url: e.target.value })}
              placeholder="http://localhost:4000/v1"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wider text-canvas-muted">
              Model Name
            </label>
            <input
              className={inputCls}
              value={draft.model_name}
              onChange={(e) => setDraft({ ...draft, model_name: e.target.value })}
              placeholder="ollama/qwen2.5"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wider text-canvas-muted">
              API Key <span className="text-canvas-muted/60">(optional)</span>
            </label>
            <input
              type="password"
              className={inputCls}
              value={draft.api_key}
              onChange={(e) => setDraft({ ...draft, api_key: e.target.value })}
              placeholder="Leave empty for local proxy"
            />
          </div>
          {saved && <p className="text-xs text-emerald-400">Settings saved.</p>}
          {error && <p className="text-xs text-accent">{error}</p>}
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-canvas-line bg-canvas-base px-4 py-2 text-sm font-medium text-canvas-muted transition hover:bg-canvas-raise"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="inline-flex items-center gap-1.5 rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-white shadow-crimson transition hover:opacity-90 disabled:opacity-50"
          >
            <Save size={14} />
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

async function save() {
  setSaving(true)
  setSaved(false)
  setError(null)
  try {
    await onSave(draft)
    setSaved(true)
  } catch (e) {
    setError(handleApiError(e).detail)
  } finally {
    setSaving(false)
  }
}

const inputCls =
  'w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text outline-none transition hover:bg-canvas-raise focus:border-canvas-accent'
