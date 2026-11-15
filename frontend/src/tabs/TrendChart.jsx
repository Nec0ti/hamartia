import { useMemo, useState } from 'react'
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { TrendingUp } from 'lucide-react'
import { Panel, Header, Toggle, SubjectSelect } from '../components/ui.jsx'
import { fmtDate, fmtNet } from '../utils/formatters'
import { examResultsForSubject } from '../utils/examSections.js'
import { useI18n } from '../i18n.jsx'

/**
 * Recharts net-score trend chart with a bar/line toggle and a subject filter.
 * Only exams with a positive net are shown by default to keep the trend
 * meaningful; the filter narrows the series to a single subject.
 */
export default function TrendChart({ data, toggle, subjectFilter, subjects, onToggle, onFilter }) {
  const { t, locale } = useI18n()
  const [hover, setHover] = useState(null)

  const formatDate = (date) => fmtDate(date, locale, { month: 'numeric', day: 'numeric' })

  const series = useMemo(() => {
    return examResultsForSubject(data, subjectFilter).filter((exam) => exam.net > 0)
  }, [data, subjectFilter])

  const chart =
    toggle === 'line' ? (
      <LineChart data={series} onMouseMove={setHover} onMouseLeave={() => setHover(null)}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
        <XAxis dataKey="date" tick={{ fill: '#a1a1aa', fontSize: 11 }} tickFormatter={formatDate} />
        <YAxis tick={{ fill: '#a1a1aa', fontSize: 11 }} domain={[-2, 'auto']} width={34} />
        <Tooltip
          contentStyle={{
            background: '#18181b',
            border: '1px solid #27272a',
            borderRadius: '8px',
            color: '#d4d4d8',
            fontSize: '12px',
          }}
          formatter={(v) => [fmtNet(v, locale), t('exams.net')]}
        />
        <Line type="monotone" dataKey="net" stroke="#d4d4d8" strokeWidth={2} dot={{ fill: '#d4d4d8', r: 4 }} activeDot={{ r: 6 }} />
      </LineChart>
    ) : (
      <BarChart data={series}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
        <XAxis dataKey="date" tick={{ fill: '#a1a1aa', fontSize: 11 }} tickFormatter={formatDate} />
        <YAxis tick={{ fill: '#a1a1aa', fontSize: 11 }} domain={[-2, 'auto']} width={34} />
        <Tooltip
          contentStyle={{
            background: '#18181b',
            border: '1px solid #27272a',
            borderRadius: '8px',
            color: '#d4d4d8',
            fontSize: '12px',
          }}
          formatter={(v) => [fmtNet(v, locale), t('exams.net')]}
        />
        <Bar dataKey="net" fill="#d4d4d8" radius={[4, 4, 0, 0]} />
      </BarChart>
    )

  return (
    <Panel>
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <Header icon={TrendingUp} title={t('dashboard.netTrend')} />
        <div className="flex items-center gap-2">
          <SubjectSelect value={subjectFilter} options={['all', ...subjects]} onChange={onFilter} allLabel={t('common.allSubjects')} ariaLabel={t('dashboard.subjectFilter')} />
          <Toggle value={toggle} options={[{ value: 'bar', label: t('dashboard.bar') }, { value: 'line', label: t('dashboard.line') }]} onChange={onToggle} />
        </div>
      </div>
      <div role="img" aria-label={`${t('dashboard.netTrend')} · ${subjectFilter === 'all' ? t('common.allSubjects') : subjectFilter}`} className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          {chart}
        </ResponsiveContainer>
      </div>
      {hover && (
        <div className="mt-2 text-center text-xs text-canvas-muted">
          {formatDate(hover.date)} — {t('exams.net')} {fmtNet(hover.net, locale)}
        </div>
      )}
    </Panel>
  )
}
