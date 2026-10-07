import { useEffect, useState } from 'react'
import { GraduationCap } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import {
  ApiError,
  getStudentWorkspace,
  listPublicSchoolFormations,
  type StudentWorkspace,
} from '../lib/api'

type Filter = 'all' | 'classic' | 'guided'

const formatLabels = {
  ligne: 'En ligne',
  live: 'Live',
  presentiel: 'Présentiel',
}

export function StudentParcoursPage() {
  const { activeOrganization } = useTenant()
  const [workspace, setWorkspace] = useState<StudentWorkspace | null>(null)
  const [filter, setFilter] = useState<Filter>('all')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!activeOrganization) return
    let cancelled = false
    setWorkspace(null)
    setError('')
    getStudentWorkspace()
      .then(async (next) => {
        if (next.sessions.some((session) => !session.formation_image)) {
          try {
            const catalogue = await listPublicSchoolFormations(activeOrganization.slug)
            const images = new Map(catalogue.map((formation) => [formation.id, formation.cover_image_url]))
            next = {
              ...next,
              sessions: next.sessions.map((session) => ({
                ...session,
                formation_image: session.formation_image || images.get(session.formation_id) || null,
              })),
            }
          } catch {
            // The student workspace remains available if the public catalogue cannot load.
          }
        }
        if (!cancelled) setWorkspace(next)
      })
      .catch((err) => { if (!cancelled) setError(err instanceof ApiError ? err.message : 'Chargement impossible.') })
    return () => { cancelled = true }
  }, [activeOrganization?.id])

  const sessions = workspace?.sessions ?? []
  const visible = sessions.filter((item) => filter === 'all' || item.dashboard_type === filter)
  const classicCount = sessions.filter((item) => item.dashboard_type === 'classic').length
  const guidedCount = sessions.length - classicCount

  return (
    <main className="app-page student-parcours-page">
      <header className="app-page-header">
        <div><span className="page-kicker">Espace étudiant</span><h1>Mes parcours</h1><p>{sessions.length} formation{sessions.length > 1 ? 's' : ''} active{sessions.length > 1 ? 's' : ''}</p></div>
      </header>
      {error && <div className="form-error">{error}</div>}
      {!workspace && !error && <div className="page-state">Chargement de vos parcours…</div>}
      {workspace && <>
        <div className="student-parcours-filters" aria-label="Filtrer les parcours">
          {([
            ['all', `Tous (${sessions.length})`],
            ['classic', `En ligne (${classicCount})`],
            ['guided', `Guidés (${guidedCount})`],
          ] as const).map(([value, label]) => (
            <button key={value} type="button" className={filter === value ? 'is-active' : ''} onClick={() => setFilter(value)} aria-pressed={filter === value}>{label}</button>
          ))}
        </div>
        {visible.length === 0 ? <div className="app-card">Aucun parcours dans cette catégorie.</div> : (
          <div className="student-parcours-grid">
            {visible.map((session) => <article className="student-parcours-card" key={session.enrollment_id}>
              <div className="student-parcours-card__media">
                {session.formation_image ? (
                  <img src={session.formation_image} alt="" loading="lazy" decoding="async" />
                ) : (
                  <GraduationCap size={36} aria-hidden="true" />
                )}
              </div>
              <div className="student-parcours-card__body">
                <div className="student-parcours-tags">
                  <span className={`student-parcours-tags__format student-parcours-tags__format--${session.format_type}`}>{formatLabels[session.format_type]}</span>
                  <span className="student-parcours-tags__mode">{session.dashboard_type === 'classic' ? 'Autonome' : 'Guidé'}</span>
                </div>
                <h2>{session.formation_title}</h2>
                <p>{session.session_label || 'Session à venir'}</p>
                <Link className="student-parcours-card__link" to={`/app/student/${session.dashboard_type}/${session.enrollment_id}`}>
                  {session.dashboard_type === 'classic' ? 'Accéder au parcours' : session.format_type === 'presentiel' ? 'Ouvrir le suivi scolaire' : 'Accéder au parcours guidé'}
                </Link>
              </div>
            </article>)}
          </div>
        )}
      </>}
    </main>
  )
}
