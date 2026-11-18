import { useMemo } from 'react'
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
  ReferenceLine,
} from 'recharts'
import { TrendingUp } from 'lucide-react'
import { Panel, Header, Toggle, SubjectSelect, Empty } from '../components/ui.jsx'
import { fmtDate, fmtNet } from '../utils/formatters'
import { examChartLabel, examNetChanges, examResultsForSubject } from '../utils/examSections.js'
import { useI18n } from '../i18n.jsx'
import ExamChartDataTable from './ExamChartDataTable.jsx'

/**
 * Recharts net-score trend chart with a bar/line toggle and a subject filter.
 * The filter narrows the series to a single subject; zero and negative nets
 * remain visible so the chart reflects every recorded result.
 */
export default function TrendChart({ data, toggle, subjectFilter, subjects, onToggle, onFilter }) {
  const { t, locale } = useI18n()

  const series = useMemo(() => {
    return examNetChanges(examResultsForSubject(data, subjectFilter)).map((exam) => ({
      ...exam,
      chart_label: examChartLabel(exam, fmtDate(exam.date, locale, { month: 'numeric', day: 'numeric' }), t),
    }))
  }, [data, subjectFilter, locale, t])

  const chart =
    toggle === 'line' ? (
      <LineChart data={series}>
        <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
        <ReferenceLine y={0} stroke="#71717a" />
        <XAxis dataKey="chart_label" tick={{ fill: '#a1a1aa', fontSize: 11 }} />
        <YAxis tick={{ fill: '#a1a1aa', fontSize: 11 }} domain={[-2, 'auto']} width={34} />
        <Tooltip
          contentStyle={{
            background: '#18181b',
            border: '1px solid #27272a',
            borderRadius: '8px',
            color: '#d4d4d8',
            fontSize: '12px',
          }}
          labelFormatter={(label, payload) => payload?.[0]?.payload?.subject ? `${label} · ${payload[0].payload.subject}` : label}
          formatter={(v) => [fmtNet(v, locale), t('exams.net')]}
        />
        <Line type="monotone" dataKey="net" stroke="#fb7185" strokeWidth={3} dot={{ fill: '#fb7185', stroke: '#18181b', strokeWidth: 2, r: 4 }} activeDot={{ r: 6 }} />
      </LineChart>
    ) : (
      <BarChart data={series}>
        <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
        <ReferenceLine y={0} stroke="#71717a" />
        <XAxis dataKey="chart_label" tick={{ fill: '#a1a1aa', fontSize: 11 }} />
        <YAxis tick={{ fill: '#a1a1aa', fontSize: 11 }} domain={[-2, 'auto']} width={34} />
        <Tooltip
          contentStyle={{
            background: '#18181b',
            border: '1px solid #27272a',
            borderRadius: '8px',
            color: '#d4d4d8',
            fontSize: '12px',
          }}
          labelFormatter={(label, payload) => payload?.[0]?.payload?.subject ? `${label} · ${payload[0].payload.subject}` : label}
          formatter={(v) => [fmtNet(v, locale), t('exams.net')]}
        />
        <Bar dataKey="net" fill="#fb7185" radius={[4, 4, 0, 0]} />
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
      {series.length ? <div role="img" aria-label={`${t('dashboard.netTrend')} · ${subjectFilter === 'all' ? t('common.allSubjects') : subjectFilter}`} aria-describedby="exam-net-trend-data" className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          {chart}
        </ResponsiveContainer>
      </div> : <div className="h-72"><Empty>{t('dashboard.noNetTrend')}</Empty></div>}
      {series.length > 0 && <ExamChartDataTable id="exam-net-trend-data" title="dashboard.netTrend" data={series} locale={locale} t={t} />}
    </Panel>
  )
}
