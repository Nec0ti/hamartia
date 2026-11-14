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
  return Math.max(0, Math.trunc(raw))
}

/** Cumulative XP to next level: level N needs N * 500 total XP. */
export const levelForXp = (totalXp) => {
  if (totalXp < 500) return 1
  return Math.floor(totalXp / 500) + 1
}

/** XP required to advance from the current level to the next. */
export const xpToNextLevel = (level) => Math.max(1, level) * 500

/** Progress (0..1) toward the next level. 1.0 when already at the cap. */
export const xpProgress = (totalXp, level) => {
  const earned = totalXp - (Math.max(1, level) - 1) * 500
  return Math.min(1, Math.max(0, earned / 500))
}

/* ------------------------------ formatters ------------------------------ */

/** Compact numeric formatter for stat labels (e.g. 127 -> "127"). */
export const fmtInt = (n, locale = 'en-US') => Math.round(Number(n) || 0).toLocaleString(locale)

/** Present positive nets in green, negative in crimson, zero neutral. */
export const fmtNet = (net, locale = 'en-US') => {
  const rounded = Math.round(net * 100) / 100
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: rounded === 0 ? 1 : 2,
    maximumFractionDigits: 2,
  }).format(rounded)
}

/** Format a whole number of minutes with leading zero padding. */
export const fmtDuration = (minutes, seconds) => {
  const m = Math.max(0, Math.floor(minutes))
  const s = Math.max(0, Math.floor(seconds || 0))
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

/** Human-readable subject/emoji tag for a subject string. */
export const subjectLabel = (subject, fallback = 'Unlabelled') =>
  (subject || fallback).slice(0, 24)
