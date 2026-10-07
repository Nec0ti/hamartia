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
  Cell,
} from 'recharts'
import { TrendingUp } from 'lucide-react'
import { Panel, Header, Toggle, SubjectSelect } from '../components/ui.jsx'
import { fmtNet } from '../utils/formatters'

/**
 * Recharts net-score trend chart with a bar/line toggle and a subject filter.
 * Only exams with a positive net are shown by default to keep the trend
 * meaningful; the filter narrows the series to a single subject.
 */
export default function TrendChart({ data, toggle, subjectFilter, subjects, onToggle, onFilter }) {
  const [hover, setHover] = useState(null)

  const series = useMemo(() => {
    if (subjectFilter !== 'all') {
      return data.filter((e) => e.net > 0 && e.subject === subjectFilter)
    }
    return data.filter((e) => e.net > 0)
  }, [data, subjectFilter])

  const chart =
    toggle === 'line' ? (
      <LineChart data={series} onMouseMove={setHover} onMouseLeave={() => setHover(null)}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
        <XAxis dataKey="date" tick={{ fill: '#a1a1aa', fontSize: 11 }} tickFormatter={(d) => d.slice(5)} />
        <YAxis tick={{ fill: '#a1a1aa', fontSize: 11 }} domain={[-2, 'auto']} width={34} />
        <Tooltip
          contentStyle={{
            background: '#18181b',
            border: '1px solid #27272a',
            borderRadius: '8px',
            color: '#d4d4d8',
            fontSize: '12px',
          }}
          formatter={(v) => [fmtNet(v), 'Net']}
        />
        <Line type="monotone" dataKey="net" stroke="#10b981" strokeWidth={2} dot={{ fill: '#10b981', r: 4 }} activeDot={{ r: 6 }} />
      </LineChart>
    ) : (
      <BarChart data={series}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
        <XAxis dataKey="date" tick={{ fill: '#a1a1aa', fontSize: 11 }} tickFormatter={(d) => d.slice(5)} />
        <YAxis tick={{ fill: '#a1a1aa', fontSize: 11 }} domain={[-2, 'auto']} width={34} />
        <Tooltip
          contentStyle={{
            background: '#18181b',
            border: '1px solid #27272a',
            borderRadius: '8px',
            color: '#d4d4d8',
            fontSize: '12px',
          }}
          formatter={(v) => [fmtNet(v), 'Net']}
        />
        <Bar dataKey="net" radius={[4, 4, 0, 0]}>
          {series.map((entry, i) => (
            <Cell key={i} fill={entry.net >= 0 ? '#10b981' : '#ef4444'} />
          ))}
        </Bar>
      </BarChart>
    )

  return (
    <Panel>
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <Header icon={TrendingUp} title="Net Score Trend" />
        <div className="flex items-center gap-2">
          <SubjectSelect value={subjectFilter} options={['all', ...subjects]} onChange={onFilter} />
          <Toggle value={toggle} options={[{ value: 'bar', label: 'Bar' }, { value: 'line', label: 'Line' }]} onChange={onToggle} />
        </div>
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          {chart}
        </ResponsiveContainer>
      </div>
      {hover && (
        <div className="mt-2 text-center text-xs text-canvas-muted">
          {hover.date.slice(5)} — net {fmtNet(hover.net)}
        </div>
      )}
    </Panel>
  )
}
