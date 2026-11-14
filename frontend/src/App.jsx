import { useCallback, useEffect, useMemo, useState } from 'react'
import Navbar from './components/Navbar.jsx'
import DashboardTab from './tabs/DashboardTab.jsx'
import QuestionsTab from './tabs/QuestionsTab.jsx'
import StudyPlanTab from './tabs/StudyPlanTab.jsx'
import ComingSoon from './tabs/ComingSoon.jsx'
import SettingsModal from './components/SettingsModal.jsx'
import api from './services/api'
import { handleApiError } from './services/api'

/**
 * App root. Owns the active-tab selection and renders the shared Navbar above
 * the selected tab panel. Only the Dashboard is fully built in Phase 5; the
 * other tabs surface a placeholder that is fleshed out in later phases.
 *
 * The Settings modal is rendered as a sibling portal so it never collapses the
 * Navbar — the Navbar must keep rendering regardless of the modal state.
 */
export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [questionSubject, setQuestionSubject] = useState('')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settings, setSettings] = useState(null)
  const [settingsError, setSettingsError] = useState(null)

  const loadSettings = useCallback(async () => {
    setSettingsError(null)
    try {
      const data = await api.settings.get()
      setSettings(data)
    } catch (e) {
      setSettingsError(handleApiError(e).detail)
    }
  }, [])

  useEffect(() => {
    loadSettings()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const saveSettings = useCallback(async (draft) => {
    setSettingsError(null)
    try {
      const saved = await api.settings.update(draft)
      setSettings(saved)
    } catch (e) {
      setSettingsError(handleApiError(e).detail)
      throw e
    }
  }, [])

  const panel = useMemo(() => {
    if (activeTab === 'dashboard') return <DashboardTab onUploadQuestion={(exam) => {
      setQuestionSubject(exam.subject)
      setActiveTab('questions')
    }} />
    if (activeTab === 'questions') return <QuestionsTab initialSubject={questionSubject} />
    if (activeTab === 'studyplan') return <StudyPlanTab />
    return <ComingSoon />
  }, [activeTab, questionSubject])

  return (
    <div className="flex h-full flex-col">
      <Navbar
        activeTab={activeTab}
        onSelectTab={(tab) => {
          if (tab !== 'questions') setQuestionSubject('')
          setActiveTab(tab)
        }}
        onOpenSettings={() => {
          setSettingsOpen(true)
        }}
      />
      <main className="min-h-[calc(100vh-57px)] flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        {panel}
      </main>
      <SettingsModal
        open={settingsOpen}
        settings={settings}
        onSave={saveSettings}
        onClose={() => setSettingsOpen(false)}
        loadError={settingsError}
      />
    </div>
  )
}
