import { useEffect, useState } from 'react'
import { Radar, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts'
import { Activity } from 'lucide-react'
import { Panel, Header } from '../components/ui.jsx'

const AXES = ['Speed', 'Focus', 'Precision', 'Stamina']

/**
 * Recharts spider/radar chart for the four performance axes. Renders an outer
 * faint grid ring plus a thin accent sector so the panel reads as "cosmic"
 * without extra chrome.
 */
export default function RadarChart({ radar }) {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    // Recharts SVG geometry needs the browser layout engine.
    requestAnimationFrame(() => setReady(true))
  }, [])

  if (!radar)
    return (
      <Panel>
        <Empty>No radar data yet</Empty>
      </Panel>
    )

  const data = AXES.map((axis, i) => ({
    axis,
    value: radar[axis.toLowerCase()] ?? 50,
    fullMark: 100,
  }))

  return (
    <Panel>
      <Header icon={Activity} title="Performance Radar" />
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} cx="50%" cy="50%" outerRadius={90}>
            <PolarAngleAxis
              type="number"
              dataKey="axis"
              tick={{ fill: '#a1a1aa', fontSize: 12 }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={false}
              axisLine={false}
            />
            {/* Faint concentric grid ring. */}
            <Radar
              name="Performance"
              dataKey="value"
              stroke="#818cf8"
              strokeOpacity={0.3}
              polygon={{ fill: '#818cf8', fillOpacity: 0.12 }}
            />
            {/* Primary performance layer. */}
            <Radar
              name="Actual"
              dataKey="value"
              stroke="#22d3ee"
              strokeWidth={2}
              polygon={{ fill: '#22d3ee', fillOpacity: 0.35 }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={{ fill: '#52525b', fontSize: 10 }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <Legend />
    </Panel>
  )
}
