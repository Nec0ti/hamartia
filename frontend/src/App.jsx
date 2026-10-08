import { useCallback, useEffect, useMemo, useState } from 'react'
import Navbar from './components/Navbar.jsx'
import DashboardTab from './tabs/DashboardTab.jsx'
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
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settings, setSettings] = useState(null)
  const [settingsLoaded, setSettingsLoaded] = useState(false)
  const [settingsError, setSettingsError] = useState(null)
  const [settingsSaved, setSettingsSaved] = useState(false)

  const loadSettings = useCallback(async () => {
    setSettingsLoaded(true)
    setSettingsError(null)
    try {
      const data = await api.settings.get()
      setSettings(data)
      setSettingsSaved(false)
    } catch (e) {
      setSettingsError(handleApiError(e).detail)
    }
  }, [])

  useEffect(() => {
    loadSettings()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const saveSettings = useCallback(async (draft) => {
    setSettingsSaved(true)
    setSettingsError(null)
    try {
      const saved = await api.settings.update(draft)
      setSettings(saved)
      setSettingsSaved(false)
    } catch (e) {
      setSettingsError(handleApiError(e).detail)
    }
  }, [])

  const panel = useMemo(() => {
    if (activeTab === 'dashboard') return <DashboardTab />
    return <ComingSoon />
  }, [activeTab])

  return (
    <div className="flex h-full flex-col">
      <Navbar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onOpenSettings={() => {
          setSettingsOpen(true)
          setSettingsSaved(false)
          setSettingsError(null)
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
      />
    </div>
  )
}
