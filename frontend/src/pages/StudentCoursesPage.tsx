import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CheckCircle2, ChevronDown, ChevronRight, ExternalLink, PlayCircle } from 'lucide-react'
import { useTenant } from '../app/TenantContext'
import { PdfLessonReader } from '../components/PdfLessonReader'
import { loadBunnyPlayerApi, loadVimeoApi, loadYouTubeApi, parseVideoEmbed } from '../lib/videoEmbed'
import {
  ApiError, completeStudentLesson, listStudentLearning, reportStudentLessonVideoProgress,
  type LearningLesson, type LearningSession,
} from '../lib/api'

type Mode = 'classic' | 'guided'
type VideoPayload = Parameters<typeof reportStudentLessonVideoProgress>[1]

function bunnyTiming(payload: unknown): { seconds: number; duration: number } | null {
  try {
    const value = typeof payload === 'string' ? JSON.parse(payload) as unknown : payload
    if (!value || typeof value !== 'object') return null
    const timing = value as Record<string, unknown>
    if (typeof timing.seconds !== 'number' || typeof timing.duration !== 'number') return null
    return { seconds: timing.seconds, duration: timing.duration }
  } catch {
    return null
  }
}

function findLesson(session: LearningSession, lessonId: number): LearningLesson | null {
  for (const course of session.courses) {
    for (const chapter of course.chapters) {
      const lesson = chapter.lessons.find((item) => item.id === lessonId)
      if (lesson) return lesson
    }
  }
  return null
}

function firstLesson(session: LearningSession): LearningLesson | null {
  return session.courses.flatMap((course) => course.chapters.flatMap((chapter) => chapter.lessons)).find((lesson) => !lesson.is_locked) ?? null
}

function TrackedLessonVideo({ lesson, onUpdated, onError }: {
  lesson: LearningLesson
  onUpdated: (session: LearningSession) => void
  onError: (message: string) => void
}) {
  const inFlight = useRef(false)
  const queued = useRef<VideoPayload | null>(null)
  const lastHeartbeat = useRef(0)
  const completedRef = useRef(lesson.completed)
  completedRef.current = lesson.completed
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const embed = useMemo(() => parseVideoEmbed(lesson.video_url ?? ''), [lesson.video_url])
  const [bunnyScriptReady, setBunnyScriptReady] = useState(false)

  const send = useCallback(async (payload: VideoPayload) => {
    if (inFlight.current) { queued.current = payload; return }
    inFlight.current = true
    try {
      onUpdated(await reportStudentLessonVideoProgress(lesson.id, payload))
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Le suivi vidéo n’a pas pu être enregistré.')
    } finally {
      inFlight.current = false
      if (queued.current) {
        const next = queued.current
        queued.current = null
        void send(next)
      }
    }
  }, [lesson.id, onUpdated, onError])

  const report = useCallback((position: number, duration: number, rate: number, event: VideoPayload['event']) => {
    if (!Number.isFinite(position) || !Number.isFinite(duration) || duration <= 0) return
    if (event === 'heartbeat') {
      if (completedRef.current || performance.now() - lastHeartbeat.current < 1500) return
      lastHeartbeat.current = performance.now()
    }
    void send({ current_time_seconds: position, duration_seconds: duration, playback_rate: rate, event })
  }, [send])

  useEffect(() => {
    if (embed.kind !== 'youtube' || !iframeRef.current) return
    let cancelled = false
    let player: InstanceType<NonNullable<Window['YT']>['Player']> | null = null
    let interval: number | null = null
    const stop = () => { if (interval !== null) window.clearInterval(interval); interval = null }
    void loadYouTubeApi().then(() => {
      if (cancelled || !iframeRef.current || !window.YT?.Player) return
      player = new window.YT.Player(iframeRef.current, {
        events: { onStateChange: (event: { data: number }) => {
          if (!player || !window.YT) return
          if (event.data === window.YT.PlayerState.PLAYING) {
            report(player.getCurrentTime(), player.getDuration(), player.getPlaybackRate(), 'seek')
            stop()
            interval = window.setInterval(() => {
              if (player) report(player.getCurrentTime(), player.getDuration(), player.getPlaybackRate(), 'heartbeat')
            }, 1000)
          } else if (event.data === window.YT.PlayerState.ENDED) {
            stop()
            report(player.getCurrentTime(), player.getDuration(), player.getPlaybackRate(), 'ended')
          } else stop()
        } },
      })
    }).catch(() => { if (!cancelled) onError('Le lecteur YouTube n’a pas pu être chargé.') })
    return () => { cancelled = true; stop(); player?.destroy() }
  }, [embed, report, onError])

  useEffect(() => {
    if (embed.kind !== 'vimeo' || !iframeRef.current) return
    let cancelled = false
    let player: InstanceType<NonNullable<Window['Vimeo']>['Player']> | null = null
    const onPlay = async () => {
      if (!player) return
      const [position, duration] = await Promise.all([player.getCurrentTime(), player.getDuration()])
      if (!cancelled) report(position, duration, 1, 'seek')
    }
    const onHeartbeat = (value?: Record<string, number>) => { if (value) report(value.seconds ?? 0, value.duration ?? 0, 1, 'heartbeat') }
    const onSeek = (value?: Record<string, number>) => { if (value) report(value.seconds ?? 0, value.duration ?? 0, 1, 'seek') }
    const onEnded = (value?: Record<string, number>) => { if (value) report(value.seconds ?? value.duration ?? 0, value.duration ?? 0, 1, 'ended') }
    void loadVimeoApi().then(() => {
      if (cancelled || !iframeRef.current || !window.Vimeo?.Player) return
      player = new window.Vimeo.Player(iframeRef.current)
      player.on('play', onPlay)
      player.on('timeupdate', onHeartbeat)
      player.on('seeking', onSeek)
      player.on('seeked', onSeek)
      player.on('ended', onEnded)
    }).catch(() => { if (!cancelled) onError('Le lecteur Vimeo n’a pas pu être chargé.') })
    return () => {
      cancelled = true
      player?.off('play', onPlay)
      player?.off('timeupdate', onHeartbeat)
      player?.off('seeking', onSeek)
      player?.off('seeked', onSeek)
      player?.off('ended', onEnded)
    }
  }, [embed, report, onError])

  useEffect(() => {
    if (embed.kind !== 'stream') return
    let cancelled = false
    void loadBunnyPlayerApi().then(() => {
      if (!cancelled) setBunnyScriptReady(true)
    }).catch(() => { if (!cancelled) onError('Le lecteur Bunny n’a pas pu être chargé.') })
    return () => { cancelled = true }
  }, [embed.kind, onError])

  useEffect(() => {
    if (embed.kind !== 'stream' || !bunnyScriptReady || !iframeRef.current || !window.playerjs?.Player) return
    const player = new window.playerjs.Player(iframeRef.current)
    let needsBaseline = true
    const baseline = () => { needsBaseline = true }
    const timeupdate = (payload?: unknown) => {
      const timing = bunnyTiming(payload)
      if (!timing) return
      report(timing.seconds, timing.duration, 1, needsBaseline ? 'seek' : 'heartbeat')
      needsBaseline = false
    }
    const ended = (payload?: unknown) => {
      const timing = bunnyTiming(payload)
      if (timing) report(timing.seconds, timing.duration, 1, 'ended')
      needsBaseline = true
    }
    player.on('play', baseline)
    player.on('pause', baseline)
    player.on('seeking', baseline)
    player.on('seeked', baseline)
    player.on('timeupdate', timeupdate)
    player.on('ended', ended)
    return () => {
      player.off('play', baseline)
      player.off('pause', baseline)
      player.off('seeking', baseline)
      player.off('seeked', baseline)
      player.off('timeupdate', timeupdate)
      player.off('ended', ended)
    }
  }, [embed.kind, bunnyScriptReady, report])

  return <>
    {embed.kind === 'direct' ? <video className="student-reader-video" src={embed.src} controls preload="metadata"
      onPlay={(event) => { const video = event.currentTarget; report(video.currentTime, video.duration, video.playbackRate, 'seek') }}
      onSeeking={(event) => { const video = event.currentTarget; report(video.currentTime, video.duration, video.playbackRate, 'seek') }}
      onTimeUpdate={(event) => { const video = event.currentTarget; if (!video.paused && !video.seeking) report(video.currentTime, video.duration, video.playbackRate, 'heartbeat') }}
      onEnded={(event) => { const video = event.currentTarget; report(video.currentTime, video.duration, video.playbackRate, 'ended') }}
    /> : embed.kind === 'stream' && !bunnyScriptReady ? <div className="student-reader-video">Chargement du lecteur…</div> : <iframe className="student-reader-video" ref={iframeRef} src={embed.src} title={lesson.title} allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen" allowFullScreen />}
    <p className="student-reader-video-progress">Lecture suivie : {Math.round(lesson.video_watched_pct)} % · validation automatique à 80 %.</p>
  </>
}

export function StudentCoursesPage({ mode }: { mode?: Mode }) {
  const { activeOrganization } = useTenant()
  const { enrollmentId } = useParams()
  const [sessions, setSessions] = useState<LearningSession[]>([])
  const [selectedEnrollmentId, setSelectedEnrollmentId] = useState<number | null>(null)
  const [activeLesson, setActiveLesson] = useState<LearningLesson | null>(null)
  const [openChapters, setOpenChapters] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!activeOrganization) return
    let cancelled = false
    setLoading(true)
    setError('')
    setSessions([])
    setSelectedEnrollmentId(null)
    setActiveLesson(null)
    listStudentLearning().then((rows) => {
      if (cancelled) return
      setSessions(rows)
      const selected = mode
        ? rows.find((item) => item.enrollment_id === Number(enrollmentId) && item.dashboard_type === mode)
        : rows[0]
      setSelectedEnrollmentId(selected?.enrollment_id ?? null)
      setActiveLesson(selected && !selected.is_locked ? firstLesson(selected) : null)
      const chapterId = selected?.courses[0]?.chapters[0]?.id
      setOpenChapters(chapterId ? new Set([chapterId]) : new Set())
    }).catch((err) => {
      if (!cancelled) setError(err instanceof ApiError ? err.message : 'Chargement impossible.')
    }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [mode, enrollmentId, activeOrganization?.id])

  const session = useMemo(
    () => sessions.find((item) => item.enrollment_id === selectedEnrollmentId) ?? null,
    [sessions, selectedEnrollmentId],
  )

  const onUpdated = useCallback((updated: LearningSession) => {
    setSessions((current) => current.map((item) => item.enrollment_id === updated.enrollment_id ? updated : item))
    setActiveLesson((current) => current ? findLesson(updated, current.id) : current)
  }, [])

  async function complete() {
    if (!activeLesson) return
    try { onUpdated(await completeStudentLesson(activeLesson.id)) }
    catch (err) { setError(err instanceof ApiError ? err.message : 'Validation impossible.') }
  }

  function selectSession(id: number) {
    setSelectedEnrollmentId(id)
    const selected = sessions.find((item) => item.enrollment_id === id)
    setActiveLesson(selected && !selected.is_locked ? firstLesson(selected) : null)
    const chapterId = selected?.courses[0]?.chapters[0]?.id
    setOpenChapters(chapterId ? new Set([chapterId]) : new Set())
  }

  function renderLesson(lesson: LearningLesson) {
    if (lesson.lesson_type === 'video' && lesson.video_url) return <TrackedLessonVideo key={lesson.id} lesson={lesson} onUpdated={onUpdated} onError={setError} />
    if (lesson.lesson_type === 'pdf' && lesson.quiz_id) return <PdfLessonReader key={lesson.id} lesson={lesson} onCompleted={() => {
      void listStudentLearning().then((rows) => {
        const updated = rows.find((item) => item.enrollment_id === selectedEnrollmentId)
        if (updated) onUpdated(updated)
      }).catch((caught) => setError(caught instanceof ApiError ? caught.message : 'Actualisation impossible.'))
    }} />
    return <>
      {lesson.content && <div className="student-reader-text">{lesson.content}</div>}
      {lesson.file_url && <a className="primary-button" href={lesson.file_url} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Ouvrir le document</a>}
      {lesson.quiz_id && <p>Réussissez le quiz pour valider cette leçon. <Link to={`/app/student/quizzes#quiz-${lesson.quiz_id}`}>Ouvrir le quiz lié</Link></p>}
      {lesson.assignment_id && <p>Déposez votre travail pour valider cette leçon. <Link to={`/app/student/assignments#assignment-${lesson.assignment_id}`}>Ouvrir le devoir lié</Link></p>}
      {!lesson.content && !lesson.file_url && !lesson.quiz_id && !lesson.assignment_id && <div className="student-reader-text">Aucun contenu textuel.</div>}
    </>
  }

  const title = mode === 'classic' ? 'Parcours classique' : mode === 'guided' ? 'Parcours guidé' : 'Mes cours'
  const canMarkComplete = activeLesson && !activeLesson.completed && !activeLesson.quiz_id && !activeLesson.assignment_id && !['video', 'quiz', 'assignment'].includes(activeLesson.lesson_type)

  return <main className="app-page student-reader-page">
    <header className="app-page-header">
      <div><span className="page-kicker">Espace étudiant</span><h1>{title}</h1><p>{mode === 'guided' ? 'Suivez les cours de votre session à mesure qu’ils deviennent disponibles.' : 'Avancez module par module dans votre formation.'}</p></div>
      {mode && <Link to="/app/student/formations">Tous mes parcours</Link>}
    </header>
    {error && <div className="form-error">{error}</div>}
    {loading && <div className="page-state">Chargement des cours…</div>}
    {!loading && !mode && sessions.length > 0 && <label className="academic-session-select">Formation
      <select value={selectedEnrollmentId ?? ''} onChange={(event) => selectSession(Number(event.target.value))}>
        {sessions.map((item) => <option key={item.enrollment_id} value={item.enrollment_id}>{item.formation_title} · {item.session_label} · {item.dashboard_type === 'classic' ? 'Classique' : 'Guidé'}</option>)}
      </select>
    </label>}
    {!loading && !session && <div className="app-card">{mode ? 'Parcours introuvable dans votre école.' : 'Aucune formation disponible.'}</div>}
    {session && <>
      <p>{session.formation_title} · {session.session_label} · {session.dashboard_type === 'classic' ? 'En ligne' : 'Guidé'}</p>
      {session.is_locked && <div className="student-reader-lock">Ce parcours ouvrira au début de la session{session.available_at ? `, le ${new Date(session.available_at).toLocaleDateString('fr-FR')}` : ''}.</div>}
      <section className="student-reader-layout">
        <aside className="app-card student-reader-nav">
          {session.courses.map((course) => <div key={course.id}>
            <h3>{course.title}</h3>
            {course.chapters.map((chapter) => {
              const open = openChapters.has(chapter.id)
              return <div className="student-reader-chapter" key={chapter.id}>
                <button type="button" onClick={() => setOpenChapters((current) => {
                  const next = new Set(current)
                  if (next.has(chapter.id)) next.delete(chapter.id)
                  else next.add(chapter.id)
                  return next
                })}>{open ? <ChevronDown size={14} /> : <ChevronRight size={14} />} Module {chapter.order_index + 1} · {chapter.title}</button>
                {open && <div>{chapter.lessons.map((lesson) => <button type="button" disabled={lesson.is_locked} className={activeLesson?.id === lesson.id ? 'is-active' : ''} key={lesson.id} onClick={() => setActiveLesson(lesson)} title={lesson.is_locked ? `Disponible ${lesson.available_at ? `le ${new Date(lesson.available_at).toLocaleString('fr-FR')}` : 'après publication de l’activité'}` : undefined}>{lesson.completed ? <CheckCircle2 size={13} /> : <PlayCircle size={13} />}<span>{lesson.title}{lesson.is_locked && ' · À venir'}</span></button>)}</div>}
              </div>
            })}
          </div>)}
          {session.courses.length === 0 && <p>Cours en préparation.</p>}
        </aside>
        <article className="app-card student-reader-content">
          {activeLesson && !session.is_locked ? <>
            <div className="student-reader-heading"><div><span className="section-label">{activeLesson.lesson_type}</span><h2>{activeLesson.title}</h2></div>{activeLesson.completed && <span className="assignment-status reviewed"><CheckCircle2 size={13} />Terminée</span>}</div>
            {renderLesson(activeLesson)}
            {canMarkComplete && <button type="button" className="primary-button student-complete-button" onClick={() => void complete()}><CheckCircle2 size={14} /> Marquer comme terminée</button>}
          </> : <div className="formation-empty">{session.is_locked ? 'Les leçons seront accessibles au début de la session.' : 'Sélectionnez une leçon.'}</div>}
        </article>
      </section>
    </>}
  </main>
}
