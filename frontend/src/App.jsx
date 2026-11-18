import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Navbar from './components/Navbar.jsx'
import DashboardTab from './tabs/DashboardTab.jsx'
const QuestionsTab = lazy(() => import('./tabs/QuestionsTab.jsx'))
const StudyPlanTab = lazy(() => import('./tabs/StudyPlanTab.jsx'))
const StudyAgentTab = lazy(() => import('./tabs/StudyAgentTab.jsx'))
const CosmosTab = lazy(() => import('./tabs/CosmosTab.jsx'))
const ClockTab = lazy(() => import('./tabs/ClockTab.jsx'))
const ComingSoon = lazy(() => import('./tabs/ComingSoon.jsx'))
import SettingsModal from './components/SettingsModal.jsx'
import OnboardingModal from './components/OnboardingModal.jsx'
import StudentProfileModal from './components/StudentProfileModal.jsx'
import api from './services/api'
import { handleApiError } from './services/api'
import { useI18n } from './i18n.jsx'
import { ClockProvider } from './clock/ClockContext.jsx'
import { firstRunStage } from './studentProfile/profile.js'

/**
 * App root. Owns active-tab selection and renders the shared navigation above
 * the selected study workflow.
 *
 * The Settings modal is rendered as a sibling portal so it never collapses the
 * Navbar — the Navbar must keep rendering regardless of the modal state.
 */
function AppContent() {
  const { t } = useI18n()
  const [activeTab, setActiveTab] = useState('dashboard')
  const [questionExam, setQuestionExam] = useState(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [studentProfileOpen, setStudentProfileOpen] = useState(false)
  const [onboarding, setOnboarding] = useState(null)
  const onboardingRef = useRef(onboarding)
  onboardingRef.current = onboarding
  const [onboardingStage, setOnboardingStage] = useState(null)
  const [settings, setSettings] = useState(null)
  const [settingsLoading, setSettingsLoading] = useState(true)
  const [settingsError, setSettingsError] = useState(null)

  const loadSettings = useCallback(async () => {
    setSettingsLoading(true)
    setSettingsError(null)
    try {
      const data = await api.settings.get()
      setSettings(data)
    } catch (e) {
      setSettingsError(handleApiError(e, t).detail)
    } finally {
      setSettingsLoading(false)
    }
  }, [t])

  useEffect(() => {
    loadSettings()
  }, [loadSettings])

  useEffect(() => {
    let active = true
    api.studentProfile.get().then((data) => {
      if (!active) return
      setOnboarding(data)
      setOnboardingStage(firstRunStage(data))
    }).catch(() => {})
    return () => { active = false }
  }, [])

  const saveOnboarding = useCallback(async (draft) => {
    const saved = await api.studentProfile.save(draft)
    setOnboarding(saved)
    setOnboardingStage(saved.survey_completed ? null : saved.tutorial_completed || saved.tutorial_skipped ? 'survey' : 'tutorial')
    return saved
  }, [])

  const dismissOnboarding = useCallback(() => {
    const current = onboardingRef.current
    if (current) saveOnboarding({ ...current, tutorial_skipped: !current.tutorial_completed, survey_completed: true }).catch(() => {})
    setOnboardingStage(null)
  }, [saveOnboarding])

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

  const openSettings = useCallback(() => setSettingsOpen(true), [])

  const panel = useMemo(() => {
    if (activeTab === 'dashboard') return <DashboardTab onUploadQuestion={(exam) => {
      setQuestionExam(exam)
      setActiveTab('questions')
    }} />
    if (activeTab === 'questions') return <QuestionsTab initialExam={questionExam} />
    if (activeTab === 'studyplan') return <StudyPlanTab />
    if (activeTab === 'studyagent') return <StudyAgentTab settings={settings} settingsOpen={settingsOpen} onOpenSettings={openSettings} />
    if (activeTab === 'cosmos') return <CosmosTab />
    if (activeTab === 'clock') return <ClockTab />
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
        <Suspense fallback={<div role="status" aria-live="polite" className="px-6 py-24 text-center text-canvas-muted">{t('navigation.loadingTab')}</div>}>
          {panel}
        </Suspense>
      </main>
      <SettingsModal
        open={settingsOpen}
        settings={settings}
        loading={settingsLoading}
        onSave={saveSettings}
        onClose={() => setSettingsOpen(false)}
        onEditProfile={() => { setSettingsOpen(false); setStudentProfileOpen(true) }}
        onReplayTour={() => { setSettingsOpen(false); setOnboardingStage('tutorial') }}
        loadError={settingsError}
      />
      <StudentProfileModal
        open={studentProfileOpen}
        initial={onboarding}
        onClose={() => setStudentProfileOpen(false)}
        onSaved={setOnboarding}
        onRestartOnboarding={() => setOnboardingStage('language')}
      />
      <OnboardingModal
        stage={onboardingStage}
        onboarding={onboarding}
        onLanguage={() => {}}
        onSave={saveOnboarding}
        onDismiss={dismissOnboarding}
      />
    </div>
  )
}

export default function App() {
  return <ClockProvider><AppContent /></ClockProvider>
}
