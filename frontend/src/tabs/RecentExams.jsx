import { useMemo } from 'react'
import { ArrowUpRight, ArrowDownRight, Clock } from 'lucide-react'
import { Panel, Header } from '../components/ui.jsx'
import { fmtInt, fmtNet, fmtDuration, subjectLabel } from '../utils/formatters'

/**
 * Recent-exams table. Each row shows the derived net and XP. Double-clicking
 * the Incorrect cell (or the row) opens the question-upload modal, matching the
 * "double-click Incorrect to upload" behaviour from the spec.
 */
export default function RecentExams({ exams, onDoubleClickIncorrect, recentError, setRecentError }) {
  const recent = useMemo(() => exams.slice().sort((a, b) => (b.date < a.date ? 1 : -1)).slice(0, 8), [exams])

  if (recent.length === 0) {
    return (
      <Panel>
        <Header title="Recent Exams" />
        <p className="py-10 text-center text-sm text-canvas-muted">
          No exams logged yet. Click &quot;Add Exam&quot; to record your first run.
        </p>
      </Panel>
    )
  }

  return (
    <Panel>
      <Header title="Recent Exams" />
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-canvas-line text-xs uppercase tracking-wider text-canvas-muted">
              <th className="py-3 pr-4">Date</th>
              <th className="py-3 pr-4">Subject</th>
              <th className="py-3 pr-4">Correct</th>
              <th className="py-3 pr-4">Incorrect</th>
              <th className="py-3 pr-4">Blank</th>
              <th className="py-3 pr-4">Duration</th>
              <th className="py-3 pr-4 text-right">Net</th>
              <th className="py-3 pr-4 text-right">XP</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((ex) => {
              const net = ex.net
              const xp = ex.xp
              const handleRow = (e) => {
                if ((e.button === 0 && e.detail === 2) || e.ctrlKey) {
                  onDoubleClickIncorrect(ex)
                }
              }
              return (
                <tr
                  key={ex.id}
                  onDoubleClick={() => onDoubleClickIncorrect(ex)}
                  className="cursor-pointer transition hover:bg-canvas-raise/50"
                >
                  <td className="py-3 pr-4 text-canvas-text">{ex.date}</td>
                  <td className="py-3 pr-4 text-canvas-text">{subjectLabel(ex.subject)}</td>
                  <td className="py-3 pr-4 text-emerald-400">{fmtInt(ex.correct)}</td>
                  <td
                    className="py-3 pr-4 text-accent font-semibold transition hover:underline"
                    title="Double-click to upload a question for analysis"
                  >
                      <span className="inline-flex items-center gap-1">
                        {fmtInt(ex.incorrect)}
                        {net < 0 && <ArrowDownRight size={12} />}
                      </span>
                    </td>
                  <td className="py-3 pr-4 text-canvas-muted">{fmtInt(ex.blank)}</td>
                  <td className="py-3 pr-4 text-canvas-muted">
                    <span className="inline-flex items-center gap-1">
                      <Clock size={12} />
                      {fmtDuration(ex.duration_minutes, ex.duration_seconds)}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-right">
                    <span
                      className={[
                        'font-semibold',
                        net > 0 ? 'text-emerald-400' : net < 0 ? 'text-accent' : 'text-canvas-text',
                      ].join(' ')}
                    >
                      {fmtNet(net)}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-right text-canvas-cyan">{fmtInt(xp)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {recentError && (
        <div className="mt-3 rounded-lg border border-canvas-line bg-canvas-accent/10 p-3 text-sm text-accent">
          {recentError}
        </div>
      )}
    </Panel>
  )
}
