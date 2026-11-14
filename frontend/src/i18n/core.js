import messages from './messages/index.js'

export { messages }

export const LANGUAGE_STORAGE_KEY = 'hamartia.language'
export const SUPPORTED_LANGUAGES = ['en', 'tr']

export function normalizeLanguage(value) {
  return SUPPORTED_LANGUAGES.includes(value) ? value : 'en'
}

export function getSavedLanguage(storage) {
  try {
    return normalizeLanguage((storage ?? globalThis.localStorage)?.getItem(LANGUAGE_STORAGE_KEY))
  } catch {
    return 'en'
  }
}

export function translate(key, language, values = {}) {
  let result = messages[key]?.[language] ?? messages[key]?.en ?? key
  for (const [name, value] of Object.entries(values)) result = result.replaceAll(`{{${name}}}`, String(value))
  return result
}
