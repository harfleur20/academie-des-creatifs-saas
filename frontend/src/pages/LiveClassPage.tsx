import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, Video } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, joinLiveClass, type LiveRoom } from '../lib/api'

declare global {
  interface Window {
    JitsiMeetExternalAPI?: new (domain: string, options: {
      roomName: string
      jwt: string
      parentNode: HTMLElement
      width: string
      height: string
      configOverwrite: Record<string, unknown>
    }) => { dispose: () => void }
  }
}

const scripts = new Map<string, Promise<void>>()

function loadJaasScript(src: string): Promise<void> {
  const previous = scripts.get(src)
  if (previous) return previous
  const loading = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = src
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => { script.remove(); scripts.delete(src); reject(new Error('Chargement du service live impossible.')) }
    document.head.appendChild(script)
  })
  scripts.set(src, loading)
  return loading
}

export function LiveClassPage({ space }: { space: 'teacher' | 'student' }) {
  const { courseDayId } = useParams()
  const container = useRef<HTMLDivElement>(null)
  const [room, setRoom] = useState<LiveRoom | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const id = Number(courseDayId)
    if (!Number.isInteger(id) || id < 1) { setError('Séance introuvable.'); setLoading(false); return }
    let cancelled = false
    let meeting: { dispose: () => void } | null = null
    setLoading(true)
    setError('')
    void joinLiveClass(id).then(async (joined) => {
      if (cancelled) return
      setRoom(joined)
      await loadJaasScript(joined.external_api_url)
      if (cancelled || !container.current) return
      if (!window.JitsiMeetExternalAPI) throw new Error('Le lecteur de classe live est indisponible.')
      meeting = new window.JitsiMeetExternalAPI(joined.domain, {
        roomName: joined.room_name,
        jwt: joined.token,
        parentNode: container.current,
        width: '100%',
        height: '100%',
        configOverwrite: { prejoinConfig: { enabled: true } },
      })
    }).catch((caught) => {
      if (!cancelled) setError(caught instanceof ApiError || caught instanceof Error ? caught.message : 'Impossible de rejoindre la classe live.')
    }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true; meeting?.dispose() }
  }, [courseDayId])

  return <main className="app-page live-class-page">
    <Link className="planning-back-link" to={space === 'teacher' ? '/app/teacher/sessions' : '/app/student/formations'}><ArrowLeft size={15}/> Retour aux sessions</Link>
    <header className="app-page-header"><div><span className="page-kicker">Classe en direct</span><h1>{room?.title || 'Votre cours live'}</h1><p>{room ? new Date(room.starts_at).toLocaleString('fr-FR', { dateStyle: 'full', timeStyle: 'short' }) : 'Connexion à la salle sécurisée'}</p></div><Video size={22}/></header>
    {error && <div className="form-error">{error}</div>}
    {loading && <div className="page-state">Ouverture de la classe live…</div>}
    <div ref={container} className="live-class-stage" aria-label="Salle de classe en direct" />
  </main>
}
