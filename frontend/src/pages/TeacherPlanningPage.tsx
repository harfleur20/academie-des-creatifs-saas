import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useState } from 'react'
import { CalendarDays, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import {
  ApiError,
  getTeacherWorkspace,
  type TeacherWorkspace,
} from '../lib/api'

function dateLabel(value: string) {
  return new Date(value).toLocaleDateString(activeSchoolLocale(), {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

const sessionStatusLabels: Record<string, string> = {
  open: 'Ouverte',
  planned: 'Planifiée',
  completed: 'Terminée',
}

export function TeacherPlanningPage() {
  const { activeOrganization } = useTenant()
  const [workspace, setWorkspace] = useState<TeacherWorkspace | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!activeOrganization) return
    let cancelled = false
    getTeacherWorkspace()
      .then((result) => {
        if (!cancelled) setWorkspace(result)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Chargement impossible.')
        }
      })
    return () => { cancelled = true }
  }, [activeOrganization?.id])

  const sessions = workspace?.sessions ?? []

  return (
    <main className="app-page academic-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Espace enseignant</span>
          <h1>Emploi du temps</h1>
          <p>Choisissez une session pour consulter et gérer les séances planifiées.</p>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}
      {!workspace && !error && <div className="page-state">Chargement de votre emploi du temps…</div>}

      {workspace && (
        <section className="academic-card-list">
          {sessions.map((session) => (
            <Link
              className="app-card planning-overview-card"
              key={session.session_id}
              to={`/app/teacher/sessions/${session.session_id}`}
            >
              <span className="academic-item-icon"><CalendarDays size={17} /></span>
              <div>
                <span className="section-label">{sessionStatusLabels[session.status] || session.status}</span>
                <h3>{session.formation_title}</h3>
                <small>
                  {session.session_label} · du {dateLabel(session.start_date)} au {dateLabel(session.end_date)}
                  {' · '}{session.course_count} cours planifié{session.course_count !== 1 ? 's' : ''}
                </small>
              </div>
              <ChevronRight size={17} />
            </Link>
          ))}
          {sessions.length === 0 && (
            <div className="app-card formation-empty">
              <CalendarDays size={26} />
              <strong>Aucun emploi du temps disponible</strong>
              <p>Les sessions qui vous seront attribuées apparaîtront ici.</p>
            </div>
          )}
        </section>
      )}
    </main>
  )
}
