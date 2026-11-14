import { type CSSProperties, type FormEvent, useEffect, useRef, useState } from 'react'
import { Hand, LogOut, Mic, MicOff, Video, VideoOff, X } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  ApiError, answerLiveRollCall, fetchLiveRoomInfo, heartbeatLiveClass, joinLiveClass, leaveLiveClass, startLiveClass,
  startLiveRollCall, submitCourseDayReport, type LiveDevice, type LiveRollCall, type LiveRoom, type LiveRoomInfo,
} from '../lib/api'

const DEVICE_KEY = 'academie_live_device_id'

/** This browser's lasting identifier: the server keeps a student on one device at a time. */
function liveDevice(): LiveDevice {
  let id = ''
  try { id = window.localStorage.getItem(DEVICE_KEY) ?? '' } catch { /* storage blocked */ }
  if (!id) {
    id = typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`
    try { window.localStorage.setItem(DEVICE_KEY, id) } catch { /* kept for this page only */ }
  }
  return { id, label: navigator.userAgent.slice(0, 160) }
}

const HEARTBEAT_MS = 30_000
// Ten minutes before a forced end, the room says how long is left.
const END_WARNING_MS = 10 * 60_000
// While a roll call is open, the teacher's count of answers refreshes faster.
const ROLL_CALL_REFRESH_MS = 10_000

type JitsiApi = { dispose: () => void; addEventListener: (event: string, listener: () => void) => void }

declare global {
  interface Window {
    JitsiMeetExternalAPI?: new (domain: string, options: Record<string, unknown>) => JitsiApi
  }
}

const scripts = new Map<string, Promise<void>>()

function loadJitsiScript(src: string): Promise<void> {
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

// As on the mother site, the class keeps a short toolbar. The teacher also gets the
// participants pane, to mute or remove someone.
const STUDENT_TOOLBAR = ['microphone', 'camera', 'desktop', 'chat', 'raisehand', 'tileview', 'fullscreen', 'hangup']
const TEACHER_TOOLBAR = ['microphone', 'camera', 'desktop', 'chat', 'raisehand', 'participants-pane', 'tileview', 'fullscreen', 'hangup']

type DeliveryStatus = 'held' | 'partial' | 'interrupted' | 'not_held'
const DELIVERY_STATUSES: { value: DeliveryStatus; label: string }[] = [
  { value: 'held', label: 'Cours tenu' },
  { value: 'partial', label: 'Partiel' },
  { value: 'interrupted', label: 'Interrompu' },
  { value: 'not_held', label: 'Non tenu' },
]

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('fr-FR', { weekday: 'short', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function formatWait(ms: number) {
  const total = Math.max(0, Math.ceil(ms / 1000))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = String(total % 60).padStart(2, '0')
  return hours > 0 ? `${hours}h ${String(minutes).padStart(2, '0')}min ${seconds}s` : `${minutes}min ${seconds}s`
}

function formatMinutes(minutes: number) {
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours === 0) return `${rest} min`
  return rest === 0 ? `${hours} h` : `${hours} h ${String(rest).padStart(2, '0')}`
}

/** The live class, full screen as on the mother site: waiting room, welcome card, then the room. */
export function LiveClassPage({ space }: { space: 'teacher' | 'student' }) {
  const { courseDayId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const stage = useRef<HTMLDivElement>(null)
  const meeting = useRef<JitsiApi | null>(null)
  const joinedRoom = useRef<LiveRoom | null>(null)
  const device = useRef<LiveDevice>(liveDevice())
  const [info, setInfo] = useState<LiveRoomInfo | null>(null)
  const [error, setError] = useState('')
  const [nowMs, setNowMs] = useState(() => Date.now())
  const [withAudio, setWithAudio] = useState(false)
  const [withVideo, setWithVideo] = useState(true)
  const [joining, setJoining] = useState(false)
  const [joinError, setJoinError] = useState('')
  const [entered, setEntered] = useState(false)
  const [starting, setStarting] = useState(false)
  const [leaveOpen, setLeaveOpen] = useState(false)
  const [endOpen, setEndOpen] = useState(false)
  const [ending, setEnding] = useState(false)
  const [endError, setEndError] = useState('')
  const [draft, setDraft] = useState({ delivery_status: 'held' as DeliveryStatus, summary: '', difficulties: '', homework: '', attendance_notes: '' })
  const [rollCall, setRollCall] = useState<LiveRollCall | null>(null)
  const [rollCallBusy, setRollCallBusy] = useState(false)
  const [endsBy, setEndsBy] = useState<string | null>(null)
  const backPath = space === 'teacher' ? '/app/teacher/sessions' : '/app/student/formations'

  useEffect(() => {
    const id = Number(courseDayId)
    if (!Number.isInteger(id) || id < 1) { setError('Séance introuvable.'); return }
    let cancelled = false
    fetchLiveRoomInfo(id)
      .then((loaded) => { if (!cancelled) { setInfo(loaded); setEndsBy(loaded.ends_by ?? null) } })
      .catch((caught) => { if (!cancelled) setError(caught instanceof ApiError ? caught.message : 'Classe live introuvable.') })
    return () => { cancelled = true }
  }, [courseDayId])

  useEffect(() => {
    const interval = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(interval)
  }, [])

  // The room mounts once the welcome card has handed over a token.
  useEffect(() => {
    const room = joinedRoom.current
    if (!entered || !room || !stage.current || !window.JitsiMeetExternalAPI) return
    const toolbar = room.moderator ? TEACHER_TOOLBAR : STUDENT_TOOLBAR
    const api = new window.JitsiMeetExternalAPI(room.domain, {
      roomName: room.room_name,
      jwt: room.token,
      parentNode: stage.current,
      width: '100%',
      height: '100%',
      lang: 'fr',
      configOverwrite: {
        startWithAudioMuted: !withAudio,
        startWithVideoMuted: !withVideo,
        toolbarButtons: toolbar,
        disablePolls: !room.moderator,
        disableInviteFunctions: true,
        disableDeepLinking: true,
        readOnlyName: true,
        hideConferenceSubject: true,
      },
      interfaceConfigOverwrite: { TOOLBAR_BUTTONS: toolbar, DEFAULT_BACKGROUND: '#0f0f1a' },
    })
    api.addEventListener('readyToClose', () => { api.dispose(); navigate(backPath) })
    meeting.current = api
    return () => { api.dispose(); meeting.current = null }
  }, [entered]) // eslint-disable-line react-hooks/exhaustive-deps

  // While in the room, the device keeps its place; another device or the end of the course closes it.
  useEffect(() => {
    const courseDay = joinedRoom.current?.course_day_id
    if (!entered || !courseDay) return
    let stopped = false
    const beat = () => {
      heartbeatLiveClass(courseDay, device.current).then((result) => {
        if (stopped) return
        setRollCall(result?.roll_call ?? null)
        if (result && result.ends_by !== undefined) setEndsBy(result.ends_by ?? null)
      }).catch((caught) => {
        if (stopped || !(caught instanceof ApiError) || ![403, 404, 409].includes(caught.status)) return
        meeting.current?.dispose()
        meeting.current = null
        setEntered(false)
        setError(caught.message)
      })
    }
    const leaveRoom = () => { leaveLiveClass(courseDay, device.current).catch(() => undefined) }
    const onVisible = () => { if (document.visibilityState === 'visible') beat() }
    const interval = window.setInterval(beat, HEARTBEAT_MS)
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('pagehide', leaveRoom)
    return () => {
      stopped = true
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('pagehide', leaveRoom)
      leaveRoom()
    }
  }, [entered])

  // At its forced end the room closes for everyone; the server refuses it from then on too.
  useEffect(() => {
    if (!entered || !endsBy || Date.now() < Date.parse(endsBy)) return
    meeting.current?.dispose()
    meeting.current = null
    setEntered(false)
    if (info?.responsible_teacher) setEndOpen(true)
    else setError('Ce cours en live est terminé : sa salle est fermée.')
  }, [entered, endsBy, nowMs]) // eslint-disable-line react-hooks/exhaustive-deps

  // The teacher sees the answers come in while the roll call is open.
  useEffect(() => {
    const courseDay = joinedRoom.current?.course_day_id
    if (!entered || !courseDay || !rollCall?.open || rollCall.answers_count === null) return
    const interval = window.setInterval(() => {
      heartbeatLiveClass(courseDay, device.current).then((result) => setRollCall(result?.roll_call ?? null)).catch(() => undefined)
    }, ROLL_CALL_REFRESH_MS)
    return () => window.clearInterval(interval)
  }, [entered, rollCall?.open, rollCall?.answers_count === null]) // eslint-disable-line react-hooks/exhaustive-deps

  const endsByMs = endsBy ? Date.parse(endsBy) : Number.NaN
  const endingSoon = entered && !Number.isNaN(endsByMs) && endsByMs - nowMs <= END_WARNING_MS && endsByMs > nowMs

  if (error) {
    return <div className="live-room live-room--error">
      <p>{error}</p>
      <button type="button" className="live-room__leave" onClick={() => navigate(backPath)}>Retour</button>
    </div>
  }

  const opensMs = info ? Date.parse(info.opens_at) : Number.NaN
  const closesMs = info ? Date.parse(info.closes_at) : Number.NaN
  const startsMs = info ? Date.parse(info.starts_at) : Number.NaN
  const endsMs = info ? Date.parse(info.ends_at) : Number.NaN
  const phase = !info ? 'loading' : entered ? 'live' : nowMs < opensMs ? 'waiting' : nowMs > closesMs ? 'closed' : 'welcome'
  const canStart = Boolean(info?.responsible_teacher && !info.started_at && nowMs >= startsMs)
  const canEnd = Boolean(info?.responsible_teacher && (info.started_at || nowMs >= endsMs))
  const accent = { '--live-accent': info?.school_primary_color || '#2dd4bf' } as CSSProperties
  const welcomeBackground = info?.formation_image_url
    ? { '--prejoin-bg': `url(${JSON.stringify(info.formation_image_url)})` } as CSSProperties
    : undefined

  async function enterClass() {
    if (!info) return
    setJoining(true)
    setJoinError('')
    try {
      const room = await joinLiveClass(info.course_day_id, device.current)
      await loadJitsiScript(room.external_api_url)
      if (!window.JitsiMeetExternalAPI) throw new Error('Le lecteur de classe live est indisponible.')
      joinedRoom.current = room
      if (room.ends_by !== undefined) setEndsBy(room.ends_by ?? null)
      setEntered(true)
    } catch (caught) {
      setJoinError(caught instanceof ApiError || caught instanceof Error ? caught.message : 'Impossible de rejoindre la classe.')
    } finally {
      setJoining(false)
    }
  }

  async function startCourse() {
    if (!info) return
    setStarting(true)
    try {
      const started = await startLiveClass(info.course_day_id)
      setInfo({ ...info, started_at: started.started_at, closes_at: started.closes_at ?? info.closes_at })
      setEndsBy(started.ends_by ?? null)
    } catch (caught) {
      setJoinError(caught instanceof ApiError ? caught.message : 'Démarrage du cours impossible.')
    } finally {
      setStarting(false)
    }
  }

  async function callRoll() {
    if (!info) return
    setRollCallBusy(true)
    try {
      setRollCall(await startLiveRollCall(info.course_day_id))
    } catch (caught) {
      setJoinError(caught instanceof ApiError ? caught.message : "Impossible de lancer l'appel.")
    } finally {
      setRollCallBusy(false)
    }
  }

  async function answerRoll() {
    if (!info || !rollCall) return
    setRollCallBusy(true)
    try {
      await answerLiveRollCall(info.course_day_id, rollCall.id)
      setRollCall({ ...rollCall, answered: true })
    } catch (caught) {
      setRollCall(null)
      setJoinError(caught instanceof ApiError ? caught.message : "Votre réponse à l'appel n'a pas été enregistrée.")
    } finally {
      setRollCallBusy(false)
    }
  }

  function leave() {
    meeting.current?.dispose()
    meeting.current = null
    navigate(backPath)
  }

  async function endCourse(event: FormEvent) {
    event.preventDefault()
    if (!info) return
    setEnding(true)
    setEndError('')
    try {
      await submitCourseDayReport(info.course_day_id, {
        delivery_status: draft.delivery_status,
        summary: draft.summary.trim(),
        difficulties: draft.difficulties.trim() || undefined,
        homework: draft.homework.trim() || undefined,
        attendance_notes: draft.attendance_notes.trim() || undefined,
      })
      leave()
    } catch (caught) {
      setEndError(caught instanceof ApiError ? caught.message : 'Clôture du cours impossible.')
    } finally {
      setEnding(false)
    }
  }

  return <div className="live-room" style={accent}>
    <header className="live-room__bar">
      <div className="live-room__bar-left">
        {info?.school_logo_url && <img className="live-room__school-logo" src={info.school_logo_url} alt={`Logo de ${info.school_name}`} />}
        <span className={`live-room__badge${phase === 'live' ? '' : ' live-room__badge--waiting'}`}>
          {phase === 'live' ? 'EN DIRECT' : phase === 'waiting' ? 'ATTENTE' : 'ACCUEIL'}
        </span>
        {info ? <>
          <strong className="live-room__title">{info.formation_title}</strong>
          <span className="live-room__label">{info.session_label} · {info.title}</span>
          <span className="live-room__date">{formatDate(info.starts_at)}</span>
        </> : <span className="live-room__loading">Connexion en cours…</span>}
      </div>
      <div className="live-room__bar-actions">
        {endingSoon && <span className="live-room__roll-call-status" role="status">Fin du cours dans {formatWait(endsByMs - nowMs)}</span>}
        {phase === 'live' && info?.responsible_teacher && info.started_at && (rollCall?.open
          ? <span className="live-room__roll-call-status" role="status">Appel en cours · {rollCall.answers_count ?? 0} réponse(s) · {formatWait(Date.parse(rollCall.closes_at) - nowMs)}</span>
          : <>
            {rollCall && <span className="live-room__roll-call-status">Dernier appel : {rollCall.answers_count ?? 0} réponse(s)</span>}
            <button type="button" className="live-room__end" disabled={rollCallBusy} onClick={() => void callRoll()}><Hand size={14} aria-hidden="true" /> Faire l'appel</button>
          </>)}
        {canStart && <button type="button" className="live-room__end" disabled={starting} onClick={() => void startCourse()}>
          {starting ? 'Démarrage…' : 'Démarrer le cours'}
        </button>}
        {canEnd && <button type="button" className="live-room__end" onClick={() => setEndOpen(true)}>Terminer le cours</button>}
        <button type="button" className="live-room__leave" onClick={() => (phase === 'live' ? setLeaveOpen(true) : leave())}>Quitter</button>
      </div>
    </header>

    {phase === 'live' ? <div className="live-room__stage" ref={stage} aria-label="Salle de classe en direct" /> : (
      <div className="live-room__stage live-room__stage--waiting" style={phase === 'welcome' ? welcomeBackground : undefined}>
        {phase === 'loading' && <p className="live-room__loading">Ouverture de la classe…</p>}
        {info && phase === 'waiting' && <div className="live-room__waiting-card">
          <span className="live-room__waiting-kicker">Salle d'attente</span>
          <h1>{info.formation_title}</h1>
          <p>La salle de {info.school_name} ouvre le {formatDate(info.opens_at)}, 15 minutes avant le cours. Vous passerez à l'accueil de la classe automatiquement.</p>
          <strong className="live-room__waiting-countdown">{formatWait(opensMs - nowMs)}</strong>
        </div>}
        {info && phase === 'closed' && <div className="live-room__waiting-card">
          <span className="live-room__waiting-kicker">Salle fermée</span>
          <h1>{info.formation_title}</h1>
          <p>La salle ferme 15 minutes après la fin du cours.</p>
        </div>}
        {info && phase === 'welcome' && <div className="live-room__waiting-card live-room__prejoin-card">
          <span className="live-room__waiting-kicker">Accueil de la classe</span>
          <h1>{info.formation_title}</h1>
          <p>
            {user?.full_name
              ? <>Vous rejoignez la classe de {info.school_name} en tant que <span className="live-room__name-chip">{user.full_name}</span>.</>
              : `Préparez votre entrée dans la classe de ${info.school_name}.`}
          </p>
          {info.responsible_teacher && !info.started_at && info.live_minutes_left != null && <p className="live-room__prejoin-hint">
            {info.live_minutes_left > 0
              ? `Il reste à votre école ${formatMinutes(info.live_minutes_left)} de live ce mois-ci : le cours s'arrêtera au plus tard à ce moment-là.`
              : "Les heures de live incluses ce mois-ci dans votre forfait sont utilisées : le cours ne pourra pas démarrer."}
          </p>}
          {!info.started_at && <p className="live-room__prejoin-hint">
            {info.responsible_teacher
              ? "Démarrez le cours à l'heure prévue avec le bouton en haut de la page."
              : "Le professeur n'a pas encore démarré le cours. Vous pouvez déjà entrer."}
          </p>}
          <hr className="live-room__prejoin-divider" />
          <div className="live-room__prejoin-controls" aria-label="Options avant de rejoindre la classe">
            <button type="button" className={`live-room__prejoin-toggle${withAudio ? ' is-active' : ''}`} aria-pressed={withAudio} onClick={() => setWithAudio((value) => !value)}>
              {withAudio ? <Mic size={20} /> : <MicOff size={20} />}<span>{withAudio ? 'Micro ouvert' : 'Micro coupé'}</span>
            </button>
            <button type="button" className={`live-room__prejoin-toggle${withVideo ? ' is-active' : ''}`} aria-pressed={withVideo} onClick={() => setWithVideo((value) => !value)}>
              {withVideo ? <Video size={20} /> : <VideoOff size={20} />}<span>{withVideo ? 'Caméra ouverte' : 'Caméra coupée'}</span>
            </button>
          </div>
          {joinError && <p className="live-room__error" role="alert">{joinError}</p>}
          <button type="button" className="live-room__join-class" disabled={joining} onClick={() => void enterClass()}>
            <Video size={22} aria-hidden="true" />
            {joining ? 'Ouverture…' : 'Rejoindre la classe'}
          </button>
        </div>}
      </div>
    )}

    {phase === 'live' && rollCall?.open && rollCall.answers_count === null && !rollCall.answered && <div className="live-room-confirm" role="alertdialog" aria-modal="true" aria-labelledby="live-room-roll-call-title">
      <div className="live-room-confirm__backdrop" aria-hidden="true" />
      <div className="live-room-confirm__panel">
        <span className="live-room-confirm__icon live-room-roll-call__icon"><Hand size={22} /></span>
        <h2 id="live-room-roll-call-title">Le professeur fait l'appel</h2>
        <p>Confirmez que vous suivez le cours. Il reste {formatWait(Date.parse(rollCall.closes_at) - nowMs)}.</p>
        <button type="button" className="live-room__join-class" disabled={rollCallBusy} onClick={() => void answerRoll()}>Je suis là</button>
      </div>
    </div>}

    {leaveOpen && <div className="live-room-confirm" role="dialog" aria-modal="true" aria-labelledby="live-room-leave-title">
      <button type="button" className="live-room-confirm__backdrop" aria-label="Rester dans la classe" onClick={() => setLeaveOpen(false)} />
      <div className="live-room-confirm__panel">
        <button type="button" className="live-room-confirm__close" aria-label="Fermer" onClick={() => setLeaveOpen(false)}><X size={18} /></button>
        <span className="live-room-confirm__icon"><LogOut size={22} /></span>
        <h2 id="live-room-leave-title">Voulez-vous quitter le live ?</h2>
        <p>Vous pourrez revenir tant que la salle est encore ouverte.</p>
        <div className="live-room-confirm__actions">
          <button type="button" className="live-room-confirm__cancel" onClick={() => setLeaveOpen(false)}>Rester</button>
          <button type="button" className="live-room-confirm__leave" onClick={leave}>Oui, quitter</button>
        </div>
      </div>
    </div>}

    {endOpen && info && <div className="live-room-confirm live-room-end" role="dialog" aria-modal="true" aria-labelledby="live-room-end-title">
      <button type="button" className="live-room-confirm__backdrop" aria-label="Annuler la fin du cours" onClick={() => setEndOpen(false)} />
      <form className="live-room-confirm__panel live-room-end__panel" onSubmit={(event) => void endCourse(event)}>
        <button type="button" className="live-room-confirm__close" aria-label="Fermer" onClick={() => setEndOpen(false)}><X size={18} /></button>
        <div className="live-room-end__head">
          <h2 id="live-room-end-title">Terminer le cours</h2>
          <p>Le compte rendu clôture la séance et la salle. Les étudiants entrés en salle sont marqués présents, ou en retard au-delà de 15 minutes après le début ; les autres absents. Vous pourrez corriger les présences pendant 24 heures.</p>
        </div>
        <div className="live-room-end__status-row">
          <span className="live-room-end__status-label">Déroulement <em>*</em></span>
          <div className="live-room-end__status-pills" role="group" aria-label="Déroulement du cours">
            {DELIVERY_STATUSES.map(({ value, label }) => <button
              key={value}
              type="button"
              className={`live-room-end__status-pill live-room-end__status-pill--${value}${draft.delivery_status === value ? ' is-active' : ''}`}
              aria-pressed={draft.delivery_status === value}
              onClick={() => setDraft((current) => ({ ...current, delivery_status: value }))}
            >{label}</button>)}
          </div>
        </div>
        <div className="live-room-end__fields">
          <label className="live-room-end__field live-room-end__field--full">
            <span>Résumé du cours <em>*</em></span>
            <textarea required minLength={10} rows={3} value={draft.summary} placeholder="Notions vues, démonstration, exercices réalisés…"
              onChange={(event) => setDraft((current) => ({ ...current, summary: event.target.value }))} />
          </label>
          <label className="live-room-end__field">
            <span>Difficultés rencontrées</span>
            <textarea rows={2} value={draft.difficulties} placeholder="Technique, compréhension, rythme…"
              onChange={(event) => setDraft((current) => ({ ...current, difficulties: event.target.value }))} />
          </label>
          <label className="live-room-end__field">
            <span>Devoirs ou suite</span>
            <textarea rows={2} value={draft.homework} placeholder="Travail à faire, ressources à consulter…"
              onChange={(event) => setDraft((current) => ({ ...current, homework: event.target.value }))} />
          </label>
          <label className="live-room-end__field live-room-end__field--full">
            <span>Notes de présence</span>
            <textarea rows={2} value={draft.attendance_notes} placeholder="Retards, absences justifiées, remarques…"
              onChange={(event) => setDraft((current) => ({ ...current, attendance_notes: event.target.value }))} />
          </label>
        </div>
        {endError && <p className="live-room__error" role="alert">{endError}</p>}
        <div className="live-room-confirm__actions">
          <button type="button" className="live-room-confirm__cancel" onClick={() => setEndOpen(false)}>Annuler</button>
          <button type="submit" className="live-room-confirm__leave" disabled={ending}>{ending ? 'Clôture…' : 'Clôturer le cours'}</button>
        </div>
      </form>
    </div>}
  </div>
}
