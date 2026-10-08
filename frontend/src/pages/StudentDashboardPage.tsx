import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Award,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Clock3,
  CreditCard,
  GraduationCap,
  HelpCircle,
  Layers,
  TrendingUp,
  Users,
} from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import {
  ApiError,
  getSessionPlanning,
  getStudentWorkspace,
  listStudentAssignments,
  listStudentGrades,
  listStudentProgress,
  listStudentQuizzes,
  type SessionPlanning,
  type StudentAssignment,
  type StudentGrade,
  type StudentProgress,
  type StudentQuiz,
  type StudentWorkspace,
} from '../lib/api'
import { useTenant } from '../app/TenantContext'
import {
  RoleDashboardCalendar,
  type RoleScheduleItem,
} from '../components/RoleDashboardCalendar'
import { RoleSchoolVisual } from '../components/RoleSchoolVisual'
import { RoleQuickAccess } from '../components/RoleQuickAccess'
import { StudentLevelBadge } from '../components/StudentLevelBadge'

function firstName(name?: string | null) {
  return name?.trim().split(/\s+/)[0] || 'Étudiant'
}

const quickAccessLinks = [
  { to: '/app/student/formations?filter=classic', label: 'Formations en ligne', icon: BookOpen, tone: 'indigo' },
  { to: '/app/student/formations?filter=guided', label: 'Parcours guidés', icon: Users, tone: 'sky' },
  { to: '/app/student/quizzes', label: 'Mes quiz', icon: HelpCircle, tone: 'emerald' },
  { to: '/app/student/results', label: 'Mes résultats', icon: Award, tone: 'amber' },
  { to: '/app/student/payments', label: 'Mes paiements', icon: CreditCard, tone: 'pink' },
  { to: '/app/student/assignments', label: 'Mes devoirs', icon: Layers, tone: 'violet' },
] as const

export function StudentDashboardPage() {
  const { user } = useAuth()
  const { activeOrganization } = useTenant()
  const [workspace, setWorkspace] = useState<StudentWorkspace | null>(null)
  const [progress, setProgress] = useState<StudentProgress[]>([])
  const [assignments, setAssignments] = useState<StudentAssignment[]>([])
  const [grades, setGrades] = useState<StudentGrade[]>([])
  const [quizzes, setQuizzes] = useState<StudentQuiz[]>([])
  const [planning, setPlanning] = useState<SessionPlanning[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    if (!activeOrganization) return
    let cancelled = false

    async function load() {
      setError('')
      try {
        const nextWorkspace = await getStudentWorkspace()
        if (cancelled) return
        setWorkspace(nextWorkspace)

        const [progressRows, assignmentRows, quizRows, gradeRows, planningRows] =
          await Promise.all([
            listStudentProgress().catch(() => []),
            listStudentAssignments().catch(() => []),
            listStudentQuizzes().catch(() => []),
            listStudentGrades().catch(() => []),
            Promise.all(
              nextWorkspace.sessions.map((session) => (
                getSessionPlanning(session.session_id).catch(() => null)
              )),
            ),
          ])
        if (cancelled) return
        setProgress(progressRows)
        setAssignments(assignmentRows)
        setQuizzes(quizRows)
        setGrades(gradeRows)
        setPlanning(
          planningRows.filter(
            (item): item is SessionPlanning => item !== null,
          ),
        )
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? err.message
              : 'Impossible de charger votre espace étudiant.',
          )
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [activeOrganization?.id])

  const scheduleItems = useMemo<RoleScheduleItem[]>(() => (
    planning.flatMap((plan) => (
      plan.course_days
        .filter((day) => day.status !== 'cancelled')
        .map((day) => ({
          id: `day-${day.id}`,
          title: day.title,
          detail: `${plan.formation_title} · ${plan.session_label}`,
          startsAt: day.scheduled_at,
          durationMinutes: day.duration_minutes,
          href: `/app/student/sessions/${plan.session_id}`,
          status: day.status === 'planned' ? 'Planifié' : day.status,
        }))
    ))
  ), [planning])

  const nextCourse = useMemo(() => {
    const now = Date.now()
    return scheduleItems
      .filter((item) => (
        new Date(item.startsAt).getTime() + item.durationMinutes * 60_000 >= now
      ))
      .sort((a, b) => (
        new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime()
      ))[0] || null
  }, [scheduleItems])

  const focusSession =
    workspace?.sessions.find((session) => session.enrollment_status === 'active')
    || workspace?.sessions[0]
    || null
  const focusProgress =
    progress.find((item) => item.session_id === focusSession?.session_id)
    || progress[0]
    || null
  const pendingAssignments = assignments.filter(
    (item) => item.student_status === 'pending',
  ).length
  const availableQuizzes = quizzes.filter((item) => item.can_attempt).length
  const taskCount = pendingAssignments + availableQuizzes
  const lessonPercent = focusProgress?.lesson_progress_pct ?? 0
  const attendanceTotal = focusProgress?.attendance_total ?? 0
  const attendancePresent = focusProgress?.attendance_present ?? 0
  const attendancePercent = attendanceTotal
    ? Math.round((attendancePresent / attendanceTotal) * 100)
    : null
  const focusGrades = grades.filter((item) => item.session_id === focusSession?.session_id)
  const validGrades = focusGrades.filter((item) => item.max_score > 0)
  const averageOnTwenty = validGrades.length
    ? validGrades.reduce((sum, item) => sum + (item.score / item.max_score) * 20, 0) / validGrades.length
    : null
  const averageLabel = averageOnTwenty === null
    ? '—/20'
    : `${averageOnTwenty.toFixed(1).replace(/\.0$/, '')}/20`

  if (!workspace && !error) {
    return <div className="page-state">Chargement de votre espace étudiant…</div>
  }

  const progressPercent = focusProgress?.badge.score_pct || 0
  const badgeIsPreview = !focusProgress || focusProgress.badge.level === 'aventurier'

  return (
    <div className="role-overview">
      {error && <div className="form-error">{error}</div>}
      {workspace && (
        <div className="role-overview-grid">
          <section className="role-overview-main">
            <section className="role-hero role-hero--student">
              <div className="role-hero__copy">
                <span>ESPACE ÉTUDIANT</span>
                <h1>Bonjour, {firstName(user?.full_name)}</h1>
                <p>Matricule : <strong>{workspace.student_code || 'En attente'}</strong></p>
                <p>
                  {focusSession
                    ? `${focusSession.formation_title} · ${focusSession.session_label}`
                    : 'Aucune session active'}
                </p>
                <small>
                  Retrouvez vos cours, devoirs, résultats et votre progression.
                </small>
              </div>
              <RoleSchoolVisual
                role="student"
                schoolName={activeOrganization?.name || 'Votre école'}
                logoUrl={activeOrganization?.logo_url}
              />
            </section>

            <section className="role-kpi-grid student-dashboard-kpis" aria-label="Mon suivi en un coup d’œil">
              <article className="role-kpi role-kpi--primary">
                <span>MA PROGRESSION</span>
                <strong>{Math.round(lessonPercent)}%</strong>
                <small>{focusProgress?.completed_lessons ?? 0}/{focusProgress?.total_lessons ?? 0} leçons terminées</small>
                <div className="student-dashboard-kpis__track" role="progressbar" aria-label="Leçons terminées" aria-valuenow={Math.round(lessonPercent)} aria-valuemin={0} aria-valuemax={100}>
                  <i style={{ width: `${Math.min(100, Math.max(0, lessonPercent))}%` }} />
                </div>
                <TrendingUp size={84} aria-hidden="true" />
              </article>
              <article className="role-kpi role-kpi--secondary">
                <span>TRAVAIL À FAIRE</span>
                <strong>{taskCount}</strong>
                <small>{pendingAssignments} devoir{pendingAssignments > 1 ? 's' : ''} · {availableQuizzes} quiz</small>
                <HelpCircle size={84} aria-hidden="true" />
              </article>
              <article className="role-kpi role-kpi--mint">
                <span>ASSIDUITÉ</span>
                <strong>{attendancePercent === null ? '—' : `${attendancePercent}%`}</strong>
                <small>{attendancePresent}/{attendanceTotal} présence{attendancePresent > 1 ? 's' : ''} validée{attendancePresent > 1 ? 's' : ''}</small>
                <Users size={84} aria-hidden="true" />
              </article>
              <article className="role-kpi role-kpi--accent">
                <span>MOYENNE</span>
                <strong>{averageLabel}</strong>
                <small>{focusGrades.length ? `${focusGrades.length} note${focusGrades.length > 1 ? 's' : ''} publiée${focusGrades.length > 1 ? 's' : ''}` : 'Aucune note publiée'}</small>
                <GraduationCap size={84} aria-hidden="true" />
              </article>
            </section>

            <section className="role-calendar-card">
              <header>
                <div>
                  <CalendarDays size={17} />
                  <strong>Calendrier des cours</strong>
                </div>
                <Link className="dashboard-text-link" to="/app/student/planning">Voir tout le planning <ChevronRight size={15} aria-hidden="true" /></Link>
              </header>

              {nextCourse ? (
                <div className="role-next-course">
                  <div>
                    <span>Prochain cours</span>
                    <strong>{nextCourse.title}</strong>
                    <p>
                      {nextCourse.detail} ·{' '}
                      {new Date(nextCourse.startsAt).toLocaleString('fr-FR', {
                        weekday: 'long',
                        day: 'numeric',
                        month: 'long',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                  <Link className="dashboard-text-link" to={nextCourse.href}>Voir la séance <ChevronRight size={15} aria-hidden="true" /></Link>
                </div>
              ) : (
                <div className="role-next-course is-empty">
                  <div>
                    <span>Planning</span>
                    <strong>Aucun prochain cours programmé</strong>
                    <p>Les nouvelles séances apparaîtront ici.</p>
                  </div>
                </div>
              )}

              <RoleDashboardCalendar items={scheduleItems} />
            </section>

            <RoleQuickAccess links={quickAccessLinks} />
          </section>

          <aside className="role-overview-side">
            <section className="role-side-card">
              <header>
                <strong>MA PROGRESSION</strong>
                <span>{progressPercent}%</span>
              </header>
              <div className="role-student-progress-card">
                <div className="role-student-progress-card__head">
                  <StudentLevelBadge
                    level={focusProgress?.badge.level}
                    className="role-student-progress-card__badge"
                  />
                  <span>
                    <small>{badgeIsPreview ? 'Prochain badge' : 'Niveau actuel'}</small>
                    <strong>
                      {badgeIsPreview
                        ? 'Débutant · Niveau 1'
                        : focusProgress?.badge.label}
                    </strong>
                  </span>
                </div>
                <div className="role-student-progress-card__bar">
                  <i style={{ width: `${progressPercent}%` }} />
                </div>
                <p>
                  {focusProgress
                    ? `${focusProgress.completed_lessons}/${focusProgress.total_lessons} leçons terminées dans votre formation active.`
                    : 'Votre progression apparaîtra dès que vous commencerez vos cours.'}
                </p>
                <Link className="dashboard-text-link" to="/app/student/progress">Voir ma progression <ChevronRight size={15} aria-hidden="true" /></Link>
              </div>
            </section>

            <section className="role-side-card">
              <header>
                <strong>MES FORMATIONS ACTIVES</strong>
                <span>{workspace.sessions.length}</span>
              </header>
              <div className="role-side-list">
                {workspace.sessions.slice(0, 4).map((session) => (
                  <Link
                    to={`/app/student/${session.dashboard_type}/${session.enrollment_id}`}
                    key={session.enrollment_id}
                  >
                    <i />
                    <span>
                      <strong>{session.session_label}</strong>
                      <small>{session.formation_title}</small>
                    </span>
                    <b>Ouvrir</b>
                  </Link>
                ))}
                {workspace.sessions.length === 0 && (
                  <p>Aucune formation active.</p>
                )}
              </div>
            </section>

            <section className="role-side-card">
              <header>
                <strong>À FAIRE</strong>
                <span>{pendingAssignments + availableQuizzes}</span>
              </header>
              {pendingAssignments + availableQuizzes === 0 ? (
                <div className="role-priority is-ok">
                  <CheckCircle2 size={18} />
                  <span>
                    <strong>Tout est à jour</strong>
                    <small>Aucun devoir ou quiz urgent.</small>
                  </span>
                </div>
              ) : (
                <div className="role-action-stack">
                  {pendingAssignments > 0 && (
                    <Link to="/app/student/assignments">
                      <ClipboardCheck size={16} />
                      <span>
                        <strong>{pendingAssignments} devoir(s) à rendre</strong>
                        <small>Consultez les dates limites.</small>
                      </span>
                    </Link>
                  )}
                  {availableQuizzes > 0 && (
                    <Link to="/app/student/quizzes">
                      <CheckCircle2 size={16} />
                      <span>
                        <strong>{availableQuizzes} quiz/examen(s)</strong>
                        <small>Évaluations disponibles.</small>
                      </span>
                    </Link>
                  )}
                </div>
              )}
            </section>

            <section className="role-side-card">
              <header>
                <strong>PROCHAIN RENDEZ-VOUS</strong>
                <Clock3 size={16} />
              </header>
              <div className="role-recent-list">
                {scheduleItems.slice(0, 2).map((item) => (
                  <Link to={item.href} key={item.id}>
                    <span className="role-recent-icon">
                      <CalendarDays size={14} />
                    </span>
                    <span>
                      <strong>{item.title}</strong>
                      <small>{item.detail}</small>
                    </span>
                  </Link>
                ))}
                {scheduleItems.length === 0 && <p>Aucun rendez-vous.</p>}
              </div>
            </section>
          </aside>
        </div>
      )}
    </div>
  )
}
