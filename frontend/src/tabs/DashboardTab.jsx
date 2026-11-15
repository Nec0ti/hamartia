import { useEffect, useMemo, useState } from 'react'
import { Plus, SlidersHorizontal } from 'lucide-react'
import api from '../services/api'
import { handleApiError } from '../services/api'
import {
  fmtInt,
  fmtNet,
  levelForXp,
} from '../utils/formatters'
import StatsCards from './StatsCards.jsx'
import RadarChart from './RadarChart.jsx'
import TrendChart from './TrendChart.jsx'
import RecentExams from './RecentExams.jsx'
import AddExamModal from './AddExamModal.jsx'
import ExamProfileManager from './ExamProfileManager.jsx'
import { examPayloadFromForm, examResultsForSubject, examScoringProfileKey, examSubjectOptions, filterExamsByScoringProfile } from '../utils/examSections.js'
import { useI18n } from '../i18n.jsx'

const EMPTY_FORM = {
  date: new Date().toLocaleDateString('en-CA'),
  exam_type: 'branch',
  subject: '',
  duration_minutes: 30,
  duration_seconds: 0,
  correct: 10,
  incorrect: 2,
  blank: 1,
  sections: [],
  scoring_profile_id: 'legacy-yks',
  scoring_profile_version: 1,
}

/**
 * Tab 1: Dashboard. Aggregates exam history into stat cards, a radar chart of
 * the four performance axes, a net-score trend (bar/line toggle + subject
 * filter), and a recent-exams table. Double-clicking an Incorrect cell opens
 * the question-upload modal.
 */
export default function DashboardTab({ onUploadQuestion }) {
  const { t } = useI18n()
  const [exams, setExams] = useState([])
  const [scoringProfiles, setScoringProfiles] = useState([])
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [showAdd, setShowAdd] = useState(false)
  const [showProfileManager, setShowProfileManager] = useState(false)
  const [form, setForm] = useState(() => ({ ...EMPTY_FORM, subject: t('exams.defaultSubject') }))
  const [editingExam, setEditingExam] = useState(null)

  const [toggle, setToggle] = useState('bar') // 'bar' | 'line'
  const [subjectFilter, setSubjectFilter] = useState('all')
  const [examTypeFilter, setExamTypeFilter] = useState('all')
  const [scoringProfileFilter, setScoringProfileFilter] = useState('legacy-yks@1')
  const [recentError, setRecentError] = useState(null)

  const blankExamForm = (subject = t('exams.defaultSubject')) => {
    const [scoring_profile_id, version] = scoringProfileFilter.split('@')
    return { ...EMPTY_FORM, subject, scoring_profile_id, scoring_profile_version: Number(version) || 1 }
  }

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [ex, prof, profiles] = await Promise.all([api.exams.list(), api.user.get(), api.examProfiles.list()])
      setExams(ex)
      setScoringProfiles(profiles)
      setProfile({
        level: prof.level ?? levelForXp(prof.total_xp ?? 0),
        totalXp: prof.total_xp ?? 0,
        streakDays: prof.streak_days ?? 0,
        radar: prof.radar_stats ?? { speed: 50, focus: 50, precision: 50, stamina: 50 },
      })
    } catch (e) {
      setError(handleApiError(e, t).detail)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const availableProfiles = useMemo(() => {
    const byKey = new Map()
    for (const item of [...scoringProfiles, ...exams.map((exam) => exam.scoring_profile).filter(Boolean)]) {
      byKey.set(examScoringProfileKey(item), item)
    }
    if (!byKey.has('legacy-yks@1')) byKey.set('legacy-yks@1', { profile_id: 'legacy-yks', version: 1, display_name: 'YKS (legacy)', country_label: 'Türkiye' })
    return [...byKey.values()].sort((a, b) => a.display_name.localeCompare(b.display_name) || a.version - b.version)
  }, [scoringProfiles, exams])

  const profileExams = useMemo(
    () => filterExamsByScoringProfile(exams, scoringProfileFilter),
    [exams, scoringProfileFilter],
  )

  const subjects = useMemo(() => examSubjectOptions(profileExams), [profileExams])

  const filtered = useMemo(() => {
    return profileExams.filter(
      (exam) => (examTypeFilter === 'all' || (exam.exam_type || 'branch') === examTypeFilter)
        && (subjectFilter === 'all' || exam.subject === subjectFilter || exam.sections?.some((section) => section.subject === subjectFilter)),
    )
  }, [profileExams, examTypeFilter, subjectFilter])

  const stats = useMemo(() => {
    const total = filtered.length
    const results = examResultsForSubject(filtered, subjectFilter)
    const answered = results.filter((e) => e.correct + e.incorrect > 0)
    const avgNet =
      answered.length > 0
        ? answered.reduce((s, e) => s + e.net, 0) / answered.length
        : 0
    return { total, avgNet }
  }, [filtered, subjectFilter])

  const submitExam = (e) => {
    e.preventDefault()
    setRecentError(null)
    const payload = examPayloadFromForm(form)
    const save = editingExam ? api.exams.update(editingExam.id, payload) : api.exams.create(payload)
    save.then(load).then(() => {
      setShowAdd(false)
      setEditingExam(null)
      setForm(blankExamForm())
    }).catch((err) => setRecentError(handleApiError(err, t).detail))
  }

  const editExam = (exam) => {
    setEditingExam(exam)
    setForm({
      date: exam.date,
      exam_type: exam.exam_type || 'branch',
      scoring_profile_id: exam.scoring_profile?.profile_id || 'legacy-yks',
      scoring_profile_version: exam.scoring_profile?.version || 1,
      subject: exam.subject,
      duration_minutes: exam.duration_minutes,
      duration_seconds: exam.duration_seconds,
      correct: exam.correct,
      incorrect: exam.incorrect,
      blank: exam.blank,
      sections: exam.sections?.length ? exam.sections : exam.exam_type !== 'branch' ? [{
        subject: exam.subject, correct: exam.correct, incorrect: exam.incorrect, blank: exam.blank,
      }] : [],
    })
    setShowAdd(true)
  }

  const deleteExam = async (exam) => {
    if (!window.confirm(t('dashboard.deleteConfirm', { date: exam.date, subject: exam.subject }))) return
    setRecentError(null)
    try {
      await api.exams.remove(exam.id)
      await load()
    } catch (err) {
      setRecentError(handleApiError(err, t).detail)
    }
  }

  if (loading)
    return (
      <div className="px-6 py-24 text-center text-canvas-muted">
        {t('dashboard.loading')}
      </div>
    )

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-canvas-text">
          {t('dashboard.title')}
        </h1>
        <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setShowProfileManager(true)}
          className="inline-flex items-center gap-2 rounded-lg border border-canvas-line px-4 py-2 text-sm font-semibold text-canvas-text hover:bg-canvas-raise"
        >
          <SlidersHorizontal size={16} />
          {t('exams.profileManager')}
        </button>
        <button
          type="button"
          onClick={() => {
            setEditingExam(null)
            setForm(blankExamForm())
            setShowAdd(true)
          }}
          className="inline-flex items-center gap-2 rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-canvas-base shadow-crimson transition hover:opacity-90"
        >
          <Plus size={16} />
          {t('dashboard.addExam')}
        </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-canvas-line bg-canvas-base p-3 text-sm text-canvas-muted">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="scoring-profile-filter" className="text-xs text-canvas-muted">{t('dashboard.scoringProfile')}</label>
        <select id="scoring-profile-filter" aria-label={t('dashboard.scoringProfileFilter')} value={scoringProfileFilter} onChange={(event) => setScoringProfileFilter(event.target.value)} className="rounded-lg border border-canvas-line bg-canvas-base px-3 py-1.5 text-xs text-canvas-text">
          {availableProfiles.map((item) => <option key={examScoringProfileKey(item)} value={examScoringProfileKey(item)}>
            {item.display_name} · {item.country_label} · v{item.version}
          </option>)}
        </select>
        <label htmlFor="exam-type-filter" className="text-xs text-canvas-muted">{t('dashboard.examType')}</label>
        <select
          id="exam-type-filter"
          aria-label={t('dashboard.examTypeFilter')}
          value={examTypeFilter}
          onChange={(e) => setExamTypeFilter(e.target.value)}
          className="rounded-lg border border-canvas-line bg-canvas-base px-3 py-1.5 text-xs text-canvas-text"
        >
          <option value="all">{t('dashboard.allTypes')}</option>
          <option value="tyt">TYT</option>
          <option value="ayt">AYT</option>
          <option value="branch">{t('dashboard.branch')}</option>
        </select>
      </div>
      <StatsCards profile={profile} stats={stats} examType={examTypeFilter} />

      <div className="grid gap-6 lg:grid-cols-2">
        <RadarChart radar={profile?.radar} />
        <TrendChart data={filtered} toggle={toggle} subjectFilter={subjectFilter} subjects={subjects} onToggle={setToggle} onFilter={setSubjectFilter} />
      </div>

      <RecentExams
        exams={filtered}
        onDoubleClickIncorrect={(q) => {
          onUploadQuestion(q)
        }}
        onEdit={editExam}
        onDelete={deleteExam}
        recentError={recentError}
      />

      {/* Add Exam modal. */}
      <AddExamModal
        open={showAdd}
        form={form}
        setForm={setForm}
        onClose={() => {
          setShowAdd(false)
          setEditingExam(null)
          setForm(blankExamForm())
        }}
        onSubmit={submitExam}
        editing={Boolean(editingExam)}
        profiles={availableProfiles}
      />
      <ExamProfileManager open={showProfileManager} profiles={availableProfiles} onClose={() => setShowProfileManager(false)} onSaved={async () => setScoringProfiles(await api.examProfiles.list())} />
    </div>
  )
}
