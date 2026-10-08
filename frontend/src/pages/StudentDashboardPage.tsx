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
  HelpCircle,
  Layers,
  TrendingUp,
  Users,
  Video,
} from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import {
  ApiError,
  getSessionPlanning,
  getStudentWorkspace,
  listStudentLearning,
  listStudentAssignments,
  listStudentGrades,
  listStudentProgress,
  listStudentQuizzes,
  type SessionPlanning,
  type LearningSession,
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
import { badgeRingPercent, StudentLevelBadge } from '../components/StudentLevelBadge'

function firstName(name?: string | null) {
  return name?.trim().split(/\s+/)[0] || 'Étudiant'
}

function shortDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString('fr-FR', {
    day: 'numeric', month: 'long', year: 'numeric',
  })
}

function sessionStatus(status: string) {
  if (status === 'open') return 'Ouverte'
  if (status === 'running') return 'En cours'
  if (status === 'completed') return 'Terminée'
  return 'À venir'
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
  const [learning, setLearning] = useState<LearningSession[]>([])
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

        const [progressRows, learningRows, assignmentRows, quizRows, gradeRows, planningRows] =
          await Promise.all([
            listStudentProgress().catch(() => []),
            listStudentLearning().catch(() => []),
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
        setLearning(learningRows)
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
    progress.find((item) => item.enrollment_id === focusSession?.enrollment_id)
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
  const courseProgress = learning.flatMap((session) => session.courses.map((course) => {
    const lessons = course.chapters.flatMap((chapter) => chapter.lessons)
    const completed = lessons.filter((lesson) => lesson.completed).length
    return {
      id: `${session.enrollment_id}-${course.id}`,
      title: course.title,
      completed,
      total: lessons.length,
      percent: lessons.length ? Math.round(completed / lessons.length * 100) : 0,
    }
  }))

  if (!workspace && !error) {
    return <div className="page-state">Chargement de votre espace étudiant…</div>
  }

  const progressPercent = focusProgress ? badgeRingPercent(focusProgress.badge) : 0
  const nextBadgeLabel = focusProgress?.badge.next_level
    ? ({ debutant: 'Débutant', intermediaire: 'Intermédiaire', semi_pro: 'Semi-pro', professionnel: 'Professionnel' } as Record<string, string>)[focusProgress.badge.next_level]
    : null

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

            {workspace.sessions.length > 0 && <section className="student-overview-panel student-overview-sessions">
              <header><div><Video size={19} aria-hidden="true" /><h2>Mes sessions programmées</h2></div></header>
              <div className="student-overview-sessions__list">
                {workspace.sessions.map((session) => <article className="student-overview-session" key={session.enrollment_id}>
                  <div className="student-overview-session__content">
                    <span className={`student-overview-session__status student-overview-session__status--${session.session_status}`}>{sessionStatus(session.session_status)}</span>
                    <h3>{session.formation_title}</h3>
                    <strong>{session.session_label}</strong>
                    <p><CalendarDays size={17} aria-hidden="true" /> {shortDate(session.start_date)} → {shortDate(session.end_date)}{session.teacher_name ? ` · ${session.teacher_name}` : ''}{session.campus_label ? ` · ${session.campus_label}` : ''}</p>
                  </div>
                  <Link className="student-overview-session__action" to={`/app/student/${session.dashboard_type}/${session.enrollment_id}${session.dashboard_type === 'guided' ? '?tab=calendar' : ''}`}>
                    <BookOpen size={17} aria-hidden="true" /> Voir le programme <ChevronRight size={17} aria-hidden="true" />
                  </Link>
                </article>)}
              </div>
            </section>}

            <section className="student-overview-panel student-overview-progress">
              <header><div><TrendingUp size={19} aria-hidden="true" /><h2>Ma progression</h2></div><Link className="dashboard-text-link" to="/app/student/formations">Voir tout <ChevronRight size={16} aria-hidden="true" /></Link></header>
              {courseProgress.length > 0 ? <div className="student-overview-progress__list">
                {courseProgress.map((course) => <article className="student-overview-progress__row" key={course.id}>
                  <div><h3>{course.title}</h3><strong>{course.completed}/{course.total} leçons</strong></div>
                  <div className="student-overview-progress__meter"><span>Avancement du cours</span><div role="progressbar" aria-label={`Progression de ${course.title}`} aria-valuenow={course.percent} aria-valuemin={0} aria-valuemax={100}><i style={{ width: `${course.percent}%` }} /></div><strong>{course.percent}%</strong></div>
                </article>)}
              </div> : <p className="student-overview-progress__empty">Les cours et leur progression apparaîtront ici dès leur publication.</p>}
            </section>

            <RoleQuickAccess links={quickAccessLinks} />
          </section>

          <aside className="role-overview-side">
            <section className="student-badge-card">
              <header><Award size={21} aria-hidden="true" /><strong>Mon badge</strong></header>
              <div className="student-badge-card__body">
                <div className="student-badge-card__course">
                  <strong title={focusSession?.formation_title || focusProgress?.formation_title}>{focusSession?.formation_title || focusProgress?.formation_title || 'Mon parcours'}</strong>
                  <span>{focusSession?.session_label || focusProgress?.session_label || 'Votre session'}</span>
                </div>
                <StudentLevelBadge level={focusProgress?.badge.level} ringPct={progressPercent} locked={!focusProgress} className="student-badge-card__visual" />
                <strong className="student-badge-card__level">{focusProgress?.badge.label || 'Aventurier'}</strong>
                <div className="student-badge-card__progress">
                  <span>{nextBadgeLabel ? <>Progression vers <strong>{nextBadgeLabel}</strong></> : 'Niveau maximal'}</span>
                  <strong>{progressPercent}%</strong>
                </div>
                <div className="student-badge-card__footer">
                  <Link className="dashboard-text-link" to="/app/student/progress">Voir ma progression <ChevronRight size={15} aria-hidden="true" /></Link>
                </div>
              </div>
            </section>

            <section className="student-dashboard-kpis" aria-label="Mon suivi en un coup d’œil">
              <article className="student-dashboard-kpi student-dashboard-kpi--blue">
                <span className="student-dashboard-kpi__label">Ma progression</span>
                <strong className="student-dashboard-kpi__value">{Math.round(lessonPercent)}%</strong>
                <small className="student-dashboard-kpi__sub">{focusProgress?.completed_lessons ?? 0}/{focusProgress?.total_lessons ?? 0} leçons terminées</small>
                <div className="student-dashboard-kpi__progress" role="progressbar" aria-label="Leçons terminées" aria-valuenow={Math.round(lessonPercent)} aria-valuemin={0} aria-valuemax={100}>
                  <span style={{ width: `${Math.min(100, Math.max(0, lessonPercent))}%` }} />
                </div>
                <span className="student-dashboard-kpi__icon" aria-hidden="true"><TrendingUp size={52} /></span>
              </article>
              <article className="student-dashboard-kpi student-dashboard-kpi--purple">
                <span className="student-dashboard-kpi__label">Travail à faire</span>
                <strong className="student-dashboard-kpi__value">{taskCount}</strong>
                <small className="student-dashboard-kpi__sub">{pendingAssignments} devoir{pendingAssignments > 1 ? 's' : ''} · {availableQuizzes} quiz</small>
                <span className="student-dashboard-kpi__icon" aria-hidden="true"><HelpCircle size={52} /></span>
              </article>
              <article className="student-dashboard-kpi student-dashboard-kpi--green">
                <span className="student-dashboard-kpi__label">Assiduité</span>
                <strong className="student-dashboard-kpi__value">{attendancePercent === null ? '—' : `${attendancePercent}%`}</strong>
                <small className="student-dashboard-kpi__sub">{attendancePresent}/{attendanceTotal} présence{attendancePresent > 1 ? 's' : ''} validée{attendancePresent > 1 ? 's' : ''}</small>
                <span className="student-dashboard-kpi__icon" aria-hidden="true"><Users size={52} /></span>
              </article>
              <article className="student-dashboard-kpi student-dashboard-kpi--yellow">
                <span className="student-dashboard-kpi__label">Moyenne</span>
                <strong className="student-dashboard-kpi__value">{averageLabel}</strong>
                <small className="student-dashboard-kpi__sub">{focusGrades.length ? `${focusGrades.length} note${focusGrades.length > 1 ? 's' : ''} publiée${focusGrades.length > 1 ? 's' : ''}` : 'Aucune note publiée'}</small>
                <span className="student-dashboard-kpi__icon" aria-hidden="true"><Layers size={52} /></span>
              </article>
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
