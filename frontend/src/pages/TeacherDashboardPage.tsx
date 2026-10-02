import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BookOpen,
  CalendarDays,
  GraduationCap,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  Users,
} from 'lucide-react'
import {
  ApiError,
  getTeacherWorkspace,
  type TeacherWorkspace,
} from '../lib/api'
import { useTenant } from '../app/TenantContext'

export function TeacherDashboardPage() {
  const { activeOrganization } = useTenant()
  const [workspace, setWorkspace] = useState<TeacherWorkspace | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!activeOrganization) return
    getTeacherWorkspace()
      .then(setWorkspace)
      .catch((err) => setError(
        err instanceof ApiError ? err.message : 'Impossible de charger votre espace professeur.',
      ))
  }, [activeOrganization?.id])

  if (!workspace && !error) {
    return <div className="page-state">Chargement de votre espace professeur…</div>
  }

  return (
    <main className="app-page role-workspace-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Espace professeur</span>
          <h1>Mes enseignements</h1>
          <p>Vous ne voyez ici que les sessions auxquelles vous êtes affecté.</p>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}

      {workspace && (
        <>
          <section className="role-metric-grid">
            <article><CalendarDays size={19} /><strong>{workspace.total_sessions}</strong><span>Sessions</span></article>
            <article><Users size={19} /><strong>{workspace.total_students}</strong><span>Étudiants suivis</span></article>
            <article><BookOpen size={19} /><strong>{workspace.total_courses}</strong><span>Cours</span></article>
          </section>

          <section className="workspace-shortcuts">
            <Link to="/app/teacher/courses"><BookOpen size={17}/><span>Mes cours</span></Link>
            <Link to="/app/teacher/resources"><FileText size={17}/><span>Ressources</span></Link>
            <Link to="/app/teacher/assignments"><ClipboardCheck size={17}/><span>Devoirs</span></Link>
            <Link to="/app/teacher/quizzes"><CheckCircle2 size={17}/><span>Quiz / Examens</span></Link>
          </section>

          <section className="role-session-list">
            {workspace.sessions.map((session) => (
              <article className="app-card role-session-card" key={session.session_id}>
                <div>
                  <span className="section-label">{session.assignment_role}</span>
                  <h2>{session.formation_title}</h2>
                  <p>{session.session_label}</p>
                </div>
                <div className="role-session-meta">
                  <span><CalendarDays size={14} /> {new Date(session.start_date).toLocaleDateString('fr-FR')} → {new Date(session.end_date).toLocaleDateString('fr-FR')}</span>
                  <span><Users size={14} /> {session.student_count} étudiant(s)</span>
                  <span><GraduationCap size={14} /> {session.course_count} cours</span>
                  <Link className="secondary-button compact-action" to={`/app/teacher/sessions/${session.session_id}`}>
                    Ouvrir le planning
                  </Link>
                </div>
              </article>
            ))}
            {workspace.sessions.length === 0 && (
              <div className="app-card formation-empty">
                <CalendarDays size={28} />
                <strong>Aucune session affectée</strong>
                <p>Une session apparaîtra ici dès que l’administration vous y affectera.</p>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  )
}
