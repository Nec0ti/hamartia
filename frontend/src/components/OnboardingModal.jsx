import { useEffect, useState } from 'react'
import Modal from './Modal.jsx'
import StudentProfileFields from './StudentProfileFields.jsx'
import { useI18n } from '../i18n.jsx'
import { validateStudentProfile } from '../studentProfile/profile.js'

const TOUR_KEYS = ['dashboard', 'review', 'clock', 'privacy']
const empty = { nickname: null, age_years: null, grade_year: null, curriculum: null, study_preferences: null, study_goals: null, avatar_preset: null }

export default function OnboardingModal({ stage, onboarding, onLanguage, onSave, onDismiss }) {
  const { t, language, setLanguage } = useI18n()
  const [tourIndex, setTourIndex] = useState(0)
  const [profile, setProfile] = useState({ ...empty, ...(onboarding?.profile || {}) })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (stage === 'tutorial') setTourIndex(0)
    if (stage === 'survey') setProfile({ ...empty, ...(onboarding?.profile || {}) })
    setError('')
  }, [stage, onboarding])
  if (!stage) return null
  const update = async (data) => {
    setBusy(true)
    setError('')
    try { await onSave(data) } catch { setError(t('profile.error')) } finally { setBusy(false) }
  }
  const close = () => { if (!busy) onDismiss() }

  if (stage === 'language') return <Modal open onClose={close} title={t('onboarding.languageTitle')} footer={<button type="button" disabled={busy} onClick={() => { onLanguage(language); update({ ...onboarding, tutorial_completed: false, tutorial_skipped: false, survey_completed: false }) }} className="rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-canvas-base">{t('onboarding.next')}</button>}>
    <div className="space-y-4"><p className="text-sm text-canvas-muted">{t('onboarding.languageDescription')}</p>
      <label htmlFor="onboarding-language" className="block text-sm text-canvas-muted">{t('settings.language')}</label>
      <select id="onboarding-language" autoFocus value={language} onChange={(event) => { setLanguage(event.target.value); onLanguage(event.target.value) }} className="w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-canvas-text"><option value="en">English</option><option value="tr">Türkçe</option></select>
      {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
    </div>
  </Modal>

  if (stage === 'tutorial') {
    const step = TOUR_KEYS[tourIndex]
    return <Modal open onClose={close} title={t('onboarding.walkthroughTitle')} footer={<>
      <span className="mr-auto self-center text-xs text-canvas-muted">{t('onboarding.stepCount', { current: tourIndex + 1, total: TOUR_KEYS.length })}</span>
      {tourIndex > 0 && <button type="button" onClick={() => setTourIndex((current) => current - 1)} className="rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-muted">{t('onboarding.back')}</button>}
      <button type="button" disabled={busy} onClick={() => update({ ...onboarding, tutorial_completed: false, tutorial_skipped: true })} className="rounded-lg px-3 py-2 text-sm text-canvas-muted underline">{t('onboarding.skipTour')}</button>
      <button type="button" disabled={busy} onClick={() => tourIndex + 1 < TOUR_KEYS.length ? setTourIndex((current) => current + 1) : update({ ...onboarding, tutorial_completed: true, tutorial_skipped: false })} className="rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-canvas-base">{tourIndex + 1 < TOUR_KEYS.length ? t('onboarding.next') : (onboarding?.survey_completed ? t('settings.cancel') : t('onboarding.continueSurvey'))}</button>
    </>}>
      <section aria-live="polite" className="min-h-32 space-y-3 py-2"><h3 className="text-xl font-semibold text-canvas-text">{t(`onboarding.tour.${step}.title`)}</h3><p className="text-sm leading-relaxed text-canvas-muted">{t(`onboarding.tour.${step}.body`)}</p></section>
      {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
    </Modal>
  }

  return <Modal open onClose={close} title={t('onboarding.surveyTitle')} footer={<>
    <button type="button" disabled={busy} onClick={() => update({ ...onboarding, tutorial_skipped: onboarding?.tutorial_skipped || false, survey_completed: true })} className="mr-auto rounded-lg px-3 py-2 text-sm text-canvas-muted underline">{t('onboarding.skipSurvey')}</button>
    <button type="button" disabled={busy} onClick={() => {
      try { validateStudentProfile(profile) } catch (e) { setError(e.message.startsWith('Age') ? t('profile.ageError') : t('profile.error')); return }
      update({ ...onboarding, tutorial_completed: onboarding?.tutorial_completed || false, survey_completed: true, profile })
    }} className="rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-canvas-base">{busy ? t('settings.saving') : t('onboarding.finish')}</button>
  </>}>
    <div className="space-y-4"><p className="text-sm leading-relaxed text-canvas-muted">{t('onboarding.surveyDescription')}</p>
      <StudentProfileFields profile={profile} onChange={(field, value) => { setError(''); setProfile((current) => ({ ...current, [field]: value })) }} />
      {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
    </div>
  </Modal>
}
