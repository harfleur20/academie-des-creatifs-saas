import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useState } from 'react'
import { CalendarDays, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  ApiError,
  getStudentWorkspace,
  type StudentWorkspace,
} from '../lib/api'

export function StudentPlanningPage() {
  const [workspace, setWorkspace] = useState<StudentWorkspace | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getStudentWorkspace()
      .then(setWorkspace)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Chargement impossible.'),
      )
  }, [])

  return (
    <main className="app-page academic-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Espace étudiant</span>
          <h1>Planning</h1>
          <p>Choisissez une formation pour consulter toutes les séances publiées.</p>
        </div>
      </header>
      {error && <div className="form-error">{error}</div>}
      <section className="academic-card-list">
        {workspace?.sessions.map((session) => (
          <Link
            className="app-card planning-overview-card"
            key={session.enrollment_id}
            to={'/app/student/sessions/' + session.session_id}
          >
            <span className="academic-item-icon"><CalendarDays size={17} /></span>
            <div>
              <span className="section-label">{session.session_status}</span>
              <h3>{session.formation_title}</h3>
              <small>
                {session.session_label} · du{' '}
                {new Date(session.start_date).toLocaleDateString(activeSchoolLocale())} au{' '}
                {new Date(session.end_date).toLocaleDateString(activeSchoolLocale())}
              </small>
            </div>
            <ChevronRight size={17} />
          </Link>
        ))}
        {workspace && workspace.sessions.length === 0 && (
          <div className="app-card formation-empty">
            <CalendarDays size={26} />
            <strong>Aucun planning disponible</strong>
            <p>Vous n’êtes inscrit dans aucune session active.</p>
          </div>
        )}
      </section>
    </main>
  )
}
