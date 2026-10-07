/**
 * Small presentational primitives shared across dashboard panels. Kept as plain
 * function components so they can compose inside recharts containers.
 */

/** Standard zinc card container. */
export function Panel({ children, className = '' }) {
  return (
    <div
      className={`rounded-xl border border-canvas-line bg-canvas-panel p-5 ${className}`}
    >
      {children}
    </div>
  )
}

/** Panel header with an icon and title. */
export function Header({ icon: Icon, title, subtitle }) {
  return (
    <div className="mb-4 flex items-center gap-2">
      {Icon && <Icon size={16} className="text-canvas-accent" />}
      <h3 className="text-sm font-semibold uppercase tracking-wider text-canvas-text">
        {title}
      </h3>
      {subtitle && <span className="text-xs text-canvas-muted">{subtitle}</span>}
    </div>
  )
}

/** Placeholder shown when a chart has no data to render. */
export function Empty({ children }) {
  return (
    <div className="flex h-full items-center justify-center text-sm text-canvas-muted">
      {children}
    </div>
  )
}

/** Segmented control for bar/line toggle. */
export function Toggle({ value, options, onChange }) {
  return (
    <div className="inline-flex rounded-lg border border-canvas-line bg-canvas-base p-0.5">
      {options.map((opt) => {
        const active = value === opt.value
        const Icon = opt.icon
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={[
              'rounded-md px-3 py-1 text-xs font-medium transition',
              active
                ? 'bg-canvas-accent text-white'
                : 'text-canvas-muted hover:text-canvas-text',
            ].join(' ')}
          >
            {active && (Icon && typeof Icon === 'function' ? <Icon size={12} className="inline mr-1" /> : null)}
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

/** Minimal select for subject filtering. */
export function SubjectSelect({ value, options, onChange }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-lg border border-canvas-line bg-canvas-base px-3 py-1.5 text-xs text-canvas-text outline-none transition hover:bg-canvas-raise"
    >
      {options.map((s) => (
        <option key={s} value={s} className="bg-canvas-panel">
          {s === 'all' ? 'All subjects' : s}
        </option>
      ))}
    </select>
  )
}
