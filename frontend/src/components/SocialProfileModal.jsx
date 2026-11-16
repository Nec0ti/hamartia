import { useEffect, useState } from 'react'
import Modal from './Modal'
import { useI18n } from '../i18n.jsx'
import socialClient from '../social/socialClient.js'
import { AVATAR_PRESETS, emptyProfileDraft, profileDraftFromServer, validateProfileDraft } from '../social/profileDraft.js'
import SocialForumPanel from './SocialForumPanel.jsx'

const TEXT_FIELDS = [
  ['nickname', 'nickname_public', 'social.nickname', 80],
  ['school_grade', 'school_grade_public', 'social.schoolGrade', 80],
  ['school_class', 'school_class_public', 'social.schoolClass', 80],
  ['curriculum', 'curriculum_public', 'social.curriculum', 120],
  ['study_preferences', 'study_preferences_public', 'social.studyPreferences', 2000, true],
  ['study_goals', 'study_goals_public', 'social.studyGoals', 2000, true],
]

function FieldVisibility({ checked, onChange, label }) {
  const { t, language } = useI18n()
  return (
    <label className="mt-2 flex items-start gap-2 text-xs text-canvas-muted">
      <input type="checkbox" checked={checked} onChange={onChange} className="mt-0.5 accent-canvas-accent" />
      <span>{t('social.visibility', { field: label })}</span>
    </label>
  )
}

export default function SocialProfileModal({ open, onClose }) {
  const { t, language } = useI18n()
  const [draft, setDraft] = useState(emptyProfileDraft)
  const [signedIn, setSignedIn] = useState(false)
  const [agreementAccepted, setAgreementAccepted] = useState(false)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!open) {
      setAgreementAccepted(false)
      setSignedIn(false)
      socialClient.clearAgreementAcceptance()
      return undefined
    }
    setError('')
    setSaved(false)
    setDraft(emptyProfileDraft())
    setAgreementAccepted(false)
    socialClient.clearAgreementAcceptance()
    return () => socialClient.clearAgreementAcceptance()
  }, [open])

  useEffect(() => {
    if (!open || !agreementAccepted || !socialClient.isEnabled()) return undefined
    socialClient.setAgreementAccepted(true)
    let active = true
    setLoading(true)
    socialClient.getProfile().then((result) => {
      if (!active) return
      if (result.status === 'signedIn') {
        setSignedIn(true)
        setDraft(profileDraftFromServer(result.profile))
      } else {
        setSignedIn(false)
      }
    }).catch(() => {
      if (active) {
        setSignedIn(false)
        setError('social.loadError')
      }
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [open, agreementAccepted])

  const update = (key, value) => {
    setSaved(false)
    setDraft((current) => ({ ...current, [key]: value }))
  }

  const signIn = async () => {
    setBusy(true)
    setError('')
    try {
      const result = await socialClient.signIn()
      if (result.status === 'cancelled') return
      if (result.status !== 'signedIn') {
        setError('social.notConfigured')
        return
      }
      const profile = await socialClient.getProfile()
      if (profile.status === 'signedIn') {
        setSignedIn(true)
        setDraft(profileDraftFromServer(profile.profile))
      } else {
        setSignedIn(false)
        setError('social.loadError')
      }
    } catch {
      setError('social.signInError')
    } finally {
      setBusy(false)
    }
  }

  const save = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    setSaved(false)
    try {
      const patch = validateProfileDraft(draft)
      const result = await socialClient.patchProfile(patch)
      if (result.status === 'signedIn') {
        setDraft(profileDraftFromServer(result.profile))
        setSaved(true)
      } else {
        setSignedIn(false)
      }
    } catch {
      setError('social.saveError')
    } finally {
      setBusy(false)
    }
  }

  const signOut = async () => {
    setBusy(true)
    setError('')
    try {
      await socialClient.signOut()
      setSignedIn(false)
      setDraft(emptyProfileDraft())
    } catch {
      setError('social.signInError')
    } finally {
      setBusy(false)
    }
  }

  const closeModal = () => {
    if (signedIn) socialClient.signOut().catch(() => {})
    socialClient.clearAgreementAcceptance()
    setAgreementAccepted(false)
    setSignedIn(false)
    setDraft(emptyProfileDraft())
    onClose()
  }

  return (
    <Modal open={open} onClose={closeModal} title={t('social.title')}>
      <p className="mb-4 text-sm text-canvas-muted">{t('social.description')}</p>
      <p className="mb-4 rounded-lg border border-canvas-line bg-canvas-base p-3 text-xs text-canvas-muted">{t('social.publicNotice')}</p>
      <div className="mb-4 space-y-2 text-sm">
        <p>{t('social.legalLinks')}</p>
        <ul className="list-inside list-disc">
          <li><a className="underline" href={language === 'tr' ? 'https://nec0ti.github.io/hamartia/tr/user-agreement-v0.1-draft.html' : 'https://nec0ti.github.io/hamartia/user-agreement-v0.1-draft.html'} target="_blank" rel="noreferrer">{t('social.userAgreement')}</a></li>
          <li><a className="underline" href={language === 'tr' ? 'https://nec0ti.github.io/hamartia/tr/privacy-and-consent/' : 'https://nec0ti.github.io/hamartia/privacy-and-consent/'} target="_blank" rel="noreferrer">{t('social.privacyNotice')}</a></li>
        </ul>
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={agreementAccepted}
            onChange={(event) => {
              const accepted = event.target.checked
              socialClient.setAgreementAccepted(accepted)
              setAgreementAccepted(accepted)
              if (!accepted) {
                if (signedIn) socialClient.signOut().catch(() => {})
                setSignedIn(false)
                setDraft(emptyProfileDraft())
              }
            }}
            className="mt-1 accent-canvas-accent"
            required
            aria-required="true"
          />
          <span>{t('social.acceptAgreement')}</span>
        </label>
        <p className="text-xs text-canvas-muted">{t('social.agreementReviewBlocker')}</p>
      </div>

      {!socialClient.isEnabled() ? (
        <div className="space-y-3">
          <p role="status" className="text-sm text-canvas-muted">{t('social.notConfigured')}</p>
          <button type="button" disabled className="rounded-lg bg-canvas-line px-4 py-2 text-sm text-canvas-muted opacity-60">
            {t('social.signIn')}
          </button>
        </div>
      ) : loading ? (
        <p role="status" className="py-4 text-sm text-canvas-muted">{t('social.loading')}</p>
      ) : !signedIn ? (
        <div className="space-y-3">
          <p className="text-sm text-canvas-muted">{t('social.signedOut')}</p>
          <button type="button" onClick={signIn} disabled={busy || !agreementAccepted || !socialClient.isEnabled()} className="rounded-lg bg-canvas-text px-4 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50">
            {busy ? t('social.signingIn') : t('social.signIn')}
          </button>
        </div>
      ) : (
        <>
        <form onSubmit={save} className="space-y-4">
          {TEXT_FIELDS.slice(0, 1).map(([field, visibility, label, max]) => (
            <div key={field}>
              <label htmlFor={`social-${field}`} className="mb-1 block text-sm font-medium text-canvas-text">{t(label)}</label>
              <input id={`social-${field}`} maxLength={max} value={draft[field]} onChange={(event) => update(field, event.target.value)} className="w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text" />
              <FieldVisibility checked={draft[visibility]} onChange={(event) => update(visibility, event.target.checked)} label={t(label)} />
            </div>
          ))}

          <div>
            <label htmlFor="social-age" className="mb-1 block text-sm font-medium text-canvas-text">{t('social.age')}</label>
            <input id="social-age" type="number" min="5" max="120" step="1" value={draft.age ?? ''} onChange={(event) => update('age', event.target.value === '' ? null : Number(event.target.value))} className="w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text" />
            <p className="mt-1 text-xs text-canvas-muted">{t('social.ageHint')}</p>
            <FieldVisibility checked={draft.age_public} onChange={(event) => update('age_public', event.target.checked)} label={t('social.age')} />
          </div>

          {TEXT_FIELDS.slice(1).map(([field, visibility, label, max, multiline]) => (
            <div key={field}>
              <label htmlFor={`social-${field}`} className="mb-1 block text-sm font-medium text-canvas-text">{t(label)}</label>
              {multiline ? (
                <textarea id={`social-${field}`} maxLength={max} rows={3} value={draft[field]} onChange={(event) => update(field, event.target.value)} className="w-full resize-y rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text" />
              ) : (
                <input id={`social-${field}`} maxLength={max} value={draft[field]} onChange={(event) => update(field, event.target.value)} className="w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text" />
              )}
              <FieldVisibility checked={draft[visibility]} onChange={(event) => update(visibility, event.target.checked)} label={t(label)} />
            </div>
          ))}

          <div>
            <label htmlFor="social-avatar" className="mb-1 block text-sm font-medium text-canvas-text">{t('social.avatar')}</label>
            <select id="social-avatar" value={draft.avatar_preset} onChange={(event) => update('avatar_preset', event.target.value)} className="w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text">
              {AVATAR_PRESETS.map((preset) => <option key={preset} value={preset}>{t(`social.avatar.${preset}`)}</option>)}
            </select>
            <FieldVisibility checked={draft.avatar_preset_public} onChange={(event) => update('avatar_preset_public', event.target.checked)} label={t('social.avatar')} />
          </div>

          {error && <p role="alert" className="text-sm text-red-300">{t(error)}</p>}
          {saved && <p role="status" className="text-sm text-green-300">{t('social.saved')}</p>}
          <div className="flex flex-wrap justify-between gap-2 border-t border-canvas-line pt-4">
            <button type="button" onClick={signOut} disabled={busy} className="rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-muted hover:bg-canvas-raise disabled:opacity-50">{t('social.signOut')}</button>
            <button type="submit" disabled={busy} className="rounded-lg bg-canvas-text px-4 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50">{t('common.save')}</button>
          </div>
        </form>
        <SocialForumPanel />
        </>
      )}

      {error && !signedIn && <p role="alert" className="mt-4 text-sm text-red-300">{t(error)}</p>}
    </Modal>
  )
}
