import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { BookOpen, CalendarDays, ChevronLeft, ChevronRight, GraduationCap, MonitorPlay, Users } from 'lucide-react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import { ApiError, ATTENDANCE_LABELS, getSessionPlanning, getStudentWorkspace, listPublicSchoolFormations, listStudentAssignments, listStudentAttendance, listStudentGrades, listStudentLearning, listStudentProgress, listStudentQuizzes, listStudentResources, submitCourseDayFeedback,
  type AcademicResource, type CourseDay, type LearningSession, type SessionPlanning, type StudentAssignment, type StudentAttendance, type StudentGrade, type StudentProgress, type StudentQuiz, type StudentWorkspaceSession } from '../lib/api'
import { liveClassIsOpen } from '../lib/liveWindow'
import { formatDuration } from '../lib/formatDuration'

type Tab = 'overview' | 'program' | 'calendar' | 'schedule' | 'assignments' | 'quizzes' | 'resources' | 'results'
const tabs: Array<{ id: Tab; label: string }> = [
  { id: 'overview', label: 'Vue d’ensemble' }, { id: 'program', label: 'Programme' },
  { id: 'calendar', label: 'Calendrier' }, { id: 'schedule', label: 'Emploi du temps' },
  { id: 'assignments', label: 'Devoirs' },
  { id: 'quizzes', label: 'Quiz' }, { id: 'resources', label: 'Ressources' }, { id: 'results', label: 'Notes' },
]
const dateLabel = (value: string) => new Date(value).toLocaleString(activeSchoolLocale(), { dateStyle: 'medium', timeStyle: 'short' })

function startOfWeek(value: Date) {
  const date = new Date(value)
  date.setHours(0, 0, 0, 0)
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7))
  return date
}

function addDays(value: Date, count: number) {
  const date = new Date(value)
  date.setDate(date.getDate() + count)
  return date
}

function localDateKey(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function courseDayTimeRange(day: CourseDay) {
  const start = new Date(day.scheduled_at)
  const end = new Date(start.getTime() + day.duration_minutes * 60_000)
  const time = (value: Date) => value.toLocaleTimeString(activeSchoolLocale(), { hour: '2-digit', minute: '2-digit' })
  return `${time(start)} – ${time(end)}`
}

export function StudentGuidedWorkspacePage() {
  const { activeOrganization } = useTenant()
  const { enrollmentId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedTab = searchParams.get('tab')
  const tab: Tab = tabs.some((item) => item.id === requestedTab) ? requestedTab as Tab : 'overview'
  const [session, setSession] = useState<LearningSession | null>(null)
  const [workspaceSession, setWorkspaceSession] = useState<StudentWorkspaceSession | null>(null)
  const [planning, setPlanning] = useState<SessionPlanning | null>(null)
  const [attendance, setAttendance] = useState<StudentAttendance[]>([])
  const [assignments, setAssignments] = useState<StudentAssignment[]>([])
  const [quizzes, setQuizzes] = useState<StudentQuiz[]>([])
  const [resources, setResources] = useState<AcademicResource[]>([])
  const [grades, setGrades] = useState<StudentGrade[]>([])
  const [progress, setProgress] = useState<StudentProgress | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()))
  const [feedbackDayId, setFeedbackDayId] = useState<number | null>(null)
  const [feedbackRating, setFeedbackRating] = useState(5)
  const [feedbackDelivery, setFeedbackDelivery] = useState<'held' | 'partial' | 'not_held'>('held')
  const [feedbackComment, setFeedbackComment] = useState('')
  const [feedbackSaving, setFeedbackSaving] = useState(false)

  async function saveFeedback(event: FormEvent) {
    event.preventDefault()
    if (feedbackDayId === null) return
    setFeedbackSaving(true)
    setError('')
    try {
      setPlanning(await submitCourseDayFeedback(feedbackDayId, {
        rating: feedbackRating, delivery_status: feedbackDelivery, comment: feedbackComment.trim(),
      }))
      setFeedbackDayId(null)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Avis impossible à enregistrer.')
    } finally {
      setFeedbackSaving(false)
    }
  }

  useEffect(() => {
    if (!activeOrganization) { setSession(null); return }
    const organizationSlug = activeOrganization.slug
    let cancelled = false
    setLoading(true)
    setSession(null)
    setError('')
    async function load() {
      try {
        const learning = await listStudentLearning()
        const selected = learning.find((item) => item.enrollment_id === Number(enrollmentId) && item.dashboard_type === 'guided')
        if (!selected) throw new Error('Parcours guidé introuvable dans votre école.')
        const [days, attendanceRows, assignmentRows, quizRows, resourceRows, gradeRows, progressRows, workspace] = await Promise.all([
          getSessionPlanning(selected.session_id), listStudentAttendance(), listStudentAssignments(), listStudentQuizzes(), listStudentResources(), listStudentGrades(), listStudentProgress(), getStudentWorkspace(),
        ])
        let selectedWorkspaceSession = workspace.sessions.find((item) => item.enrollment_id === selected.enrollment_id) ?? null
        if (selectedWorkspaceSession && !selectedWorkspaceSession.formation_image) {
          const catalogue = await listPublicSchoolFormations(organizationSlug).catch(() => [])
          const cover = catalogue.find((formation) => formation.id === selected.formation_id)?.cover_image_url
          if (cover) selectedWorkspaceSession = { ...selectedWorkspaceSession, formation_image: cover }
        }
        if (cancelled) return
        setSession(selected)
        setWorkspaceSession(selectedWorkspaceSession)
        setPlanning(days)
        setAttendance(attendanceRows.filter((row) => days.course_days.some((day) => day.id === row.course_day_id)))
        setAssignments(assignmentRows.filter((row) => row.enrollment_id === selected.enrollment_id))
        setQuizzes(quizRows.filter((row) => row.enrollment_id === selected.enrollment_id))
        setResources(resourceRows.filter((row) => row.session_id === selected.session_id))
        setGrades(gradeRows.filter((row) => row.session_id === selected.session_id))
        setProgress(progressRows.find((row) => row.enrollment_id === selected.enrollment_id) ?? null)
      } catch (caught) {
        if (!cancelled) setError(caught instanceof ApiError || caught instanceof Error ? caught.message : 'Chargement impossible.')
      } finally { if (!cancelled) setLoading(false) }
    }
    void load()
    return () => { cancelled = true }
  }, [enrollmentId, activeOrganization?.id])

  const days = useMemo(() => (planning?.course_days ?? []).filter((day) => day.status !== 'cancelled'), [planning])
  const weekDays = useMemo(() => Array.from({ length: 7 }, (_, index) => {
    const date = addDays(weekStart, index)
    const key = localDateKey(date)
    const entries = days
      .filter((day) => localDateKey(new Date(day.scheduled_at)) === key)
      .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
    return { date, entries }
  }), [days, weekStart])
  const weekEnd = addDays(weekStart, 6)
  const weekRange = `Semaine du ${weekStart.toLocaleDateString(activeSchoolLocale(), { dateStyle: 'medium' })} au ${weekEnd.toLocaleDateString(activeSchoolLocale(), { dateStyle: 'medium' })}`
  const nextDay = days.find((day) => new Date(day.scheduled_at).getTime() >= Date.now())
  const pendingAssignments = assignments.filter((item) => item.student_status === 'pending' || item.student_status === 'late')
  const activeQuizzes = quizzes.filter((item) => !item.is_locked && !item.passed && item.can_attempt)
  const gradePoints = grades.reduce((sum, grade) => sum + grade.score, 0)
  const gradeMaximum = grades.reduce((sum, grade) => sum + grade.max_score, 0)
  const gradeAverage = gradeMaximum > 0 ? (gradePoints / gradeMaximum * 20).toFixed(1) : null
  const readerUrl = `/app/student/guided/${enrollmentId}/program`
  const teacherName = workspaceSession?.teacher_name || session?.courses.find((course) => course.teacher_name)?.teacher_name || null
  const teacherAvatarUrl = workspaceSession?.teacher_avatar_url
    || session?.courses.find((course) => course.teacher_name === teacherName && course.teacher_avatar_url)?.teacher_avatar_url
    || null

  return <main className="app-page guided-workspace-page">
    {!session && <header className="app-page-header"><div><span className="page-kicker">Parcours guidé</span><h1>Mon parcours</h1></div></header>}
    {error && <div className="form-error">{error}</div>}
    {loading && <div className="page-state">Chargement du parcours…</div>}
    {session && <>
      <section className="guided-course-hero">
        <div className="guided-course-hero__copy">
          <span>PARCOURS {session.format_type === 'presentiel' ? 'PRÉSENTIEL' : 'LIVE'}</span>
          <h1>{session.formation_title}</h1>
          <p>Votre cohorte, les séances, les supports, les quiz et les corrections au même endroit.</p>
          <div className="guided-course-hero__actions"><Link to="/app/student/formations">Retour à mes parcours</Link><button type="button" onClick={() => setSearchParams({ tab: 'program' })}>Voir le programme <ChevronRight size={17} aria-hidden="true" /></button></div>
          {teacherName && <div className="guided-course-hero__teacher">{teacherAvatarUrl ? <img src={teacherAvatarUrl} alt="" /> : <span aria-hidden="true">{teacherName.trim().charAt(0)}</span>}<div><small>Votre enseignant</small><strong>{teacherName}</strong></div></div>}
        </div>
        <div className="guided-course-hero__media">{workspaceSession?.formation_image ? <img src={workspaceSession.formation_image} alt="" /> : <GraduationCap size={70} aria-hidden="true" />}</div>
      </section>
      <div className="guided-course-facts">
        <article><MonitorPlay size={21} aria-hidden="true" /><span>Format</span><strong>{session.format_type === 'presentiel' ? 'Présentiel' : 'Live'}</strong><small>{session.format_type === 'presentiel' ? 'Cours et présence sur place' : 'Cours en direct et supports synchronisés'}</small></article>
        <article><CalendarDays size={21} aria-hidden="true" /><span>Session</span><strong>{session.session_label}</strong><small>{nextDay ? `Prochain cours : ${dateLabel(nextDay.scheduled_at)}` : 'Consultez le calendrier des cours'}</small></article>
        <article><Users size={21} aria-hidden="true" /><span>Enseignant</span><strong>{teacherName || 'Équipe pédagogique'}</strong><small>{session.courses.length} cours dans ce parcours</small></article>
      </div>
      {session.is_locked && <div className="student-reader-lock">Les cours ouvriront au début de la session{session.available_at ? `, le ${dateLabel(session.available_at)}` : ''}.</div>}
      <div className="guided-summary-grid">
        <article className="app-card"><span className="section-label">Progression</span><strong>{progress?.lesson_progress_pct ?? 0} %</strong><p>{progress?.completed_lessons ?? 0} / {progress?.total_lessons ?? 0} leçons terminées</p></article>
        <article className="app-card"><span className="section-label">Prochaine séance</span><strong>{nextDay ? dateLabel(nextDay.scheduled_at) : 'À venir'}</strong><p>{nextDay?.title || 'Le calendrier sera publié par l’école.'}</p></article>
        <article className="app-card"><span className="section-label">Suivi</span><strong>{pendingAssignments.length} devoir(s) à rendre</strong><p>{activeQuizzes.length} quiz disponible(s)</p></article>
      </div>
      <section className="guided-pedagogy"><header><BookOpen size={21} aria-hidden="true" /><div><h2>Espace pédagogique</h2><p>Tout est filtré sur cette formation et cette session.</p></div></header>
      <nav className="guided-tabs" aria-label="Sections du parcours">{tabs.map((item) => <button type="button" key={item.id} className={tab === item.id ? 'is-active' : ''} aria-current={tab === item.id ? 'page' : undefined} onClick={() => setSearchParams({ tab: item.id })}>{item.label}</button>)}</nav>
      <section className="app-card guided-panel">
        {tab === 'overview' && <><h2>Vue d’ensemble</h2><p>{session.courses.length} cours publié(s) · {days.length} séance(s) · {resources.length} ressource(s)</p><p>{gradeAverage !== null ? `Moyenne : ${gradeAverage} / 20` : 'Aucune note disponible.'}</p><div className="guided-actions"><Link className="primary-button" to={readerUrl}>Ouvrir le programme</Link><Link className="secondary-button" to={`/app/student/class?session=${session.session_id}`}>Ma classe</Link><Link className="secondary-button" to="/app/student/certificates">Mes certificats</Link></div></>}
        {tab === 'program' && <><h2>Programme</h2>{session.courses.map((course) => <div className="guided-course" key={course.id}><h3>{course.title}</h3><p>{course.teacher_name || 'Équipe pédagogique'} · {course.chapters.reduce((sum, chapter) => sum + chapter.lessons.length, 0)} leçon(s)</p>{course.chapters.map((chapter) => <p key={chapter.id}>Module {chapter.order_index + 1} · {chapter.title} · {chapter.lessons.filter((lesson) => lesson.completed).length}/{chapter.lessons.length} terminée(s)</p>)}</div>)}{session.courses.length === 0 && <p>Les cours sont en préparation.</p>}<Link className="primary-button" to={readerUrl}>Lire les leçons</Link></>}
        {tab === 'calendar' && <><h2>Calendrier et présences</h2>{days.map((day) => {
          const presence = attendance.find((row) => row.course_day_id === day.id)
          const presenceLabel = !day.report_submitted_at ? 'Présence à confirmer'
            : day.delivery_status === 'not_held' ? 'Séance non tenue'
              : day.delivery_status === 'interrupted' ? 'Séance interrompue'
                : `${day.delivery_status === 'partial' ? 'Séance partielle · ' : ''}${ATTENDANCE_LABELS[presence?.status ?? 'absent']}`
          return <div className="guided-list-row" key={day.id}>
            <strong>{day.title}</strong><span>{dateLabel(day.scheduled_at)} · {formatDuration(day.duration_minutes)}</span><small>{presenceLabel}</small>
            {session.format_type === 'live' && day.started_at && !day.report_submitted_at && <small>Cours démarré</small>}
            {session.format_type === 'live' && !day.report_submitted_at && (!planning?.live_enabled ? <small>Service live en cours de configuration.</small> : liveClassIsOpen(day) ? <Link to={`/app/student/live/${day.id}`}>Rejoindre la classe live</Link> : <small>La salle ouvre 15 minutes avant la séance.</small>)}
            {day.feedback_count > 0 && <small>{day.feedback_count} avis · note moyenne {day.average_rating}/5</small>}
            {day.my_feedback && <small>Votre avis : {day.my_feedback.rating}/5 · {day.my_feedback.delivery_status === 'held' ? 'tenue' : day.my_feedback.delivery_status === 'partial' ? 'partielle' : 'non tenue'}</small>}
            {Date.now() >= new Date(day.scheduled_at).getTime() + day.duration_minutes * 60_000 && <button className="secondary-button" type="button" onClick={() => {
              setFeedbackDayId(day.id)
              setFeedbackRating(day.my_feedback?.rating ?? 5)
              setFeedbackDelivery(day.my_feedback?.delivery_status ?? 'held')
              setFeedbackComment(day.my_feedback?.comment ?? '')
            }}>{day.my_feedback ? 'Modifier mon avis' : 'Donner mon avis'}</button>}
            {feedbackDayId === day.id && <form className="course-day-report-form" onSubmit={(event) => void saveFeedback(event)}>
              <label>Note<select value={feedbackRating} onChange={(event) => setFeedbackRating(Number(event.target.value))}>{[5, 4, 3, 2, 1].map((rating) => <option key={rating} value={rating}>{rating}/5</option>)}</select></label>
              <label>La séance a-t-elle eu lieu ?<select value={feedbackDelivery} onChange={(event) => setFeedbackDelivery(event.target.value as typeof feedbackDelivery)}><option value="held">Oui</option><option value="partial">En partie</option><option value="not_held">Non</option></select></label>
              <label>Commentaire facultatif<textarea maxLength={1000} value={feedbackComment} onChange={(event) => setFeedbackComment(event.target.value)} /></label>
              <div><button className="primary-button" type="submit" disabled={feedbackSaving}>Enregistrer mon avis</button><button className="secondary-button" type="button" onClick={() => setFeedbackDayId(null)}>Annuler</button></div>
            </form>}
          </div>
        })}{days.length === 0 && <p>Le calendrier est en préparation.</p>}</>}
        {tab === 'schedule' && <>
          <h2>Emploi du temps</h2>
          <div className="guided-week-toolbar">
            <div className="guided-week-navigation">
              <button type="button" className="guided-week-button" aria-label="Semaine précédente" onClick={() => setWeekStart((current) => addDays(current, -7))}>
                <ChevronLeft size={17} aria-hidden="true" />
              </button>
              <strong>{weekRange}</strong>
              <button type="button" className="guided-week-button" aria-label="Semaine suivante" onClick={() => setWeekStart((current) => addDays(current, 7))}>
                <ChevronRight size={17} aria-hidden="true" />
              </button>
              <button type="button" className="guided-week-button guided-week-today" onClick={() => setWeekStart(startOfWeek(new Date()))}>Cette semaine</button>
            </div>
          </div>
          <div className="guided-week-scroll" role="region" aria-label="Programme de la semaine sur sept jours" tabIndex={0}>
            <div className="guided-week-grid">
              {weekDays.map(({ date, entries }) => {
                const weekday = date.toLocaleDateString(activeSchoolLocale(), { weekday: 'long' })
                const isToday = localDateKey(date) === localDateKey(new Date())
                return (
                  <article className={`guided-week-day${isToday ? ' is-today' : ''}`} key={localDateKey(date)}>
                    <header className="guided-week-day__heading">
                      <span>{weekday.charAt(0).toLocaleUpperCase(activeSchoolLocale())}{weekday.slice(1)}</span>
                      <strong>{date.getDate()}</strong>
                    </header>
                    <div className="guided-week-day__events">
                      {entries.map((day) => (
                        <article className="guided-week-event" key={day.id}>
                          <time dateTime={day.scheduled_at}>{courseDayTimeRange(day)}</time>
                          <strong>{day.title}</strong>
                          <small>{formatDuration(day.duration_minutes)} · {session.format_type === 'presentiel' ? 'Présentiel' : session.format_type === 'live' ? 'En direct' : 'En ligne'}</small>
                          <small>Prof. {day.teacher_name || 'À confirmer'}</small>
                          {session.format_type === 'live' && planning?.live_enabled && liveClassIsOpen(day) && <Link to={`/app/student/live/${day.id}`}>Rejoindre</Link>}
                        </article>
                      ))}
                      {entries.length === 0 && <p className="guided-week-empty">Aucun cours</p>}
                    </div>
                  </article>
                )
              })}
            </div>
          </div>
        </>}
        {tab === 'assignments' && <><h2>Devoirs</h2>{assignments.map((item) => <div className="guided-list-row" key={item.id}><strong>{item.title}</strong><span>À rendre le {dateLabel(item.due_date)}</span><small>{item.is_locked ? 'À venir' : item.student_status === 'submitted' ? 'Rendu' : item.student_status === 'reviewed' ? 'Corrigé' : item.student_status === 'late' ? 'En retard' : 'À rendre'}</small><Link to={`/app/student/assignments#assignment-${item.id}`}>Ouvrir</Link></div>)}{assignments.length === 0 && <p>Aucun devoir pour cette session.</p>}</>}
        {tab === 'quizzes' && <><h2>Quiz</h2>{quizzes.map((item) => <div className="guided-list-row" key={item.id}><strong>{item.title}</strong><small>{item.passed ? 'Réussi' : item.is_locked ? 'À venir' : item.can_attempt ? 'Disponible' : 'Réessai indisponible'}</small><Link to={`/app/student/quizzes#quiz-${item.id}`}>Ouvrir</Link></div>)}{quizzes.length === 0 && <p>Aucun quiz pour cette session.</p>}</>}
        {tab === 'resources' && <><h2>Ressources</h2>{resources.map((item) => <div className="guided-list-row" key={item.id}><strong>{item.title}</strong><span>{item.resource_type}</span><Link to="/app/student/resources">Consulter</Link></div>)}{resources.length === 0 && <p>Aucune ressource publiée.</p>}</>}
        {tab === 'results' && <><h2>Notes et résultats</h2><p>{gradeAverage !== null ? `Moyenne : ${gradeAverage} / 20` : 'Aucune note disponible.'}</p>{grades.map((grade) => <div className="guided-list-row" key={grade.id}><strong>{grade.label}</strong><span>{grade.score} / {grade.max_score}</span></div>)}<Link to="/app/student/progress">Voir mon suivi complet</Link></>}
      </section></section>
    </>}
  </main>
}
