import { useEffect, useState } from 'react'
import Modal from './Modal.jsx'
import StudentProfileFields from './StudentProfileFields.jsx'
import api, { handleApiError } from '../services/api'
import { useI18n } from '../i18n.jsx'
import { validateStudentProfile } from '../studentProfile/profile.js'

const empty = { nickname: null, age_years: null, grade_year: null, curriculum: null, study_preferences: null, study_goals: null, avatar_preset: null }

export default function StudentProfileModal({ open, initial, onClose, onSaved, onRestartOnboarding }) {
  const { t } = useI18n()
  const [profile, setProfile] = useState(empty)
  const [saving, setSaving] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  useEffect(() => {
    if (open) {
      setProfile({ ...empty, ...(initial?.profile || {}) })
      setConfirmReset(false)
      setError('')
      setSaved(false)
    }
  }, [open, initial])

  const save = async () => {
    try { validateStudentProfile(profile) } catch (e) { setError(e.message.startsWith('Age') ? t('profile.ageError') : t('profile.error')); return }
    setSaving(true)
    setError('')
    try {
      const result = await api.studentProfile.save({ ...(initial || {}), profile })
      onSaved(result)
      setSaved(true)
    } catch (e) {
      setError(handleApiError(e, t).detail || t('profile.error'))
    } finally {
      setSaving(false)
    }
  }
  const reset = async () => {
    setSaving(true)
    setError('')
    try {
      const result = await api.studentProfile.reset()
      onSaved(result)
      onClose()
      onRestartOnboarding()
    } catch {
      setError(t('profile.error'))
    } finally {
      setSaving(false)
    }
  }

  return <Modal open={open} onClose={onClose} title={t('profile.title')} footer={<>
    {!confirmReset ? <button type="button" onClick={() => setConfirmReset(true)} disabled={saving} className="mr-auto rounded-lg px-3 py-2 text-sm text-canvas-muted underline">{t('profile.reset')}</button> : <div role="alertdialog" className="mr-auto flex items-center gap-2 text-xs text-canvas-muted"><span>{t('profile.resetConfirm')}</span><button type="button" onClick={reset} disabled={saving} className="rounded-lg border border-canvas-line px-2 py-1 text-canvas-text">{t('common.delete')}</button><button type="button" onClick={() => setConfirmReset(false)} className="rounded-lg px-2 py-1 underline">{t('settings.cancel')}</button></div>}
    <button type="button" onClick={onClose} disabled={saving} className="rounded-lg border border-canvas-line px-4 py-2 text-sm text-canvas-muted">{t('settings.cancel')}</button>
    <button type="button" onClick={save} disabled={saving} className="rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50">{saving ? t('settings.saving') : t('profile.save')}</button>
  </>}>
    <div className="space-y-4">
      <StudentProfileFields profile={profile} onChange={(field, value) => { setSaved(false); setProfile((current) => ({ ...current, [field]: value })) }} />
      {saved && <p role="status" className="text-sm text-canvas-muted">{t('profile.saved')}</p>}
      {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
    </div>
  </Modal>
}
