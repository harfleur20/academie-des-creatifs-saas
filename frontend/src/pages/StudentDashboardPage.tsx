import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BookOpen,
  CalendarDays,
  GraduationCap,
  Award,
  BarChart3,
  CheckCircle2,
  ClipboardCheck,
  FileText,
} from 'lucide-react'
import {
  ApiError,
  getStudentWorkspace,
  type StudentWorkspace,
} from '../lib/api'
import { useTenant } from '../app/TenantContext'

export function StudentDashboardPage() {
  const { activeOrganization } = useTenant()
  const [workspace, setWorkspace] = useState<StudentWorkspace | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!activeOrganization) return
    getStudentWorkspace()
      .then(setWorkspace)
      .catch((err) => setError(
        err instanceof ApiError ? err.message : 'Impossible de charger votre espace étudiant.',
      ))
  }, [activeOrganization?.id])

  if (!workspace && !error) {
    return <div className="page-state">Chargement de votre espace étudiant…</div>
  }

  return (
    <main className="app-page role-workspace-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Espace étudiant</span>
          <h1>Mes formations</h1>
          <p>Vous ne voyez ici que les cohortes dans lesquelles vous êtes inscrit.</p>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}

      {workspace && (
        <>
          <section className="role-metric-grid">
            <article><GraduationCap size={19} /><strong>{workspace.total_sessions}</strong><span>Formations / sessions</span></article>
            <article><BookOpen size={19} /><strong>{workspace.total_courses}</strong><span>Cours disponibles</span></article>
          </section>

          <section className="workspace-shortcuts">
            <Link to="/app/student/courses"><BookOpen size={17}/><span>Mes cours</span></Link>
            <Link to="/app/student/resources"><FileText size={17}/><span>Ressources</span></Link>
            <Link to="/app/student/assignments"><ClipboardCheck size={17}/><span>Devoirs</span></Link>
            <Link to="/app/student/quizzes"><CheckCircle2 size={17}/><span>Quiz / Examens</span></Link>
            <Link to="/app/student/results"><BarChart3 size={17}/><span>Résultats</span></Link>
            <Link to="/app/student/progress"><Award size={17}/><span>Progression</span></Link>
          </section>

          <section className="role-session-list">
            {workspace.sessions.map((session) => (
              <article className="app-card role-session-card" key={session.enrollment_id}>
                <div>
                  <span className="section-label">{session.enrollment_status}</span>
                  <h2>{session.formation_title}</h2>
                  <p>{session.session_label}</p>
                </div>
                <div className="role-session-meta">
                  <span><CalendarDays size={14} /> {new Date(session.start_date).toLocaleDateString('fr-FR')} → {new Date(session.end_date).toLocaleDateString('fr-FR')}</span>
                  <span><BookOpen size={14} /> {session.course_count} cours</span>
                  <Link className="secondary-button compact-action" to={`/app/student/sessions/${session.session_id}`}>
                    Voir le planning
                  </Link>
                </div>
              </article>
            ))}
            {workspace.sessions.length === 0 && (
              <div className="app-card formation-empty">
                <GraduationCap size={28} />
                <strong>Aucune inscription active</strong>
                <p>Vos formations apparaîtront ici dès que l’école vous inscrira dans une session.</p>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  )
}
