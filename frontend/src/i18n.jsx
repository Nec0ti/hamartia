import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { getSavedLanguage, LANGUAGE_STORAGE_KEY, normalizeLanguage, translate } from './i18n/core.js'

const I18nContext = createContext(null)

export function I18nProvider({ children }) {
  const [language, setLanguage] = useState(getSavedLanguage)

  useEffect(() => {
    document.documentElement.lang = language
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, language)
    } catch {}
  }, [language])

  const value = useMemo(() => ({
    language,
    setLanguage: (value) => setLanguage(normalizeLanguage(value)),
    t: (key, values) => translate(key, language, values),
    locale: language === 'tr' ? 'tr-TR' : 'en-US',
  }), [language])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) throw new Error('useI18n must be used within I18nProvider')
  return context
}
