import { useCallback, useEffect, useMemo, useState } from 'react'
import Navbar from './components/Navbar.jsx'
import DashboardTab from './tabs/DashboardTab.jsx'
import QuestionsTab from './tabs/QuestionsTab.jsx'
import StudyPlanTab from './tabs/StudyPlanTab.jsx'
import StudyAgentTab from './tabs/StudyAgentTab.jsx'
import CosmosTab from './tabs/CosmosTab.jsx'
import ComingSoon from './tabs/ComingSoon.jsx'
import SettingsModal from './components/SettingsModal.jsx'
import api from './services/api'
import { handleApiError } from './services/api'
import { useI18n } from './i18n.jsx'

/**
 * App root. Owns active-tab selection and renders the shared navigation above
 * the selected study workflow.
 *
 * The Settings modal is rendered as a sibling portal so it never collapses the
 * Navbar — the Navbar must keep rendering regardless of the modal state.
 */
export default function App() {
  const { t } = useI18n()
  const [activeTab, setActiveTab] = useState('dashboard')
  const [questionExam, setQuestionExam] = useState(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settings, setSettings] = useState(null)
  const [settingsError, setSettingsError] = useState(null)

  const loadSettings = useCallback(async () => {
    setSettingsError(null)
    try {
      const data = await api.settings.get()
      setSettings(data)
    } catch (e) {
      setSettingsError(handleApiError(e, t).detail)
    }
  }, [t])

  useEffect(() => {
    loadSettings()
  }, [loadSettings])

  const saveSettings = useCallback(async (draft) => {
    setSettingsError(null)
    try {
      const saved = await api.settings.update(draft)
      setSettings(saved)
    } catch (e) {
      setSettingsError(handleApiError(e, t).detail)
      throw e
    }
  }, [t])

  const openSettings = useCallback(() => {
    setSettingsOpen(true)
    loadSettings()
  }, [loadSettings])

  const panel = useMemo(() => {
    if (activeTab === 'dashboard') return <DashboardTab onUploadQuestion={(exam) => {
      setQuestionExam(exam)
      setActiveTab('questions')
    }} />
    if (activeTab === 'questions') return <QuestionsTab initialExam={questionExam} />
    if (activeTab === 'studyplan') return <StudyPlanTab />
    if (activeTab === 'studyagent') return <StudyAgentTab settings={settings} settingsOpen={settingsOpen} onOpenSettings={openSettings} />
    if (activeTab === 'cosmos') return <CosmosTab />
    return <ComingSoon tabId={activeTab} />
  }, [activeTab, questionExam, settings, settingsOpen, openSettings])

  return (
    <div className="flex h-full flex-col">
      <Navbar
        activeTab={activeTab}
        onSelectTab={(tab) => {
          if (tab !== 'questions') setQuestionExam(null)
          setActiveTab(tab)
        }}
        onOpenSettings={openSettings}
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
