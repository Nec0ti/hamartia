import { useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Activity } from 'lucide-react'
import { Empty, Header, Panel } from '../components/ui.jsx'
import { useI18n } from '../i18n.jsx'
import { fmtDate, fmtNet } from '../utils/formatters'
import { examChartLabel, examNetChanges, examResultsForSubject } from '../utils/examSections.js'
import ExamChartDataTable from './ExamChartDataTable.jsx'

export default function NetChangeChart({ data, subjectFilter }) {
  const { t, locale } = useI18n()
  const series = useMemo(() => examNetChanges(examResultsForSubject(data, subjectFilter)).map((exam) => ({
    ...exam,
    chart_label: examChartLabel(exam, fmtDate(exam.date, locale, { month: 'numeric', day: 'numeric' }), t),
  })), [data, subjectFilter, locale, t])
  const changes = series.filter((item) => item.change != null)

  return <Panel>
    <Header icon={Activity} title={t('dashboard.netChange')} subtitle={t('dashboard.netChangeSubtitle')} />
    {changes.length ? <div role="img" aria-label={`${t('dashboard.netChange')} · ${subjectFilter === 'all' ? t('common.allSubjects') : subjectFilter}`} aria-describedby="exam-net-change-data" className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
          <ReferenceLine y={0} stroke="#a1a1aa" strokeWidth={1.5} />
          <XAxis dataKey="chart_label" tick={{ fill: '#a1a1aa', fontSize: 11 }} />
          <YAxis tick={{ fill: '#a1a1aa', fontSize: 11 }} width={38} />
          <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #3f3f46', borderRadius: '8px', color: '#e4e4e7', fontSize: '12px' }}
            labelFormatter={(label, payload) => payload?.[0]?.payload?.subject ? `${label} · ${payload[0].payload.subject}` : label}
            formatter={(value) => [fmtNet(value, locale), t('dashboard.netChange')]} />
          <Bar dataKey="change" radius={[4, 4, 0, 0]}>
            {series.map((item) => <Cell key={item.id} fill={item.change >= 0 ? '#34d399' : '#fb7185'} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div> : <div className="h-64"><Empty>{series.length ? t('dashboard.netChangeNeedsHistory') : t('dashboard.noNetTrend')}</Empty></div>}
    {series.length > 0 && <ExamChartDataTable id="exam-net-change-data" title="dashboard.netChange" data={series} locale={locale} t={t} />}
  </Panel>
}
