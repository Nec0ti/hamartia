import { Globe, FileQuestion, BookOpen } from 'lucide-react'

const PLACEHOLDERS = {
  questions: { icon: FileQuestion, title: 'Quest[ion]s', body: 'Mistake vault: upload a question image, run the Council of Minds analysis, and tag your recurring hamartia.' },
  cosmos: { icon: Globe, title: 'Cosmos', body: 'Assault planetary nodes born from your mistakes, spend XP to cleanse them, and unlock new sectors of the arena.' },
  fatalflaw: { icon: BookOpen, title: 'Fatal Flaw', body: 'Document-grounded study assistant: upload notes and chat with the active LiteLLM model guided by the Council of Minds.' },
}

export default function ComingSoon() {
  const tab = PLACEHOLDERS[location.hash.slice(1) || ''] || PLACEHOLDERS.questions
  const Icon = tab.icon

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-canvas-line bg-canvas-panel">
        <Icon size={28} className="text-canvas-indigo" />
      </div>
      <h1 className="text-2xl font-bold text-canvas-text">{tab.title}</h1>
      <p className="max-w-md text-sm leading-relaxed text-canvas-muted">{tab.body}</p>
      <p className="text-xs text-canvas-line">Coming in a later phase.</p>
    </div>
  )
}
