import { useMemo, useState } from 'react'
import Modal from '../components/Modal.jsx'
import api from '../services/api'
import { handleApiError } from '../services/api'
import { useI18n } from '../i18n.jsx'

const EMPTY = {
  display_name: '',
  country_label: '',
  scoring_rule: { correct_points: '1/1', wrong_penalty: '1/4', blank_points: '0/1' },
}

const inputClass = 'mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text'

export default function ExamProfileManager({ open, profiles, onClose, onSaved }) {
  const { t } = useI18n()
  const custom = useMemo(() => profiles.filter((profile) => profile.profile_id !== 'legacy-yks'), [profiles])
  const currentById = useMemo(() => {
    const latest = new Map()
    for (const profile of custom) {
      if (!latest.has(profile.profile_id) || latest.get(profile.profile_id).version < profile.version) latest.set(profile.profile_id, profile)
    }
    return [...latest.values()].sort((a, b) => a.display_name.localeCompare(b.display_name))
  }, [custom])
  const [selectedId, setSelectedId] = useState('')
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const selected = currentById.find((profile) => profile.profile_id === selectedId)

  const selectProfile = (profileId) => {
    setSelectedId(profileId)
    const profile = currentById.find((item) => item.profile_id === profileId)
    setForm(profile ? {
      display_name: profile.display_name,
      country_label: profile.country_label,
      scoring_rule: { ...profile.scoring_rule },
    } : EMPTY)
    setError('')
  }

  const setRule = (key, value) => setForm((current) => ({
    ...current, scoring_rule: { ...current.scoring_rule, [key]: value },
  }))

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    try {
      if (selected) await api.examProfiles.update(selected.profile_id, form)
      else await api.examProfiles.create(form)
      await onSaved()
      selectProfile('')
    } catch (e) {
      setError(handleApiError(e, t).detail)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={t('exams.profileManager')}>
      <form onSubmit={submit} className="space-y-4">
        <label className="block text-xs font-medium text-canvas-muted">
          {t('exams.editProfile')}
          <select className={inputClass} value={selectedId} onChange={(event) => selectProfile(event.target.value)}>
            <option value="">{t('exams.newProfile')}</option>
            {currentById.map((profile) => <option key={profile.profile_id} value={profile.profile_id}>
              {profile.display_name} · {profile.country_label} · v{profile.version}
            </option>)}
          </select>
        </label>
        {selected && <p className="text-xs text-canvas-muted">{t('exams.profileEditCreatesVersion', { version: selected.version + 1 })}</p>}
        <label className="block text-xs font-medium text-canvas-muted">{t('exams.profileDisplayName')}<input required maxLength={80} className={inputClass} value={form.display_name} onChange={(event) => setForm((current) => ({ ...current, display_name: event.target.value }))} /></label>
        <label className="block text-xs font-medium text-canvas-muted">{t('exams.profileCountryLabel')}<input required maxLength={80} className={inputClass} value={form.country_label} onChange={(event) => setForm((current) => ({ ...current, country_label: event.target.value }))} /></label>
        <fieldset className="space-y-3 rounded-lg border border-canvas-line p-3">
          <legend className="px-1 text-xs font-semibold text-canvas-text">{t('exams.scoringRule')}</legend>
          {[
            ['correct_points', 'exams.correctPoints'],
            ['wrong_penalty', 'exams.wrongPenalty'],
            ['blank_points', 'exams.blankPoints'],
          ].map(([key, label]) => <label key={key} className="block text-xs font-medium text-canvas-muted">
            {t(label)}
            <input required inputMode="text" placeholder="1/2" aria-label={t(label)} className={inputClass} value={form.scoring_rule[key]} onChange={(event) => setRule(key, event.target.value)} />
          </label>)}
          <p className="text-xs text-canvas-muted">{t('exams.rationalRuleHelp')}</p>
        </fieldset>
        <p className="text-xs text-canvas-muted">{t('exams.customRuleNotOfficial')}</p>
        {error && <p role="alert" className="text-sm text-canvas-text">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-lg border border-canvas-line px-4 py-2 text-sm text-canvas-muted">{t('common.cancel')}</button>
          <button type="submit" className="rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-canvas-base">{selected ? t('exams.saveProfileVersion') : t('exams.createProfile')}</button>
        </div>
      </form>
    </Modal>
  )
}
