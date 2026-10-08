import { useEffect, useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import api from '../services/api'
import { handleApiError } from '../services/api'
import {
  fmtInt,
  fmtNet,
  netScore,
  previewXp,
  levelForXp,
} from '../utils/formatters'
import StatsCards from './StatsCards.jsx'
import RadarChart from './RadarChart.jsx'
import TrendChart from './TrendChart.jsx'
import RecentExams from './RecentExams.jsx'
import AddExamModal from './AddExamModal.jsx'

const EMPTY_FORM = {
  date: '2026-10-07',
  subject: 'Math',
  duration_minutes: 30,
  duration_seconds: 0,
  correct: 10,
  incorrect: 2,
  blank: 1,
}

/**
 * Tab 1: Dashboard. Aggregates exam history into stat cards, a radar chart of
 * the four performance axes, a net-score trend (bar/line toggle + subject
 * filter), and a recent-exams table. Double-clicking an Incorrect cell opens
 * the question-upload modal.
 */
export default function DashboardTab({ onUploadQuestion }) {
  const [exams, setExams] = useState([])
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)

  const [toggle, setToggle] = useState('bar') // 'bar' | 'line'
  const [subjectFilter, setSubjectFilter] = useState('all')
  const [recentError, setRecentError] = useState(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [ex, prof] = await Promise.all([api.exams.list(), api.user.get()])
      setExams(ex)
      setProfile({
        level: prof.level ?? levelForXp(prof.total_xp ?? 0),
        radar: prof.radar_stats ?? { speed: 50, focus: 50, precision: 50, stamina: 50 },
      })
    } catch (e) {
      setError(handleApiError(e).detail)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const subjects = useMemo(
    () => Array.from(new Set(exams.map((e) => e.subject).filter(Boolean))).sort(),
    [exams],
  )

  const filtered = useMemo(() => {
    if (subjectFilter === 'all') return exams
    return exams.filter((e) => e.subject === subjectFilter)
  }, [exams, subjectFilter])

  const stats = useMemo(() => {
    const total = exams.length
    const answered = exams.filter((e) => e.correct + e.incorrect > 0)
    const avgNet =
      answered.length > 0
        ? answered.reduce((s, e) => s + e.net, 0) / answered.length
        : 0
    return { total, avgNet }
  }, [exams])

  const submitExam = (e) => {
    e.preventDefault()
    setRecentError(null)
    api
      .exams.create({ ...form, created_at: '' })
      .then(load)
      .then(() => {
        setShowAdd(false)
        setForm(EMPTY_FORM)
      })
      .catch((err) => {
        setRecentError(handleApiError(err).detail)
      })
  }

  if (loading)
    return (
      <div className="px-6 py-24 text-center text-canvas-muted">
        Loading dashboard…
      </div>
    )

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-canvas-text">
          Dashboard
        </h1>
        <button
          type="button"
          onClick={() => setShowAdd(true)}
          className="inline-flex items-center gap-2 rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-white shadow-crimson transition hover:opacity-90"
        >
          <Plus size={16} />
          Add Exam
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-canvas-line bg-canvas-base p-3 text-sm text-canvas-muted">
          {error}
        </div>
      )}

      <StatsCards profile={profile} stats={stats} />

      <div className="grid gap-6 lg:grid-cols-2">
        <RadarChart radar={profile?.radar} />
        <TrendChart data={filtered} toggle={toggle} subjectFilter={subjectFilter} subjects={subjects} onToggle={setToggle} onFilter={setSubjectFilter} />
      </div>

      <RecentExams
        exams={filtered}
        onDoubleClickIncorrect={(q) => {
          onUploadQuestion(q)
        }}
        recentError={recentError}
        setRecentError={setRecentError}
      />

      {/* Add Exam modal. */}
      <AddExamModal
        open={showAdd}
        form={form}
        setForm={setForm}
        onClose={() => {
          setShowAdd(false)
          setForm(EMPTY_FORM)
        }}
        onSubmit={submitExam}
      />
    </div>
  )
}
