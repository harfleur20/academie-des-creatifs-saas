import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useState } from 'react'
import {
  BookOpen,
  CalendarDays,
  ChevronRight,
  ClipboardCheck,
  FileText,
  MapPin,
  Monitor,
  Users,
  Video,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import {
  ApiError,
  getTeacherWorkspace,
  type TeacherWorkspace,
  type TeacherWorkspaceSession,
} from '../lib/api'

type StatusFilter = 'all' | 'open' | 'planned' | 'completed'

const filters: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'Toutes' },
  { value: 'open', label: 'Ouvertes' },
  { value: 'planned', label: 'Planifiées' },
  { value: 'completed', label: 'Terminées' },
]

const statusLabels: Record<string, string> = {
  open: 'Ouverte',
  planned: 'Planifiée',
  completed: 'Terminée',
}

const formatLabels = {
  ligne: 'En ligne',
  live: 'Live',
  presentiel: 'Présentiel',
}

function dateLabel(value: string) {
  return new Date(value).toLocaleDateString(activeSchoolLocale(), {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

function SessionCard({ session }: { session: TeacherWorkspaceSession }) {
  const FormatIcon = session.format_type === 'live'
    ? Video
    : session.format_type === 'presentiel'
      ? MapPin
      : Monitor

  return (
    <article className="teacher-session-card">
      <div className="teacher-session-card__cover">
        {session.formation_image ? (
          <img src={session.formation_image} alt="" />
        ) : (
          <BookOpen size={34} aria-hidden="true" />
        )}
      </div>
      <div className="teacher-session-card__body">
        <div className="teacher-session-card__badges">
          <span className={`teacher-session-status is-${session.status}`}>
            {statusLabels[session.status] || session.status}
          </span>
          <span className="teacher-session-format">
            <FormatIcon size={14} /> {formatLabels[session.format_type] || 'Formation'}
          </span>
        </div>
        <h2>{session.formation_title}</h2>
        <p className="teacher-session-card__label">{session.session_label}</p>
        <div className="teacher-session-card__meta">
          <span><CalendarDays size={15} /> {dateLabel(session.start_date)} → {dateLabel(session.end_date)}</span>
          {session.campus_label && <span><MapPin size={15} /> {session.campus_label}</span>}
          <span>
            <Users size={15} /> {session.student_count}
            {session.seat_capacity > 0 && ` / ${session.seat_capacity}`} étudiant{session.student_count !== 1 ? 's' : ''}
          </span>
          <span><BookOpen size={15} /> {session.course_count} cours</span>
        </div>
        <Link className="teacher-session-card__link" to={`/app/teacher/sessions/${session.session_id}`}>
          Ouvrir le planning <ChevronRight size={16} />
        </Link>
      </div>
    </article>
  )
}

export function TeacherSessionsPage() {
  const { activeOrganization } = useTenant()
  const [workspace, setWorkspace] = useState<TeacherWorkspace | null>(null)
  const [filter, setFilter] = useState<StatusFilter>('all')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!activeOrganization) return
    let cancelled = false
    getTeacherWorkspace()
      .then((result) => {
        if (!cancelled) setWorkspace(result)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Chargement impossible.')
      })
    return () => { cancelled = true }
  }, [activeOrganization?.id])

  if (!workspace && !error) {
    return <div className="page-state">Chargement de vos sessions…</div>
  }

  const sessions = workspace?.sessions || []
  const counts = {
    all: sessions.length,
    open: sessions.filter((session) => session.status === 'open').length,
    planned: sessions.filter((session) => session.status === 'planned').length,
    completed: sessions.filter((session) => session.status === 'completed').length,
  }
  const visible = filter === 'all'
    ? sessions
    : sessions.filter((session) => session.status === filter)

  return (
    <div className="teacher-sessions-page">
      <header className="teacher-sessions-hero">
        <div>
          <span>Espace enseignant</span>
          <h1>Mes sessions</h1>
          <p>{sessions.length} session{sessions.length !== 1 ? 's' : ''} assignée{sessions.length !== 1 ? 's' : ''}</p>
          <small>Retrouvez vos cohortes, leurs dates et leur planning pédagogique.</small>
        </div>
        <div className="teacher-sessions-hero__stats">
          <span><strong>{counts.open}</strong> ouvertes</span>
          <span><strong>{counts.planned}</strong> planifiées</span>
          <span><strong>{counts.completed}</strong> terminées</span>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}

      {workspace && (
        <>
          <div className="teacher-sessions-filters" role="group" aria-label="Filtrer les sessions">
            {filters.map((item) => (
              <button
                key={item.value}
                type="button"
                className={filter === item.value ? 'is-active' : ''}
                aria-pressed={filter === item.value}
                onClick={() => setFilter(item.value)}
              >
                {item.label} <span>{counts[item.value]}</span>
              </button>
            ))}
          </div>

          {visible.length > 0 ? (
            <div className="teacher-sessions-grid">
              {visible.map((session) => <SessionCard key={session.session_id} session={session} />)}
            </div>
          ) : (
            <div className="teacher-sessions-empty">
              <CalendarDays size={32} />
              <strong>Aucune session{filter === 'all' ? ' assignée' : ' pour ce filtre'}</strong>
              <p>{filter === 'all' ? 'Les sessions qui vous seront attribuées apparaîtront ici.' : 'Essayez un autre filtre.'}</p>
            </div>
          )}

          <section className="teacher-sessions-tools">
            <h2>Autres outils</h2>
            <div>
              <Link to="/app/teacher/courses"><BookOpen size={18} /> Mes cours <ChevronRight size={15} /></Link>
              <Link to="/app/teacher/assignments"><ClipboardCheck size={18} /> Devoirs <ChevronRight size={15} /></Link>
              <Link to="/app/teacher/resources"><FileText size={18} /> Ressources <ChevronRight size={15} /></Link>
            </div>
          </section>
        </>
      )}
    </div>
  )
}
