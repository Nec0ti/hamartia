import { levelForXp } from '../utils/formatters.js'

export const STUDENT_PROFILE_FIELDS = Object.freeze([
  'nickname', 'age_years', 'grade_year', 'curriculum', 'study_preferences', 'study_goals', 'avatar_preset',
])
export const STUDENT_AVATARS = Object.freeze(['sunrise', 'moon', 'leaf', 'star', 'book', 'mountain', 'wave', 'lantern', 'comet', 'planet', 'galaxy'])
export const AVATAR_UNLOCK_LEVELS = Object.freeze({ comet: 2, planet: 3, galaxy: 5 })

export function studentAvatarUnlocked(preset, totalXp) {
  return !AVATAR_UNLOCK_LEVELS[preset] || levelForXp(totalXp) >= AVATAR_UNLOCK_LEVELS[preset]
}

export function firstRunStage(state) {
  if (!state || state.survey_completed) return null
  return state.tutorial_completed || state.tutorial_skipped ? 'survey' : 'language'
}

export function validateStudentProfile(profile) {
  if (!profile || Object.keys(profile).some((key) => !STUDENT_PROFILE_FIELDS.includes(key))) throw new Error('Unexpected profile field.')
  if (profile.age_years !== null && profile.age_years !== undefined && (!Number.isInteger(profile.age_years) || profile.age_years < 5 || profile.age_years > 120)) {
    throw new Error('Age must be a whole number from 5 to 120.')
  }
  const limits = { nickname: 80, grade_year: 80, curriculum: 120, study_preferences: 2000, study_goals: 2000 }
  for (const [field, maximum] of Object.entries(limits)) {
    if (profile[field] != null && (typeof profile[field] !== 'string' || new TextEncoder().encode(profile[field]).length > maximum)) throw new Error(`${field} is too long.`)
  }
  if (profile.avatar_preset != null && !STUDENT_AVATARS.includes(profile.avatar_preset)) throw new Error('Choose a built-in avatar.')
  return profile
}
