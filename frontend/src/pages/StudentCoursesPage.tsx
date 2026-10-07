import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { BookOpen, CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, ExternalLink, LockKeyhole, PlayCircle } from 'lucide-react'
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
  const [openCourses, setOpenCourses] = useState<Set<number>>(new Set())
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
    setOpenCourses(new Set())
    setOpenChapters(new Set())
    listStudentLearning().then((rows) => {
      if (cancelled) return
      setSessions(rows)
      const selected = mode
        ? rows.find((item) => item.enrollment_id === Number(enrollmentId) && item.dashboard_type === mode)
        : rows.length === 1 ? rows[0] : undefined
      setSelectedEnrollmentId(selected?.enrollment_id ?? null)
    }).catch((err) => {
      if (!cancelled) setError(err instanceof ApiError ? err.message : 'Chargement impossible.')
    }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [mode, enrollmentId, activeOrganization?.id])

  const session = useMemo(
    () => sessions.find((item) => item.enrollment_id === selectedEnrollmentId) ?? null,
    [sessions, selectedEnrollmentId],
  )

  const accessibleLessons = useMemo(
    () => session
      ? session.courses.flatMap((course) => course.chapters.flatMap((chapter) => chapter.lessons)).filter((lesson) => !lesson.is_locked)
      : [],
    [session],
  )
  const activeIndex = activeLesson ? accessibleLessons.findIndex((lesson) => lesson.id === activeLesson.id) : -1
  const previousLesson = activeIndex > 0 ? accessibleLessons[activeIndex - 1] : null
  const nextLesson = activeIndex >= 0 && activeIndex < accessibleLessons.length - 1 ? accessibleLessons[activeIndex + 1] : null

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
    setActiveLesson(null)
    setOpenCourses(new Set())
    setOpenChapters(new Set())
  }

  function selectLesson(lesson: LearningLesson, courseId: number, chapterId: number) {
    if (lesson.is_locked) return
    setActiveLesson(lesson)
    setOpenCourses((current) => new Set(current).add(courseId))
    setOpenChapters((current) => new Set(current).add(chapterId))
  }

  function navigateToLesson(lesson: LearningLesson | null) {
    if (!lesson || !session) return
    for (const course of session.courses) {
      for (const chapter of course.chapters) {
        if (chapter.lessons.some((candidate) => candidate.id === lesson.id)) {
          selectLesson(lesson, course.id, chapter.id)
          return
        }
      }
    }
  }

  function renderLesson(lesson: LearningLesson) {
    if (lesson.lesson_type === 'video' && lesson.video_url) {
      return <TrackedLessonVideo key={lesson.id} lesson={lesson} onUpdated={onUpdated} onError={setError} />
    }
    if (lesson.lesson_type === 'pdf' && lesson.quiz_id) {
      return <PdfLessonReader key={lesson.id} lesson={lesson} onCompleted={() => {
        void listStudentLearning().then((rows) => {
          const updated = rows.find((item) => item.enrollment_id === selectedEnrollmentId)
          if (updated) onUpdated(updated)
        }).catch((caught) => setError(caught instanceof ApiError ? caught.message : 'Actualisation impossible.'))
      }} />
    }
    return <>
      {lesson.content && <div className="student-reader-text">{lesson.content}</div>}
      {lesson.file_url && <a className="dsh-btn dsh-btn--primary" href={lesson.file_url} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Ouvrir le document</a>}
      {lesson.quiz_id && <p>Réussissez le quiz pour valider cette leçon. <Link to={`/app/student/quizzes#quiz-${lesson.quiz_id}`}>Ouvrir le quiz lié</Link></p>}
      {lesson.assignment_id && <p>Déposez votre travail pour valider cette leçon. <Link to={`/app/student/assignments#assignment-${lesson.assignment_id}`}>Ouvrir le devoir lié</Link></p>}
      {!lesson.content && !lesson.file_url && !lesson.quiz_id && !lesson.assignment_id && <div className="student-reader-text">Aucun contenu textuel.</div>}
    </>
  }

  const title = mode === 'classic' ? 'Parcours classique' : mode === 'guided' ? 'Parcours guidé' : 'Mes cours'
  const canMarkComplete = activeLesson && !activeLesson.completed && !activeLesson.quiz_id && !activeLesson.assignment_id && !['video', 'quiz', 'assignment'].includes(activeLesson.lesson_type)

  if (loading) return <main className="app-page"><div className="dsh-empty">Chargement des cours…</div></main>

  if (!mode && sessions.length > 1 && selectedEnrollmentId === null) {
    return <main className="app-page student-reader-page">
      <div className="dsh-page">
        <div className="dsh-page__header">
          <h1>Mes cours</h1>
          <p className="dsh-page__subtitle">Choisissez une formation pour accéder à son contenu.</p>
        </div>
        {error && <div className="dsh-error">{error}</div>}
        <div className="cv-picker-grid">
          {sessions.map((item) => {
            const lessons = item.courses.flatMap((course) => course.chapters.flatMap((chapter) => chapter.lessons))
            const completed = lessons.filter((lesson) => lesson.completed).length
            const pct = lessons.length ? Math.round((completed / lessons.length) * 100) : 0
            return <button className="cv-picker-card" type="button" key={item.enrollment_id} onClick={() => selectSession(item.enrollment_id)}>
              <div className="cv-picker-card__header">
                <span className="cv-picker-card__session">{item.session_label}</span>
                <h2 className="cv-picker-card__title">{item.formation_title}</h2>
                <span className="cv-picker-card__meta">{item.courses.length} module{item.courses.length > 1 ? 's' : ''} · {lessons.length} leçon{lessons.length > 1 ? 's' : ''}</span>
              </div>
              <div className="cv-picker-card__progress">
                <div className="cv-picker-card__progress-label"><span>{completed}/{lessons.length} terminées</span><strong>{pct}%</strong></div>
                <div className="cv-progress-bar"><span className="cv-progress-bar__fill" style={{ width: `${pct}%` }} /></div>
              </div>
              <span className="cv-picker-card__cta">Ouvrir le lecteur →</span>
            </button>
          })}
        </div>
      </div>
    </main>
  }

  if (!session) {
    return <main className="app-page student-reader-page">
      <div className="dsh-page">
        <div className="dsh-page__header"><h1>{title}</h1></div>
        {error && <div className="dsh-error">{error}</div>}
        <div className="dsh-empty">{mode ? 'Parcours introuvable dans votre école.' : 'Aucune formation disponible.'}</div>
      </div>
    </main>
  }

  return <main className="app-page student-reader-page">
    {error && <div className="dsh-error">{error}</div>}
    {session.is_locked && <div className="student-reader-lock">Ce parcours ouvrira au début de la session{session.available_at ? `, le ${new Date(session.available_at).toLocaleDateString('fr-FR')}` : ''}.</div>}

    <div className="dsh-page cv-layout">
      <aside className="cv-sidebar">
        {!mode && sessions.length > 1 && (
          <button type="button" className="cv-back-btn" onClick={() => selectSession(0)}>
            <ChevronLeft size={14} /> Changer de formation
          </button>
        )}
        {mode && <Link className="cv-back-btn" to="/app/student/formations"><ChevronLeft size={14} /> Tous mes parcours</Link>}

        <div className="cv-formation-head">
          <span className="cv-formation-head__label">{session.session_label} · {session.dashboard_type === 'classic' ? 'En ligne' : 'Guidé'}</span>
          <strong>{session.formation_title}</strong>
        </div>

        {session.courses.map((course, courseIndex) => {
          const courseOpen = openCourses.has(course.id)
          const courseLessons = course.chapters.flatMap((chapter) => chapter.lessons)
          const completed = courseLessons.filter((lesson) => lesson.completed).length
          const pct = courseLessons.length ? Math.round((completed / courseLessons.length) * 100) : 0
          return <div className="cv-course-block" key={course.id}>
            <button
              type="button"
              className="cv-progress-row"
              onClick={() => setOpenCourses((current) => {
                const next = new Set(current)
                if (next.has(course.id)) next.delete(course.id)
                else next.add(course.id)
                return next
              })}
            >
              <span className="cv-progress-row__caret">{courseOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</span>
              <span className="cv-progress-row__info">
                <strong>Module {courseIndex + 1} : {course.title}</strong>
                <span className="cv-progress-bar"><span className="cv-progress-bar__fill" style={{ width: `${pct}%` }} /></span>
                <span className="cv-progress-row__pct">{completed}/{courseLessons.length} leçons · {pct}%</span>
              </span>
            </button>

            {courseOpen && course.chapters.map((chapter, chapterIndex) => {
              const chapterOpen = openChapters.has(chapter.id)
              const allDone = chapter.lessons.length > 0 && chapter.lessons.every((lesson) => lesson.completed)
              return <div className="cv-chapter-block" key={chapter.id}>
                <button
                  type="button"
                  className="cv-chapter-header"
                  onClick={() => setOpenChapters((current) => {
                    const next = new Set(current)
                    if (next.has(chapter.id)) next.delete(chapter.id)
                    else next.add(chapter.id)
                    return next
                  })}
                >
                  <span className="cv-chapter-header__caret">{chapterOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}</span>
                  <span className={`cv-chapter-header__title${allDone ? ' is-done' : ''}`}>Chapitre {chapterIndex + 1} : {chapter.title}</span>
                  {allDone && <CheckCircle2 size={12} />}
                </button>

                {chapterOpen && chapter.lessons.map((lesson, lessonIndex) => (
                  <button
                    type="button"
                    className={`cv-lesson-item${activeLesson?.id === lesson.id ? ' is-active' : ''}${lesson.completed ? ' is-done' : ''}${lesson.is_locked ? ' is-locked' : ''}`}
                    key={lesson.id}
                    onClick={() => selectLesson(lesson, course.id, chapter.id)}
                    title={lesson.is_locked ? `Disponible ${lesson.available_at ? `le ${new Date(lesson.available_at).toLocaleString('fr-FR')}` : 'plus tard'}` : undefined}
                  >
                    <span className="cv-lesson-item__check">{lesson.completed ? <CheckCircle2 size={13} /> : <PlayCircle size={12} />}</span>
                    <span className="cv-lesson-item__label">Leçon {lessonIndex + 1} : {lesson.title}</span>
                    <span className="cv-lesson-item__type">{lesson.is_locked ? <LockKeyhole size={13} /> : lesson.lesson_type}</span>
                  </button>
                ))}
              </div>
            })}
          </div>
        })}

        {session.courses.length === 0 && <p className="cv-sidebar-empty">Cours en préparation.</p>}
      </aside>

      <section className="cv-content">
        {!activeLesson || session.is_locked ? (
          <div className="cv-welcome">
            <BookOpen size={40} />
            <p>{session.is_locked ? 'Les leçons seront accessibles au début de la session.' : 'Sélectionnez une leçon dans le menu pour commencer.'}</p>
          </div>
        ) : (
          <>
            <div className="student-reader-heading">
              <div><span className="section-label">{activeLesson.lesson_type}</span><h2>{activeLesson.title}</h2></div>
              {activeLesson.completed && <span className="dsh-badge dsh-badge--green"><CheckCircle2 size={12} /> Terminée</span>}
            </div>

            {renderLesson(activeLesson)}

            {canMarkComplete && (
              <button type="button" className="dsh-btn dsh-btn--primary student-complete-button" onClick={() => void complete()}>
                <CheckCircle2 size={14} /> Marquer comme terminée
              </button>
            )}

            <div className="cv-lesson-nav">
              <button className="dsh-btn dsh-btn--ghost" type="button" disabled={!previousLesson} onClick={() => navigateToLesson(previousLesson)}>
                <ChevronLeft size={14} /> Précédent
              </button>
              <button className="dsh-btn dsh-btn--primary" type="button" disabled={!nextLesson} onClick={() => navigateToLesson(nextLesson)}>
                Suivant <ChevronRight size={14} />
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  </main>
}
