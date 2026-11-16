import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity,
  Airplay,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Clock3,
  FileText,
  GraduationCap,
  HelpCircle,
  TrendingUp,
  Users,
  Video,
} from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import {
  ApiError,
  getSessionPlanning,
  getTeacherPerformance,
  getTeacherWorkspace,
  type SessionPlanning,
  type TeacherPerformance,
  type TeacherWorkspace,
} from '../lib/api'
import { useTenant } from '../app/TenantContext'
import {
  RoleDashboardCalendar,
  type RoleScheduleItem,
} from '../components/RoleDashboardCalendar'
import { RoleSchoolVisual } from '../components/RoleSchoolVisual'
import { RoleQuickAccess } from '../components/RoleQuickAccess'

function firstName(name?: string | null) {
  return name?.trim().split(/\s+/)[0] || 'Enseignant'
}

const quickAccessLinks = [
  { to: '/app/teacher/courses', label: 'Mes cours', icon: BookOpen, tone: 'indigo' },
  { to: '/app/teacher/quizzes', label: 'Quiz & examens', icon: HelpCircle, tone: 'emerald' },
  { to: '/app/teacher/assignments', label: 'Devoirs', icon: ClipboardList, tone: 'violet' },
  { to: '/app/teacher/resources', label: 'Ressources', icon: FileText, tone: 'sky' },
  { to: '/app/teacher/sessions', label: 'Mes sessions', icon: Video, tone: 'amber' },
  { to: '/app/teacher/performance', label: 'Performance', icon: TrendingUp, tone: 'pink' },
] as const

export function TeacherDashboardPage() {
  const { user } = useAuth()
  const { activeOrganization } = useTenant()
  const [workspace, setWorkspace] = useState<TeacherWorkspace | null>(null)
  const [performance, setPerformance] = useState<TeacherPerformance | null>(null)
  const [planning, setPlanning] = useState<SessionPlanning[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    if (!activeOrganization) return
    let cancelled = false

    async function load() {
      setError('')
      try {
        const nextWorkspace = await getTeacherWorkspace()
        if (cancelled) return
        setWorkspace(nextWorkspace)

        const [performanceResult, planningResults] = await Promise.all([
          getTeacherPerformance().catch(() => null),
          Promise.all(
            nextWorkspace.sessions.map((session) => (
              getSessionPlanning(session.session_id).catch(() => null)
            )),
          ),
        ])
        if (cancelled) return
        setPerformance(performanceResult)
        setPlanning(
          planningResults.filter(
            (item): item is SessionPlanning => item !== null,
          ),
        )
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? err.message
              : 'Impossible de charger votre espace enseignant.',
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
          href: `/app/teacher/sessions/${plan.session_id}`,
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

  const openSessions = workspace?.sessions.filter(
    (session) => session.status === 'open',
  ).length || 0
  const plannedSessions = workspace?.sessions.filter(
    (session) => session.status === 'planned',
  ).length || 0
  const formationCount = new Set(
    workspace?.sessions.map((session) => session.formation_id) || [],
  ).size
  const activeSessions = workspace?.sessions.filter(
    (session) => ['open', 'planned'].includes(session.status),
  ) || []

  if (!workspace && !error) {
    return <div className="page-state">Chargement de votre espace enseignant…</div>
  }

  return (
    <div className="role-overview">
      {error && <div className="form-error">{error}</div>}
      {workspace && (
        <div className="role-overview-grid">
          <section className="role-overview-main">
            <section className="role-hero">
              <div className="role-hero__copy">
                <span>ESPACE ENSEIGNANT</span>
                <h1>Bonjour, {firstName(user?.full_name)}</h1>
                <p>
                  Code enseignant : <strong>{workspace.teacher_code}</strong>
                </p>
                <p>
                  Sessions ouvertes :{' '}
                  <strong>{String(openSessions).padStart(2, '0')}</strong>
                </p>
                <small>
                  Gérez vos cours, présences, devoirs et résultats pour chaque
                  session.
                </small>
              </div>
              <RoleSchoolVisual
                role="teacher"
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
                <Link className="dashboard-text-link" to="/app/teacher/sessions">Voir mes sessions <ChevronRight size={15} aria-hidden="true" /></Link>
              </header>

              {nextCourse ? (
                <div className="role-next-course">
                  <div>
                    <span>Prochain cours à animer</span>
                    <strong>{nextCourse.title}</strong>
                    <p>
                      {nextCourse.detail} ·{' '}
                      {new Date(nextCourse.startsAt).toLocaleString(activeSchoolLocale(), {
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
            <section className="role-kpi-grid">
              <article className="role-kpi role-kpi--primary">
                <span>SESSIONS TOTALES</span>
                <strong>{workspace.total_sessions}</strong>
                <small>{openSessions} ouverte(s)</small>
                <CalendarDays size={29} />
              </article>
              <article className="role-kpi role-kpi--secondary">
                <span>SESSIONS PLANIFIÉES</span>
                <strong>{plannedSessions}</strong>
                <small>À venir</small>
                <Clock3 size={29} />
              </article>
              <article className="role-kpi role-kpi--mint">
                <span>ÉTUDIANTS SUIVIS</span>
                <strong>{workspace.total_students}</strong>
                <small>Toutes sessions</small>
                <Users size={29} />
              </article>
              <article className="role-kpi role-kpi--accent">
                <span>FORMATIONS</span>
                <strong>{formationCount}</strong>
                <small>Assignées</small>
                <GraduationCap size={29} />
              </article>
            </section>

            <section className="role-side-card">
              <header>
                <strong>SESSIONS ACTIVES & À VENIR</strong>
                <span>{activeSessions.length}</span>
              </header>
              <div className="role-side-list">
                {activeSessions.slice(0, 4).map((session) => (
                  <Link
                    to={`/app/teacher/sessions/${session.session_id}`}
                    key={session.session_id}
                  >
                    <i />
                    <span>
                      <strong>{session.session_label}</strong>
                      <small>{session.formation_title}</small>
                    </span>
                    <b>Ouvrir</b>
                  </Link>
                ))}
                {activeSessions.length === 0 && (
                  <p>Aucune session active ou à venir.</p>
                )}
              </div>
            </section>

            <section className="role-side-card">
              <header>
                <strong>PRIORITÉS PÉDAGOGIQUES</strong>
                <span>{performance?.pending_reviews_count || 0}</span>
              </header>
              {(performance?.pending_reviews_count || 0) > 0 ? (
                <Link className="role-priority" to="/app/teacher/assignments">
                  <Activity size={18} />
                  <span>
                    <strong>
                      {performance?.pending_reviews_count} correction(s) en attente
                    </strong>
                    <small>Des remises étudiants attendent votre validation.</small>
                  </span>
                </Link>
              ) : (
                <div className="role-priority is-ok">
                  <CheckCircle2 size={18} />
                  <span>
                    <strong>Tout est à jour</strong>
                    <small>
                      Aucune correction ne demande une action immédiate.
                    </small>
                  </span>
                </div>
              )}
            </section>

            <section className="role-side-card">
              <header>
                <strong>ACTIVITÉ RÉCENTE</strong>
                <span>{Math.min(scheduleItems.length, 3)}</span>
              </header>
              <div className="role-recent-list">
                {scheduleItems
                  .slice()
                  .sort((a, b) => (
                    new Date(b.startsAt).getTime()
                    - new Date(a.startsAt).getTime()
                  ))
                  .slice(0, 3)
                  .map((item) => (
                    <Link to={item.href} key={item.id}>
                      <span className="role-recent-icon">
                        <Airplay size={14} />
                      </span>
                      <span>
                        <strong>{item.title}</strong>
                        <small>{item.detail}</small>
                      </span>
                    </Link>
                  ))}
                {scheduleItems.length === 0 && <p>Aucune activité récente.</p>}
              </div>
            </section>
          </aside>
        </div>
      )}
    </div>
  )
}
