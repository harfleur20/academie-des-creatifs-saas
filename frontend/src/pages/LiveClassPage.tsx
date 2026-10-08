import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, Video } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, joinLiveClass, startLiveClass, type LiveRoom } from '../lib/api'
import { useTenant } from '../app/TenantContext'

declare global {
  interface Window {
    JitsiMeetExternalAPI?: new (domain: string, options: {
      roomName: string
      jwt: string
      parentNode: HTMLElement
      width: string
      height: string
      configOverwrite: Record<string, unknown>
      lang?: string
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
  const { activeOrganization } = useTenant()
  const { courseDayId } = useParams()
  const container = useRef<HTMLDivElement>(null)
  const [room, setRoom] = useState<LiveRoom | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [nowMs, setNowMs] = useState(Date.now())

  useEffect(() => {
    const interval = window.setInterval(() => setNowMs(Date.now()), 10_000)
    return () => window.clearInterval(interval)
  }, [])

  async function startCourse() {
    if (!room) return
    setStarting(true)
    setError('')
    try {
      const result = await startLiveClass(room.course_day_id)
      setRoom((current) => current ? { ...current, started_at: result.started_at } : current)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Démarrage du cours impossible.')
    } finally {
      setStarting(false)
    }
  }

  useEffect(() => {
    const id = Number(courseDayId)
    if (!Number.isInteger(id) || id < 1) { setError('Séance introuvable.'); setLoading(false); return }
    let cancelled = false
    let meeting: { dispose: () => void } | null = null
    setLoading(true)
    setError('')
    setRoom(null)
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
        lang: 'fr',
        configOverwrite: {
          prejoinConfig: { enabled: true },
          subject: `${joined.school_name} · ${joined.title}`,
        },
      })
    }).catch((caught) => {
      if (!cancelled) setError(caught instanceof ApiError || caught instanceof Error ? caught.message : 'Impossible de rejoindre la classe live.')
    }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true; meeting?.dispose() }
  }, [courseDayId, activeOrganization?.id])

  return <main className="app-page live-class-page">
    <Link className="planning-back-link" to={space === 'teacher' ? '/app/teacher/sessions' : '/app/student/formations'}><ArrowLeft size={15}/> Retour aux sessions</Link>
    <header className="app-page-header"><div><span className="page-kicker">Classe en direct · {room?.school_name || activeOrganization?.name || 'Votre école'}</span><h1>{room?.title || 'Votre cours live'}</h1><p>{room ? new Date(room.starts_at).toLocaleString('fr-FR', { dateStyle: 'full', timeStyle: 'short' }) : 'Connexion à la salle sécurisée'}</p></div>{room?.school_logo_url ? <img className="live-class-school-logo" src={room.school_logo_url} alt={`Logo de ${room.school_name}`} /> : <Video size={22}/>}</header>
    {error && <div className="form-error">{error}</div>}
    {loading && <div className="page-state">Ouverture de la classe live de {activeOrganization?.name || 'votre école'}…</div>}
    {room && <div className="live-class-controls">
      {room.started_at ? <p>Cours démarré à {new Date(room.started_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}.</p> : space === 'teacher' ? <>
        <p>La salle de {room.school_name} est ouverte. Démarrez le cours à l'heure prévue lorsque vous êtes prêt.</p>
        <button className="primary-button" type="button" disabled={starting || nowMs < new Date(room.starts_at).getTime()} onClick={() => void startCourse()}>Démarrer le cours</button>
      </> : <p>La salle de {room.school_name} est ouverte. Le professeur n'a pas encore démarré le cours.</p>}
    </div>}
    <div ref={container} className="live-class-stage" aria-label="Salle de classe en direct" />
  </main>
}
