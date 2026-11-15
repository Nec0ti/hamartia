import { Globe, FileQuestion, BookOpen } from 'lucide-react'
import { useI18n } from '../i18n.jsx'

const PLACEHOLDERS = {
  questions: { icon: FileQuestion, title: 'comingSoon.questions.title', body: 'comingSoon.questions.body' },
  cosmos: { icon: Globe, title: 'comingSoon.cosmos.title', body: 'comingSoon.cosmos.body' },
  fatalflaw: { icon: BookOpen, title: 'comingSoon.coach.title', body: 'comingSoon.coach.body' },
}

export default function ComingSoon({ tabId }) {
  const { t } = useI18n()
  const tab = PLACEHOLDERS[tabId] || PLACEHOLDERS.cosmos
  const Icon = tab.icon

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-canvas-line bg-canvas-panel">
        <Icon size={28} className="text-canvas-text" />
      </div>
      <h1 className="text-2xl font-bold text-canvas-text">{t(tab.title)}</h1>
      <p className="max-w-md text-sm leading-relaxed text-canvas-muted">{t(tab.body)}</p>
      <p className="text-xs text-canvas-line">{t('common.laterPhase')}</p>
    </div>
  )
}
