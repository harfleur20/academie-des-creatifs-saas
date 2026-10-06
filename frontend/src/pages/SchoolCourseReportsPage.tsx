import { useEffect, useMemo, useState } from 'react'
import { useTenant } from '../app/TenantContext'
import {
  ApiError, listCourseDayFeedback, listSchoolCourseDayReports,
  type CourseDayFeedbackReview, type SchoolCourseDayReport,
} from '../lib/api'

const statusLabel: Record<SchoolCourseDayReport['delivery_status'], string> = {
  held: 'Tenue', partial: 'Partielle', not_held: 'Non tenue', interrupted: 'Interrompue',
}
const dateLabel = (value: string) => new Date(value).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })

export function SchoolCourseReportsPage() {
  const { activeOrganization } = useTenant()
  const [reports, setReports] = useState<SchoolCourseDayReport[]>([])
  const [reportsOrganizationId, setReportsOrganizationId] = useState<number | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [feedback, setFeedback] = useState<CourseDayFeedbackReview[]>([])
  const [status, setStatus] = useState('')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setReports([])
    setReportsOrganizationId(null)
    setSelectedId(null)
    setFeedback([])
    if (!activeOrganization) { setLoading(false); return }
    let cancelled = false
    setLoading(true)
    setError('')
    void listSchoolCourseDayReports().then((rows) => {
      if (!cancelled) { setReports(rows); setReportsOrganizationId(activeOrganization.id) }
    }).catch((caught) => {
      if (!cancelled) setError(caught instanceof ApiError ? caught.message : 'Comptes rendus impossibles à charger.')
    }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [activeOrganization?.id])

  useEffect(() => {
    if (selectedId === null) { setFeedback([]); return }
    let cancelled = false
    void listCourseDayFeedback(selectedId).then((rows) => {
      if (!cancelled) setFeedback(rows)
    }).catch((caught) => {
      if (!cancelled) setError(caught instanceof ApiError ? caught.message : 'Avis impossibles à charger.')
    })
    return () => { cancelled = true }
  }, [selectedId, activeOrganization?.id])

  const visibleReports = reportsOrganizationId === activeOrganization?.id ? reports : []
  const filtered = useMemo(() => visibleReports.filter((report) => {
    if (status && report.delivery_status !== status) return false
    const haystack = `${report.formation_title} ${report.session_label} ${report.title} ${report.teacher_name || ''}`.toLocaleLowerCase('fr-FR')
    return haystack.includes(query.trim().toLocaleLowerCase('fr-FR'))
  }), [visibleReports, status, query])
  const selected = filtered.find((report) => report.course_day_id === selectedId)

  return <main className="app-page school-course-reports-page">
    <header className="app-page-header"><div><span className="page-kicker">Suivi pédagogique</span><h1>Comptes rendus</h1><p>Rapports des séances et avis des étudiants de cette école.</p></div></header>
    {error && <div className="form-error">{error}</div>}
    {loading ? <div className="page-state">Chargement des comptes rendus…</div> : <>
      <div className="course-reports-filters">
        <input type="search" aria-label="Rechercher un compte rendu" placeholder="Formation, session, séance ou professeur" value={query} onChange={(event) => setQuery(event.target.value)} />
        <select aria-label="Filtrer par déroulement" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">Tous les déroulements</option>{Object.entries(statusLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
      </div>
      <p>{filtered.length} compte rendu{filtered.length > 1 ? 's' : ''}</p>
      <div className="course-reports-layout">
        <section className="app-card course-reports-list" aria-label="Liste des comptes rendus">
          {filtered.map((report) => <button key={report.course_day_id} type="button" className={selectedId === report.course_day_id ? 'is-active' : ''} onClick={() => { setError(''); setFeedback([]); setSelectedId(report.course_day_id) }}>
            <strong>{report.title}</strong><span>{report.formation_title} · {report.session_label}</span><small>{dateLabel(report.scheduled_at)} · {statusLabel[report.delivery_status]}</small>
          </button>)}
          {filtered.length === 0 && <p>Aucun compte rendu pour ces critères.</p>}
        </section>
        {selected && <section className="app-card course-reports-detail">
          <span className="section-label">{statusLabel[selected.delivery_status]}</span><h2>{selected.title}</h2>
          <p>{selected.formation_title} · {selected.session_label}</p>
          <p>Prof. {selected.teacher_name || '—'} · {dateLabel(selected.scheduled_at)}</p>
          <p>Rapport remis le {dateLabel(selected.submitted_at)}</p>
          <h3>Compte rendu du professeur</h3><p className="course-report-summary">{selected.summary}</p>
          <h3>Avis étudiants</h3><p>{selected.feedback_count} avis{selected.average_rating !== null ? ` · ${selected.average_rating}/5` : ''}</p>
          {feedback.map((item) => <div className="course-report-feedback" key={item.id}><strong>{item.student_name} · {item.rating}/5</strong><span>{item.delivery_status === 'held' ? 'Séance tenue' : item.delivery_status === 'partial' ? 'Séance partielle' : 'Séance non tenue'}</span>{item.comment && <p>{item.comment}</p>}</div>)}
        </section>}
      </div>
    </>}
  </main>
}
