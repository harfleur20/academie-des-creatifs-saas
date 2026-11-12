import type { ReactNode } from 'react'
import { X } from 'lucide-react'
import { filterFormations, type FilterSession, type FilterTeacher, type PedagogyFilters } from '../lib/pedagogyFilters'
import '../pedagogy-filters.css'

type Props = {
  filters: PedagogyFilters
  update: (changes: Partial<PedagogyFilters>) => void
  clear: () => void
  active: boolean
  sessions: FilterSession[]
  teachers?: FilterTeacher[]
  showPeriod?: boolean
  children?: ReactNode
}

/** Formation, then its session, the teacher and the period: the same filters on every pedagogy page. */
export function PedagogyFilterBar({ filters, update, clear, active, sessions, teachers, showPeriod, children }: Props) {
  const formations = filterFormations(sessions)
  const sessionOptions = sessions
    .filter((session) => !filters.formation || session.formationId === filters.formation)
    .sort((a, b) => a.formationTitle.localeCompare(b.formationTitle, 'fr') || a.label.localeCompare(b.label, 'fr'))

  return (
    <div className="pedagogy-filters" role="search" aria-label="Filtres">
      <label>
        <span>Formation</span>
        <select value={filters.formation ?? ''} onChange={(event) => update({ formation: event.target.value ? Number(event.target.value) : null })}>
          <option value="">Toutes les formations</option>
          {formations.map((formation) => <option key={formation.id} value={formation.id}>{formation.title}</option>)}
        </select>
      </label>
      <label>
        <span>Session</span>
        <select value={filters.session ?? ''} onChange={(event) => {
          const id = event.target.value ? Number(event.target.value) : null
          const session = sessions.find((item) => item.id === id)
          update({ session: id, ...(session?.formationId ? { formation: session.formationId } : {}) })
        }}>
          <option value="">Toutes les sessions</option>
          {sessionOptions.map((session) => (
            <option key={session.id} value={session.id}>
              {filters.formation ? session.label : `${session.formationTitle} · ${session.label}`}
            </option>
          ))}
        </select>
      </label>
      {teachers && teachers.length > 0 && (
        <label>
          <span>Professeur</span>
          <select value={filters.teacher ?? ''} onChange={(event) => update({ teacher: event.target.value ? Number(event.target.value) : null })}>
            <option value="">Tous les professeurs</option>
            {[...teachers].sort((a, b) => a.name.localeCompare(b.name, 'fr')).map((teacher) => (
              <option key={teacher.id} value={teacher.id}>{teacher.name}</option>
            ))}
          </select>
        </label>
      )}
      {showPeriod && (
        <>
          <label>
            <span>Du</span>
            <input type="date" value={filters.from} max={filters.to || undefined} onChange={(event) => update({ from: event.target.value })} />
          </label>
          <label>
            <span>Au</span>
            <input type="date" value={filters.to} min={filters.from || undefined} onChange={(event) => update({ to: event.target.value })} />
          </label>
        </>
      )}
      {children}
      {active && (
        <button type="button" className="pedagogy-filters__clear" onClick={clear}>
          <X size={14} /> Effacer les filtres
        </button>
      )}
    </div>
  )
}
