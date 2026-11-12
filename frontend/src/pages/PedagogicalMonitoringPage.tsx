import { Fragment, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ArrowDown, ArrowUp, CheckCircle2, ClipboardList, Download, Search, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import { PedagogyFilterBar } from '../components/PedagogyFilterBar'
import {
  ApiError,
  getSchoolPedagogyOverview,
  type SchoolPedagogyOverview,
  type SchoolPedagogyStudent,
} from '../lib/api'
import { downloadCsv } from '../lib/csv'
import { usePedagogyFilters, type FilterSession } from '../lib/pedagogyFilters'

function pct(value: number | null) {
  return value === null ? '—' : value.toFixed(0) + '%'
}

const SIGNAL_LABEL: Record<SchoolPedagogyStudent['alert_level'], string> = {
  good: 'Stable', warning: 'À surveiller', danger: 'À traiter',
}
const SIGNAL_RANK: Record<SchoolPedagogyStudent['alert_level'], number> = { danger: 0, warning: 1, good: 2 }

type SortKey = 'student' | 'formation' | 'progress' | 'attendance' | 'results' | 'signal'
const COLUMNS: Array<{ key: SortKey; label: string }> = [
  { key: 'student', label: 'Étudiant' },
  { key: 'formation', label: 'Parcours' },
  { key: 'progress', label: 'Progression' },
  { key: 'attendance', label: 'Présence' },
  { key: 'results', label: 'Résultats' },
  { key: 'signal', label: 'Signal' },
]

function sortValue(row: SchoolPedagogyStudent, key: SortKey): string | number {
  switch (key) {
    case 'student': return row.student_name
    case 'formation': return `${row.formation_title} ${row.session_label}`
    case 'progress': return row.progress_pct
    case 'attendance': return row.attendance_pct ?? -1
    case 'results': return row.grade_average_pct ?? -1
    case 'signal': return SIGNAL_RANK[row.alert_level]
  }
}

export function PedagogicalMonitoringPage() {
  const { activeOrganization } = useTenant()
  const { filters, update, clear, active, matches } = usePedagogyFilters(activeOrganization?.id)
  const [data, setData] = useState<SchoolPedagogyOverview | null>(null)
  const [query, setQuery] = useState('')
  const [riskOnly, setRiskOnly] = useState(false)
  const [sort, setSort] = useState<{ key: SortKey; ascending: boolean }>({ key: 'signal', ascending: true })
  const [openId, setOpenId] = useState<number | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getSchoolPedagogyOverview()
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [activeOrganization?.id])

  const sessions = useMemo<FilterSession[]>(() => (data?.sessions ?? []).map((session) => ({
    id: session.session_id,
    label: session.session_label,
    formationId: session.formation_id ?? null,
    formationTitle: session.formation_title,
    teacherIds: session.teacher_ids ?? [],
  })), [data])
  const teachersBySession = useMemo(() => new Map(sessions.map((session) => [session.id, session.teacherIds])), [sessions])

  const rows = useMemo(() => {
    if (!data) return []
    const needle = query.trim().toLowerCase()
    const filtered = data.students.filter((row) => {
      if (!matches({ formationId: row.formation_id, sessionId: row.session_id, teacherIds: teachersBySession.get(row.session_id) })) return false
      if (riskOnly && row.alert_level === 'good') return false
      if (!needle) return true
      return [row.student_name, row.student_code || '', row.formation_title, row.session_label]
        .some((value) => value.toLowerCase().includes(needle))
    })
    return filtered.sort((a, b) => {
      const left = sortValue(a, sort.key)
      const right = sortValue(b, sort.key)
      const order = typeof left === 'string' ? left.localeCompare(String(right), 'fr') : left - Number(right)
      return (sort.ascending ? order : -order) || a.student_name.localeCompare(b.student_name, 'fr')
    })
  }, [data, query, riskOnly, matches, teachersBySession, sort])

  // The figures follow the filters (except the search and the alerts box, which only narrow the list).
  const scoped = useMemo(() => (data?.students ?? []).filter((row) => (
    matches({ formationId: row.formation_id, sessionId: row.session_id, teacherIds: teachersBySession.get(row.session_id) })
  )), [data, matches, teachersBySession])
  const figures = useMemo(() => {
    const scopedSessions = (data?.sessions ?? []).filter((session) => matches({
      formationId: session.formation_id, sessionId: session.session_id, teacherIds: session.teacher_ids,
    }))
    const average = scoped.length ? scoped.reduce((sum, row) => sum + row.progress_pct, 0) / scoped.length : null
    return {
      students: new Set(scoped.map((row) => row.student_id)).size,
      enrollments: scoped.length,
      progress: average,
      atRisk: scoped.filter((row) => row.alert_level !== 'good').length,
      pending: scopedSessions.reduce((sum, session) => sum + session.pending_reviews_count, 0),
    }
  }, [data, scoped, matches])

  function toggleSort(key: SortKey) {
    setSort((current) => current.key === key
      ? { key, ascending: !current.ascending }
      : { key, ascending: key === 'student' || key === 'formation' || key === 'signal' })
  }

  function exportRows() {
    downloadCsv(
      `suivi-pedagogique-${new Date().toISOString().slice(0, 10)}.csv`,
      ['Étudiant', 'Matricule', 'Formation', 'Session', 'Statut', 'Progression (%)', 'Présence (%)', 'Résultats (%)',
        'Devoirs rendus', 'Devoirs', 'Évaluations tentées', 'Évaluations', 'Signal', 'Raisons'],
      rows.map((row) => [
        row.student_name, row.student_code, row.formation_title, row.session_label, row.enrollment_status,
        Math.round(row.progress_pct), row.attendance_pct === null ? null : Math.round(row.attendance_pct),
        row.grade_average_pct === null ? null : Math.round(row.grade_average_pct),
        row.submitted_assignments, row.total_assignments, row.attempted_quizzes, row.total_quizzes,
        SIGNAL_LABEL[row.alert_level], row.alert_reasons.join(' · '),
      ]),
    )
  }

  return (
    <main className="app-page school-monitoring-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Pilotage pédagogique</span>
          <h1>Suivi pédagogique</h1>
          <p>Repérez rapidement les étudiants en difficulté et les actions à mener.</p>
        </div>
      </header>
      {error && <div className="form-error">{error}</div>}

      {data && (
        <>
          <PedagogyFilterBar
            filters={filters} update={update} clear={clear} active={active} sessions={sessions}
            teachers={data.teachers.map((teacher) => ({ id: teacher.teacher_id, name: teacher.teacher_name }))}
          />

          <section className="management-kpi-grid">
            <article>
              <Users size={18}/>
              <strong>{figures.students}</strong>
              <span>Étudiant{figures.students > 1 ? 's' : ''} · {figures.enrollments} inscription{figures.enrollments > 1 ? 's' : ''}</span>
            </article>
            <article><CheckCircle2 size={18}/><strong>{pct(figures.progress)}</strong><span>Progression moyenne</span></article>
            <article><AlertTriangle size={18}/><strong>{figures.atRisk}</strong><span>Inscriptions à surveiller</span></article>
            <article><ClipboardList size={18}/><strong>{figures.pending}</strong><span>Corrections en attente</span></article>
          </section>

          <section className="app-card monitoring-table-card">
            <div className="monitoring-toolbar">
              <div className="management-search"><Search size={15}/><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Nom ou matricule…"/></div>
              <div className="monitoring-toolbar__actions">
                <label><input type="checkbox" checked={riskOnly} onChange={(e) => setRiskOnly(e.target.checked)}/> Uniquement les alertes</label>
                <button className="secondary-button compact-action" type="button" disabled={rows.length === 0} onClick={exportRows}>
                  <Download size={15}/> Exporter (Excel)
                </button>
              </div>
            </div>
            <p className="monitoring-count">{rows.length} inscription{rows.length > 1 ? 's' : ''}</p>
            <div className="monitoring-table">
              <div className="monitoring-row is-head" role="row">
                {COLUMNS.map((column) => (
                  <button
                    key={column.key}
                    type="button"
                    className={`monitoring-sort${sort.key === column.key ? ' is-sorted' : ''}`}
                    onClick={() => toggleSort(column.key)}
                    aria-sort={sort.key === column.key ? (sort.ascending ? 'ascending' : 'descending') : 'none'}
                  >
                    {column.label}
                    {sort.key === column.key && (sort.ascending ? <ArrowUp size={12}/> : <ArrowDown size={12}/>)}
                  </button>
                ))}
              </div>
              {rows.map((row) => (
                <Fragment key={row.enrollment_id}>
                  <button
                    type="button"
                    className={`monitoring-row is-clickable${openId === row.enrollment_id ? ' is-open' : ''}`}
                    aria-expanded={openId === row.enrollment_id}
                    onClick={() => setOpenId(openId === row.enrollment_id ? null : row.enrollment_id)}
                  >
                    <span><strong>{row.student_name}</strong><small>{row.student_code || '—'} · {row.enrollment_status}</small></span>
                    <span><strong>{row.formation_title}</strong><small>{row.session_label}</small></span>
                    <span>{pct(row.progress_pct)}<small>{row.submitted_assignments}/{row.total_assignments} devoirs</small></span>
                    <span>{pct(row.attendance_pct)}</span>
                    <span>{pct(row.grade_average_pct)}<small>{row.attempted_quizzes}/{row.total_quizzes} évaluations</small></span>
                    <span><b className={'monitoring-signal ' + row.alert_level}>{SIGNAL_LABEL[row.alert_level]}</b>{row.alert_reasons.map((reason) => <small key={reason}>{reason}</small>)}</span>
                  </button>
                  {openId === row.enrollment_id && (
                    <div className="monitoring-detail">
                      <dl>
                        <div><dt>Progression</dt><dd>{pct(row.progress_pct)}</dd></div>
                        <div><dt>Devoirs rendus</dt><dd>{row.submitted_assignments} sur {row.total_assignments}</dd></div>
                        <div><dt>Évaluations tentées</dt><dd>{row.attempted_quizzes} sur {row.total_quizzes}</dd></div>
                        <div><dt>Moyenne</dt><dd>{pct(row.grade_average_pct)}</dd></div>
                        <div><dt>Présence</dt><dd>{pct(row.attendance_pct)}</dd></div>
                      </dl>
                      <div className="monitoring-detail__side">
                        <strong>{row.alert_reasons.length ? 'Points d’attention' : 'Aucun point d’attention'}</strong>
                        {row.alert_reasons.length > 0 && <ul>{row.alert_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}
                        <div className="monitoring-detail__actions">
                          <Link className="secondary-button compact-action" to={`/app/manage/students?q=${encodeURIComponent(row.student_code || row.student_name)}`}>
                            Voir sa fiche étudiant
                          </Link>
                          <button type="button" className="secondary-button compact-action" onClick={() => update({ session: row.session_id, formation: row.formation_id ?? null })}>
                            Filtrer sur sa session
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </Fragment>
              ))}
              {rows.length === 0 && <div className="empty-row">Aucun étudiant ne correspond aux filtres.</div>}
            </div>
          </section>
        </>
      )}
    </main>
  )
}
