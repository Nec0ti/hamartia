import { useEffect, useState } from 'react'
import { Radar, RadarChart as RechartsRadarChart, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts'
import { Activity } from 'lucide-react'
import { Panel, Header } from '../components/ui.jsx'
import { useI18n } from '../i18n.jsx'

const AXES = [['speed', 'dashboard.axis.speed'], ['focus', 'dashboard.axis.focus'], ['precision', 'dashboard.axis.precision'], ['stamina', 'dashboard.axis.stamina']]

/** Recharts spider/radar chart for the four performance axes. */
export default function RadarChart({ radar }) {
  const { t } = useI18n()
  const [ready, setReady] = useState(false)

  useEffect(() => {
    // Recharts SVG geometry needs the browser layout engine.
    requestAnimationFrame(() => setReady(true))
  }, [])

  if (!radar)
    return (
      <Panel>
        <div className="flex items-center justify-center h-48 text-zinc-500 text-xs">
          {t('dashboard.noPerformanceData')}
        </div>
      </Panel>
    )

  const data = AXES.map(([key, axisKey]) => ({
    axis: t(axisKey),
    value: radar[key] ?? 50,
    fullMark: 100,
  }))

  return (
    <Panel>
      <Header icon={Activity} title={t('dashboard.performanceRadar')} />
      <div role="img" aria-label={t('dashboard.radarDescription')} className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <RechartsRadarChart data={data} cx="50%" cy="50%" outerRadius={90}>
            <PolarAngleAxis
              dataKey="axis"
              tick={{ fill: '#a1a1aa', fontSize: 12 }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={{ fill: '#52525b', fontSize: 10 }}
              axisLine={false}
            />
            <Radar
              name={t('dashboard.chartActual')}
              dataKey="value"
              stroke="#fb7185"
              strokeWidth={2.5}
              fill="#fb7185"
              fillOpacity={0.2}
              dot={{ r: 3, fill: '#fb7185', stroke: '#18181b', strokeWidth: 1.5 }}
              activeDot={{ r: 5 }}
            />
          </RechartsRadarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  )
}
