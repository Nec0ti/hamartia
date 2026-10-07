// Frontend mirrors of the canonical backend formulas (see backend/app/core/formulas.py).
// These are display-only helpers; the backend remains the source of truth for
// any value persisted or returned by the API. Keeping them in sync by hand is
// acceptable because the frontend only uses them for live previews.

export const YKS_PENALTY_FACTOR = 4.0

/** YKS net score: correct minus 1/4 penalty per incorrect. */
export const netScore = (correct, incorrect) => {
  const total = correct + incorrect
  if (total <= 0) return 0.0
  return correct - incorrect / YKS_PENALTY_FACTOR
}

/**
 * XP preview for a candidate exam. Matches xp_for_exam exactly except for the
 * duration_minutes <= 0 guard (frontend inputs default to 0).
 */
export const previewXp = (correct, incorrect, durationMinutes) => {
  const net = netScore(correct, incorrect)
  const minutes = Math.max(1, Math.round(durationMinutes))
  const raw = net * correct * 1.5 - minutes * incorrect * 0.25
  return Math.max(0, Math.round(raw))
}

/** Cumulative XP to next level: level N needs N * 500 total XP. */
export const levelForXp = (totalXp) => {
  if (totalXp < 500) return 1
  return Math.floor(totalXp / 500) + 1
}

/** XP required to advance from the current level to the next. */
export const xpToNextLevel = (level) => (level + 1) * 500

/** Progress (0..1) toward the next level. 1.0 when already at the cap. */
export const xpProgress = (totalXp, level) => {
  if (level <= 1) return 0
  const earned = totalXp - (level - 1) * 500
  const needed = 500
  return Math.min(1, Math.max(0, earned / needed))
}

/* ------------------------------ formatters ------------------------------ */

/** Compact numeric formatter for stat labels (e.g. 127 -> "127"). */
export const fmtInt = (n) => Math.round(Number(n) || 0).toLocaleString('en-US')

/** Present positive nets in green, negative in crimson, zero neutral. */
export const fmtNet = (net) => {
  const rounded = Math.round(net * 100) / 100
  if (rounded === 0) return '0.0'
  const sign = rounded < 0 ? '-' : ''
  return `${sign}${rounded.toFixed(2)}`
}

/** Format a whole number of minutes with leading zero padding. */
export const fmtDuration = (minutes, seconds) => {
  const m = Math.max(0, Math.floor(minutes))
  const s = Math.max(0, Math.floor(seconds || 0))
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

/** Human-readable subject/emoji tag for a subject string. */
export const subjectLabel = (subject) =>
  (subject || 'Unlabelled').slice(0, 24)
