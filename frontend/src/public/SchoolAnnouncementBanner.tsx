import { Megaphone, Pause, Play } from 'lucide-react'
import { useState, type CSSProperties } from 'react'
import './SchoolAnnouncementBanner.css'

export function SchoolAnnouncementBanner({ text, backgroundColor, textColor }: { text: string; backgroundColor: string; textColor: string }) {
  const [paused, setPaused] = useState(false)
  const message = text.trim()
  if (!message) return null

  return <aside className="school-announcement" aria-label="Annonce de l’école" style={{ '--school-announcement-background': backgroundColor, '--school-announcement-text': textColor } as CSSProperties}>
    <Megaphone aria-hidden="true" size={17} />
    <span className="school-announcement-accessible" data-no-translate>{message}</span>
    <div className="school-announcement-window" aria-hidden="true">
      <div className={'school-announcement-track' + (paused ? ' is-paused' : '')}>
        <span data-no-translate>{message}</span><span data-no-translate>{message}</span>
      </div>
    </div>
    <button type="button" onClick={() => setPaused((value) => !value)} aria-label={paused ? 'Reprendre le défilement' : 'Mettre en pause le défilement'}>
      {paused ? <Play size={14} aria-hidden="true" /> : <Pause size={14} aria-hidden="true" />}
    </button>
  </aside>
}
