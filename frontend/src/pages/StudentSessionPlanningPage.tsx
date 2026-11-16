import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  CalendarClock,
  Clock3,
  UserRound,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import {
  ApiError,
  getSessionPlanning,
  type SessionPlanning,
} from '../lib/api'
import { formatDuration } from '../lib/formatDuration'
import { liveClassIsOpen } from '../lib/liveWindow'

export function StudentSessionPlanningPage() {
  const { sessionId } = useParams()
  const id = Number(sessionId)
  const [planning, setPlanning] = useState<SessionPlanning | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!Number.isInteger(id)) return
    getSessionPlanning(id)
      .then(setPlanning)
      .catch((err) => setError(
        err instanceof ApiError ? err.message : 'Impossible de charger votre planning.',
      ))
  }, [id])

  if (!planning && !error) {
    return <div className="page-state">Chargement de votre planning…</div>
  }

  return (
    <main className="app-page planning-page">
      <Link className="planning-back-link" to="/app/student/formations">
        <ArrowLeft size={15} /> Mes formations
      </Link>

      {planning && (
        <header className="app-page-header">
          <div>
            <span className="page-kicker">Mon planning</span>
            <h1>{planning.formation_title}</h1>
            <p>{planning.session_label}</p>
          </div>
        </header>
      )}

      {error && <div className="form-error">{error}</div>}

      {planning && (
        <section className="planning-list student-planning-list">
          {planning.course_days
            .filter((day) => day.status !== 'cancelled')
            .map((day) => (
              <article className="app-card planning-day-card" key={day.id}>
                <div className="planning-day-date">
                  <strong>
                    {new Intl.DateTimeFormat(activeSchoolLocale(), { day: '2-digit' }).format(new Date(day.scheduled_at))}
                  </strong>
                  <span>
                    {new Intl.DateTimeFormat(activeSchoolLocale(), { month: 'short' }).format(new Date(day.scheduled_at))}
                  </span>
                </div>
                <div className="planning-day-main">
                  <div>
                    <span className="section-label">{day.report_submitted_at ? 'Séance clôturée' : day.started_at ? 'Cours démarré' : 'Cours'}</span>
                    <h3>{day.title}</h3>
                  </div>
                  <div className="planning-day-meta">
                    <span><Clock3 size={14} /> {new Intl.DateTimeFormat(activeSchoolLocale(), { hour: '2-digit', minute: '2-digit' }).format(new Date(day.scheduled_at))} · {formatDuration(day.duration_minutes)}</span>
                    <span><UserRound size={14} /> {day.teacher_name || 'Professeur'}</span>
                  </div>
                </div>
                {planning.format_type === 'live' && !day.report_submitted_at && (
                  !planning.live_enabled ? <small>Service live en cours de configuration.</small> : liveClassIsOpen(day) ? <Link className="secondary-button" to={`/app/student/live/${day.id}`}>Rejoindre la classe live</Link> : <small>La salle ouvre 15 minutes avant la séance.</small>
                )}
              </article>
            ))}

          {planning.course_days.filter((day) => day.status !== 'cancelled').length === 0 && (
            <div className="app-card formation-empty">
              <CalendarClock size={28} />
              <strong>Planning en préparation</strong>
              <p>Les séances publiées par vos professeurs apparaîtront ici.</p>
            </div>
          )}
        </section>
      )}
    </main>
  )
}
