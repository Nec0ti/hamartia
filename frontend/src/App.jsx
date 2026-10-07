import { useMemo, useState } from 'react'
import Navbar from './components/Navbar.jsx'
import DashboardTab from './tabs/DashboardTab.jsx'
import ComingSoon from './tabs/ComingSoon.jsx'

/**
 * App root. Owns the active-tab selection and renders the shared Navbar above
 * the selected tab panel. Only the Dashboard is fully built in Phase 5; the
 * other tabs surface a placeholder that is fleshed out in later phases.
 */
export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard')

  const panel = useMemo(() => {
    if (activeTab === 'dashboard') return <DashboardTab />
    return <ComingSoon />
  }, [activeTab])

  return (
    <div className="flex h-full flex-col">
      <Navbar activeTab={activeTab} onSelectTab={setActiveTab} />
      <main className="min-h-[calc(100vh-57px)] flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        {panel}
      </main>
    </div>
  )
}
