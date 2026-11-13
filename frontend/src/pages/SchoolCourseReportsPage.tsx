import { useEffect, useMemo, useState } from 'react'
import { useTenant } from '../app/TenantContext'
import { PedagogyFilterBar } from '../components/PedagogyFilterBar'
import {
  ApiError, listCourseDayFeedback, listSchoolCourseDayReports, listSchoolMissingCourseDayReports,
  type CourseDayFeedbackReview, type SchoolCourseDayReport, type SchoolMissingCourseDayReport,
} from '../lib/api'
import { usePedagogyFilters, type FilterSession, type FilterTeacher } from '../lib/pedagogyFilters'

const statusLabel: Record<SchoolCourseDayReport['delivery_status'], string> = {
  held: 'Tenue', partial: 'Partielle', not_held: 'Non tenue', interrupted: 'Interrompue',
}
const dateLabel = (value: string) => new Date(value).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
const plural = (count: number, one: string, many: string) => `${count} ${count > 1 ? many : one}`

function lateLabel(endsAt: string) {
  const days = Math.floor((Date.now() - new Date(endsAt).getTime()) / 86_400_000)
  if (days < 1) return 'Terminée aujourd’hui'
  return `En attente depuis ${plural(days, 'jour', 'jours')}`
}

type Tab = 'submitted' | 'missing'

export function SchoolCourseReportsPage() {
  const { activeOrganization } = useTenant()
  const { filters, update, clear, active, matches } = usePedagogyFilters(activeOrganization?.id)
  const [reports, setReports] = useState<SchoolCourseDayReport[]>([])
  const [missing, setMissing] = useState<SchoolMissingCourseDayReport[]>([])
  const [loadedFor, setLoadedFor] = useState<number | null>(null)
  const [tab, setTab] = useState<Tab>('submitted')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [feedback, setFeedback] = useState<CourseDayFeedbackReview[]>([])
  const [status, setStatus] = useState('')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setReports([])
    setMissing([])
    setLoadedFor(null)
    setSelectedId(null)
    setFeedback([])
    if (!activeOrganization) { setLoading(false); return }
    let cancelled = false
    setLoading(true)
    setError('')
    void Promise.all([listSchoolCourseDayReports(), listSchoolMissingCourseDayReports()]).then(([rows, owed]) => {
      if (!cancelled) { setReports(rows); setMissing(owed); setLoadedFor(activeOrganization.id) }
    }).catch((caught) => {
      if (!cancelled) setError(caught instanceof ApiError ? caught.message : 'Comptes rendus impossibles à charger.')
    }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [activeOrganization?.id])

  const visibleReports = loadedFor === activeOrganization?.id ? reports : []
  const visibleMissing = loadedFor === activeOrganization?.id ? missing : []

  // The filters offer the sessions and teachers these course days belong to.
  const { sessions, teachers } = useMemo(() => {
    const bySession = new Map<number, FilterSession>()
    const byTeacher = new Map<number, FilterTeacher>()
    for (const row of [...visibleReports, ...visibleMissing]) {
      const session = bySession.get(row.session_id) ?? {
        id: row.session_id, label: row.session_label, formationId: row.formation_id ?? null,
        formationTitle: row.formation_title, teacherIds: [],
      }
      if (row.teacher_id && !session.teacherIds.includes(row.teacher_id)) session.teacherIds.push(row.teacher_id)
      bySession.set(row.session_id, session)
      if (row.teacher_id && row.teacher_name) byTeacher.set(row.teacher_id, { id: row.teacher_id, name: row.teacher_name })
    }
    return { sessions: [...bySession.values()], teachers: [...byTeacher.values()] }
  }, [visibleReports, visibleMissing])

  const needle = query.trim().toLocaleLowerCase('fr-FR')
  const filteredReports = useMemo(() => visibleReports.filter((report) => {
    if (!matches({ formationId: report.formation_id, sessionId: report.session_id, teacherIds: report.teacher_id ? [report.teacher_id] : [], date: report.scheduled_at })) return false
    if (status && report.delivery_status !== status) return false
    const haystack = `${report.formation_title} ${report.session_label} ${report.title} ${report.teacher_name || ''}`.toLocaleLowerCase('fr-FR')
    return haystack.includes(needle)
  }), [visibleReports, matches, status, needle])
  const filteredMissing = useMemo(() => visibleMissing.filter((day) => {
    if (!matches({ formationId: day.formation_id, sessionId: day.session_id, teacherIds: day.teacher_id ? [day.teacher_id] : [], date: day.scheduled_at })) return false
    const haystack = `${day.formation_title} ${day.session_label} ${day.title} ${day.teacher_name || ''}`.toLocaleLowerCase('fr-FR')
    return haystack.includes(needle)
  }), [visibleMissing, matches, needle])

  // The first report of the list is open unless another one is chosen.
  const selected = filteredReports.find((report) => report.course_day_id === selectedId) ?? filteredReports[0]

  useEffect(() => {
    if (!selected) { setFeedback([]); return }
    let cancelled = false
    void listCourseDayFeedback(selected.course_day_id).then((rows) => {
      if (!cancelled) setFeedback(rows)
    }).catch((caught) => {
      if (!cancelled) setError(caught instanceof ApiError ? caught.message : 'Avis impossibles à charger.')
    })
    return () => { cancelled = true }
  }, [selected?.course_day_id, activeOrganization?.id])

  return <main className="app-page school-course-reports-page">
    <header className="app-page-header"><div><span className="page-kicker">Suivi pédagogique</span><h1>Comptes rendus</h1><p>Rapports des séances, avis des étudiants, et séances dont le compte rendu se fait attendre.</p></div></header>
    {error && <div className="form-error">{error}</div>}
    {loading ? <div className="page-state">Chargement des comptes rendus…</div> : <>
      <PedagogyFilterBar filters={filters} update={update} clear={clear} active={active} sessions={sessions} teachers={teachers} showPeriod>
        <label className="pedagogy-filters__search">
          <span>Recherche</span>
          <input type="search" placeholder="Séance, formation ou professeur" value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        {tab === 'submitted' && (
          <label>
            <span>Déroulement</span>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">Tous les déroulements</option>
              {Object.entries(statusLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
        )}
      </PedagogyFilterBar>

      <div className="course-reports-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'submitted'} className={tab === 'submitted' ? 'is-active' : ''} onClick={() => setTab('submitted')}>
          Remis <span>{filteredReports.length}</span>
        </button>
        <button type="button" role="tab" aria-selected={tab === 'missing'} className={`${tab === 'missing' ? 'is-active' : ''}${filteredMissing.length ? ' has-missing' : ''}`} onClick={() => setTab('missing')}>
          Manquants <span>{filteredMissing.length}</span>
        </button>
      </div>

      {tab === 'submitted' ? (
        <div className="course-reports-layout">
          <section className="app-card course-reports-list" aria-label="Liste des comptes rendus">
            <p className="course-reports-count">{plural(filteredReports.length, 'compte rendu', 'comptes rendus')}</p>
            {filteredReports.map((report) => <button key={report.course_day_id} type="button" className={selected?.course_day_id === report.course_day_id ? 'is-active' : ''} onClick={() => { setError(''); setSelectedId(report.course_day_id) }}>
              <strong>{report.title}</strong><span>{report.formation_title} · {report.session_label}</span><small>{dateLabel(report.scheduled_at)} · {statusLabel[report.delivery_status]}{report.teacher_name ? ` · ${report.teacher_name}` : ''}</small>
            </button>)}
            {filteredReports.length === 0 && <p>Aucun compte rendu pour ces critères.</p>}
          </section>
          {selected && <section className="app-card course-reports-detail">
            <span className="section-label">{statusLabel[selected.delivery_status]}</span><h2>{selected.title}</h2>
            <p>{selected.formation_title} · {selected.session_label}</p>
            <p>Prof. {selected.teacher_name || '—'} · {dateLabel(selected.scheduled_at)}</p>
            <p>Rapport remis le {dateLabel(selected.submitted_at)}</p>
            <h3>Compte rendu du professeur</h3><p className="course-report-summary">{selected.summary}</p>
            {selected.difficulties && <p><strong>Difficultés :</strong> {selected.difficulties}</p>}
            {selected.homework && <p><strong>Travail à faire :</strong> {selected.homework}</p>}
            {selected.attendance_notes && <p><strong>Présences :</strong> {selected.attendance_notes}</p>}
            <h3>Avis étudiants</h3><p>{plural(selected.feedback_count, 'avis', 'avis')}{selected.average_rating !== null ? ` · ${selected.average_rating}/5` : ''}</p>
            {feedback.map((item) => <div className="course-report-feedback" key={item.id}><strong>{item.student_name} · {item.rating}/5</strong><span>{item.delivery_status === 'held' ? 'Séance tenue' : item.delivery_status === 'partial' ? 'Séance partielle' : 'Séance non tenue'}</span>{item.comment && <p>{item.comment}</p>}</div>)}
          </section>}
        </div>
      ) : (
        <section className="app-card course-reports-missing" aria-label="Séances sans compte rendu">
          <p className="course-reports-count">
            {filteredMissing.length
              ? `${plural(filteredMissing.length, 'séance terminée attend', 'séances terminées attendent')} le compte rendu du professeur.`
              : 'Toutes les séances terminées ont leur compte rendu.'}
          </p>
          {filteredMissing.length > 0 && (
            <div className="course-reports-missing__table">
              <div className="course-reports-missing__row is-head"><span>Séance</span><span>Formation · session</span><span>Date</span><span>Professeur</span><span>Attente</span></div>
              {filteredMissing.map((day) => (
                <div className="course-reports-missing__row" key={day.course_day_id}>
                  <strong>{day.title}</strong>
                  <span>{day.formation_title} · {day.session_label}</span>
                  <span>{dateLabel(day.scheduled_at)}</span>
                  <span>{day.teacher_name || 'Sans professeur'}</span>
                  <span className="course-reports-missing__late">{lateLabel(day.ends_at)}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </>}
  </main>
}
