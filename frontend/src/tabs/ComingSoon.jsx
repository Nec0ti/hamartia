import { Globe, FileQuestion, BookOpen } from 'lucide-react'

const PLACEHOLDERS = {
  questions: { icon: FileQuestion, title: 'Yanlışlarım', body: 'Yanlış soru görsellerini yükle, hata türlerini etiketle ve tekrar eden konularını takip et.' },
  cosmos: { icon: Globe, title: 'Cosmos', body: 'Hatalarından doğan gezegenleri ve çalışma ilerlemeni tek bir haritada keşfet.' },
  fatalflaw: { icon: BookOpen, title: 'Çalışma Koçu', body: 'Kendi notlarını yükleyip yerel model bağlantısıyla çalış.' },
}

export default function ComingSoon({ tabId }) {
  const tab = PLACEHOLDERS[tabId] || PLACEHOLDERS.cosmos
  const Icon = tab.icon

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-canvas-line bg-canvas-panel">
        <Icon size={28} className="text-canvas-indigo" />
      </div>
      <h1 className="text-2xl font-bold text-canvas-text">{tab.title}</h1>
      <p className="max-w-md text-sm leading-relaxed text-canvas-muted">{tab.body}</p>
      <p className="text-xs text-canvas-line">Daha sonraki bir aşamada.</p>
    </div>
  )
}
