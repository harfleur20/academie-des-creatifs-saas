import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  ArrowLeft,
  CalendarClock,
  Clock3,
  Plus,
  UserRound,
  X,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import {
  ApiError,
  createSessionCourseDay,
  getSessionPlanning,
  listCourseDayFeedback,
  submitCourseDayReport,
  updateSessionCourseDay,
  type SessionPlanning,
  type CourseDayFeedbackReview,
} from '../lib/api'
import { liveClassIsOpen } from '../lib/liveWindow'
import { LiveRecordingsPanel } from '../components/LiveRecordingsPanel'

function toLocalInput(value: string) {
  const date = new Date(value)
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

export function TeacherSessionPlanningPage() {
  const { sessionId } = useParams()
  const id = Number(sessionId)
  const [planning, setPlanning] = useState<SessionPlanning | null>(null)
  const [title, setTitle] = useState('')
  const [scheduledAt, setScheduledAt] = useState('')
  const [duration, setDuration] = useState('90')
  const [working, setWorking] = useState(false)
  const [reportDayId, setReportDayId] = useState<number | null>(null)
  const [reportStatus, setReportStatus] = useState<'held' | 'partial' | 'not_held' | 'interrupted'>('held')
  const [reportSummary, setReportSummary] = useState('')
  const [reportDifficulties, setReportDifficulties] = useState('')
  const [reportHomework, setReportHomework] = useState('')
  const [reportAttendanceNotes, setReportAttendanceNotes] = useState('')
  const [feedbackDayId, setFeedbackDayId] = useState<number | null>(null)
  const [feedbackRows, setFeedbackRows] = useState<CourseDayFeedbackReview[]>([])
  const [error, setError] = useState('')

  async function refresh() {
    if (!Number.isInteger(id)) return
    try {
      setPlanning(await getSessionPlanning(id))
      setError('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de charger le planning.')
    }
  }

  useEffect(() => {
    void refresh()
  }, [id])

  const activeDays = useMemo(
    () => planning?.course_days.filter((item) => item.status !== 'cancelled') ?? [],
    [planning],
  )

  async function create(event: FormEvent) {
    event.preventDefault()
    if (!planning || !scheduledAt) return
    setWorking(true)
    setError('')
    try {
      const updated = await createSessionCourseDay(planning.session_id, {
        title: title.trim(),
        scheduled_at: new Date(scheduledAt).toISOString(),
        duration_minutes: Number(duration),
      })
      setPlanning(updated)
      setTitle('')
      setScheduledAt('')
      setDuration('90')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Création impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function cancelDay(dayId: number) {
    setWorking(true)
    setError('')
    try {
      setPlanning(await updateSessionCourseDay(dayId, { status: 'cancelled' }))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Modification impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function submitReport(event: FormEvent) {
    event.preventDefault()
    if (reportDayId === null) return
    setWorking(true)
    setError('')
    try {
      setPlanning(await submitCourseDayReport(reportDayId, {
        delivery_status: reportStatus, summary: reportSummary.trim(),
        difficulties: reportDifficulties.trim(), homework: reportHomework.trim(),
        attendance_notes: reportAttendanceNotes.trim(),
      }))
      setReportDayId(null)
      setReportSummary('')
      setReportDifficulties('')
      setReportHomework('')
      setReportAttendanceNotes('')
      setReportStatus('held')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Rapport impossible à enregistrer.')
    } finally {
      setWorking(false)
    }
  }

  async function showFeedback(dayId: number) {
    if (feedbackDayId === dayId) { setFeedbackDayId(null); return }
    setError('')
    try {
      setFeedbackRows(await listCourseDayFeedback(dayId))
      setFeedbackDayId(dayId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Avis impossibles à charger.')
    }
  }

  if (!planning && !error) {
    return <div className="page-state">Chargement du planning…</div>
  }

  return (
    <main className="app-page planning-page">
      <Link className="planning-back-link" to="/app/teacher/sessions">
        <ArrowLeft size={15} /> Mes sessions
      </Link>

      {planning && (
        <header className="app-page-header">
          <div>
            <span className="page-kicker">Planning pédagogique</span>
            <h1>{planning.formation_title}</h1>
            <p>
              {planning.session_label} · du{' '}
              {new Date(planning.session_start_date).toLocaleDateString('fr-FR')} au{' '}
              {new Date(planning.session_end_date).toLocaleDateString('fr-FR')}
            </p>
          </div>
          <span className="status-chip">{activeDays.length} séance(s)</span>
        </header>
      )}

      {error && <div className="form-error">{error}</div>}

      {planning && <nav className="teacher-session-tools app-card" aria-label="Outils de la session">
        <strong>Outils de la session</strong>
        <div>
          <Link to={`/app/teacher/courses?session=${id}`}>Cours</Link>
          <Link to={`/app/teacher/students?session=${id}`}>Étudiants</Link>
          <Link to={`/app/teacher/attendance?session=${id}`}>Présences</Link>
          <Link to={`/app/teacher/grades?session=${id}`}>Notes</Link>
          <Link to={`/app/teacher/assignments?session=${id}`}>Devoirs</Link>
          <Link to={`/app/teacher/quizzes?session=${id}`}>Quiz</Link>
          <Link to={`/app/teacher/resources?session=${id}`}>Ressources</Link>
        </div>
      </nav>}

      {planning && (
        <section className="planning-layout">
          <form className="app-card planning-create-card" onSubmit={create}>
            <div>
              <span className="section-label">Mon créneau</span>
              <h2>Planifier une séance</h2>
              <p>
                Ce créneau vous appartiendra. Les autres professeurs de la session pourront
                le voir mais pas le modifier.
              </p>
            </div>

            <label>
              Titre de la séance
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                minLength={2}
                maxLength={255}
                required
                placeholder="Ex. Principes du mouvement"
              />
            </label>

            <label>
              Date et heure
              <input
                type="datetime-local"
                value={scheduledAt}
                onChange={(event) => setScheduledAt(event.target.value)}
                min={`${planning.session_start_date}T00:00`}
                max={`${planning.session_end_date}T23:59`}
                required
              />
            </label>

            <label>
              Durée
              <select value={duration} onChange={(event) => setDuration(event.target.value)}>
                <option value="60">1 h</option>
                <option value="90">1 h 30</option>
                <option value="120">2 h</option>
                <option value="180">3 h</option>
                <option value="240">4 h</option>
              </select>
            </label>

            <button className="primary-button" disabled={working}>
              <Plus size={15} />
              {working ? 'Enregistrement…' : 'Ajouter au planning'}
            </button>
          </form>

          <section className="planning-list">
            {planning.course_days.map((day) => (
              <article
                className={`app-card planning-day-card ${day.status === 'cancelled' ? 'is-cancelled' : ''}`}
                key={day.id}
              >
                <div className="planning-day-date">
                  <strong>
                    {new Intl.DateTimeFormat('fr-FR', { day: '2-digit' }).format(new Date(day.scheduled_at))}
                  </strong>
                  <span>
                    {new Intl.DateTimeFormat('fr-FR', { month: 'short' }).format(new Date(day.scheduled_at))}
                  </span>
                </div>
                <div className="planning-day-main">
                  <div>
                    <span className="section-label">{day.status === 'cancelled' ? 'Annulée' : day.report_submitted_at ? 'Clôturée' : day.started_at ? 'Démarrée' : 'Planifiée'}</span>
                    <h3>{day.title}</h3>
                  </div>
                  <div className="planning-day-meta">
                    <span><Clock3 size={14} /> {new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' }).format(new Date(day.scheduled_at))} · {day.duration_minutes} min</span>
                    <span><UserRound size={14} /> {day.teacher_name || 'Professeur non disponible'}</span>
                  </div>
                </div>
                {planning.format_type === 'live' && day.status !== 'cancelled' && !day.report_submitted_at && (
                  !planning.live_enabled ? <small>Service live en cours de configuration.</small> : liveClassIsOpen(day) ? <Link className="secondary-button" to={`/app/teacher/live/${day.id}`}>Rejoindre la classe live</Link> : <small>La salle ouvre 15 minutes avant la séance.</small>
                )}
                {day.report_submitted_at && <small>Rapport remis · {day.delivery_status === 'held' ? 'Séance tenue' : day.delivery_status === 'partial' ? 'Séance partielle' : day.delivery_status === 'not_held' ? 'Séance non tenue' : 'Séance interrompue'}</small>}
                {day.report_submitted_at && (day.report_summary || day.report_difficulties || day.report_homework || day.report_attendance_notes) && <div className="planning-day-report">
                  <span className="planning-day-report__label">Compte rendu</span>
                  {day.report_summary && <p>{day.report_summary}</p>}
                  {day.report_difficulties && <p><strong>Difficultés :</strong> {day.report_difficulties}</p>}
                  {day.report_homework && <p><strong>Travail à faire :</strong> {day.report_homework}</p>}
                  {day.report_attendance_notes && <p><strong>Présences :</strong> {day.report_attendance_notes}</p>}
                </div>}
                {day.feedback_count > 0 && <button className="secondary-button planning-day-feedback" type="button" onClick={() => void showFeedback(day.id)}>{day.feedback_count} avis · {day.average_rating}/5</button>}
                {feedbackDayId === day.id && <div className="course-day-feedback-list">{feedbackRows.map((feedback) => <p key={feedback.id}><strong>{feedback.student_name}</strong> · {feedback.rating}/5 · {feedback.delivery_status === 'held' ? 'séance tenue' : feedback.delivery_status === 'partial' ? 'partielle' : 'non tenue'}{feedback.comment && <span> — {feedback.comment}</span>}</p>)}</div>}
                {day.can_edit && day.status !== 'cancelled' && Date.now() >= new Date(day.scheduled_at).getTime() + day.duration_minutes * 60_000 && <button className="secondary-button" type="button" onClick={() => {
                  setReportDayId(day.id); setReportStatus('held'); setReportSummary('')
                  setReportDifficulties(''); setReportHomework(''); setReportAttendanceNotes('')
                }}>Clôturer la séance</button>}
                {reportDayId === day.id && <form className="course-day-report-form" onSubmit={(event) => void submitReport(event)}>
                  <label>Déroulement<select value={reportStatus} onChange={(event) => setReportStatus(event.target.value as typeof reportStatus)}><option value="held">Séance tenue</option><option value="partial">Séance partielle</option><option value="not_held">Séance non tenue</option><option value="interrupted">Séance interrompue</option></select></label>
                  <label>Compte rendu<textarea minLength={10} maxLength={5000} required value={reportSummary} onChange={(event) => setReportSummary(event.target.value)} placeholder="Résumé de la séance et points à retenir" /></label>
                  <label>Difficultés rencontrées<textarea maxLength={2500} value={reportDifficulties} onChange={(event) => setReportDifficulties(event.target.value)} /></label>
                  <label>Travail à faire<textarea maxLength={2500} value={reportHomework} onChange={(event) => setReportHomework(event.target.value)} /></label>
                  <label>Notes sur les présences<textarea maxLength={2500} value={reportAttendanceNotes} onChange={(event) => setReportAttendanceNotes(event.target.value)} /></label>
                  {reportStatus !== 'not_held' && <small>{planning.format_type === 'live'
                    ? 'Les étudiants entrés en salle live sont marqués présents, ou en retard au-delà de 15 minutes ; les autres étudiants non marqués dans « Présences » seront enregistrés absents.'
                    : 'Les étudiants non marqués dans « Présences » seront enregistrés absents.'} Vous pourrez corriger les présences pendant 24 h après ce rapport.</small>}
                  <div><button className="primary-button" type="submit" disabled={working || reportSummary.trim().length < 10}>Remettre le rapport</button><button className="secondary-button" type="button" onClick={() => setReportDayId(null)}>Annuler</button></div>
                </form>}
                {day.can_edit && day.status !== 'cancelled' && !day.started_at && (
                  <button
                    className="planning-cancel-button"
                    type="button"
                    disabled={working}
                    onClick={() => void cancelDay(day.id)}
                    title="Annuler cette séance"
                  >
                    <X size={16} />
                  </button>
                )}
              </article>
            ))}

            {planning.course_days.length === 0 && (
              <div className="app-card formation-empty">
                <CalendarClock size={28} />
                <strong>Aucune séance planifiée</strong>
                <p>Ajoutez votre premier créneau pour construire le planning commun.</p>
              </div>
            )}
          </section>
        </section>
      )}
      {planning?.format_type === 'live' && (
        <LiveRecordingsPanel
          sessionId={planning.session_id}
          canManage
          finishedDayIds={new Set(planning.course_days.filter((day) => Boolean(day.report_submitted_at)).map((day) => day.id))}
        />
      )}
    </main>
  )
}
