import { AVATAR_PRESETS } from '../social/profileDraft.js'
import { useI18n } from '../i18n.jsx'

const AVATARS = { sunrise: '☀️', moon: '🌙', leaf: '🍃', star: '⭐', book: '📘', mountain: '⛰️', wave: '🌊', lantern: '🏮' }
const inputCls = 'w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text outline-none focus:border-canvas-accent'

export default function StudentProfileFields({ profile, onChange }) {
  const { t } = useI18n()
  const textField = (field, key, type = 'text') => (
    <label key={field} className="block text-sm text-canvas-muted">
      {t(key)}
      <input className={`${inputCls} mt-1`} type={type} value={profile[field] ?? ''} onChange={(event) => onChange(field, type === 'number' ? (event.target.value === '' ? null : Number(event.target.value)) : event.target.value)} />
    </label>
  )
  return <div className="space-y-4">
    {textField('nickname', 'profile.name')}
    {textField('age_years', 'profile.age', 'number')}
    {textField('grade_year', 'profile.grade')}
    {textField('curriculum', 'profile.curriculum')}
    <p className="-mt-3 text-xs text-canvas-muted">{t('profile.curriculumHint')}</p>
    <label className="block text-sm text-canvas-muted">{t('profile.preferences')}<textarea className={`${inputCls} mt-1`} rows={2} value={profile.study_preferences ?? ''} onChange={(event) => onChange('study_preferences', event.target.value)} /></label>
    <label className="block text-sm text-canvas-muted">{t('profile.goals')}<textarea className={`${inputCls} mt-1`} rows={2} value={profile.study_goals ?? ''} onChange={(event) => onChange('study_goals', event.target.value)} /></label>
    <fieldset>
      <legend className="mb-2 text-sm text-canvas-muted">{t('profile.avatar')}</legend>
      <div className="grid grid-cols-4 gap-2">
        <button type="button" aria-pressed={profile.avatar_preset === null} onClick={() => onChange('avatar_preset', null)} className={`rounded-lg border p-2 text-xs focus-visible:outline focus-visible:outline-2 focus-visible:outline-canvas-accent ${profile.avatar_preset === null ? 'border-canvas-accent bg-canvas-raise' : 'border-canvas-line bg-canvas-base'}`}>{t('profile.avatar.none')}</button>
        {AVATAR_PRESETS.map((avatar) => <button key={avatar} type="button" aria-label={t(`profile.avatar.${avatar}`)} aria-pressed={profile.avatar_preset === avatar} onClick={() => onChange('avatar_preset', avatar)} className={`rounded-lg border p-2 text-2xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-canvas-accent ${profile.avatar_preset === avatar ? 'border-canvas-accent bg-canvas-raise' : 'border-canvas-line bg-canvas-base'}`}>
          <span aria-hidden="true">{AVATARS[avatar]}</span><span className="mt-1 block text-xs text-canvas-muted">{t(`profile.avatar.${avatar}`)}</span>
        </button>)}
      </div>
    </fieldset>
  </div>
}
