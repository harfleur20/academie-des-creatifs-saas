import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Search, Users } from 'lucide-react'
import {
  ApiError,
  getSchoolPedagogyOverview,
  type SchoolPedagogyOverview,
} from '../lib/api'

function pct(value: number | null) {
  return value === null ? '—' : value.toFixed(0) + '%'
}

export function PedagogicalMonitoringPage() {
  const [data, setData] = useState<SchoolPedagogyOverview | null>(null)
  const [query, setQuery] = useState('')
  const [riskOnly, setRiskOnly] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getSchoolPedagogyOverview()
      .then(setData)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Chargement impossible.'),
      )
  }, [])

  const rows = useMemo(() => {
    if (!data) return []
    const needle = query.trim().toLowerCase()
    return data.students.filter((row) => {
      if (riskOnly && row.alert_level === 'good') return false
      if (!needle) return true
      return [
        row.student_name,
        row.student_code || '',
        row.formation_title,
        row.session_label,
      ].some((value) => value.toLowerCase().includes(needle))
    })
  }, [data, query, riskOnly])

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
          <section className="management-kpi-grid">
            <article><Users size={18}/><strong>{data.active_students}</strong><span>Étudiants actifs</span></article>
            <article><CheckCircle2 size={18}/><strong>{pct(data.average_progress_pct)}</strong><span>Progression moyenne</span></article>
            <article><AlertTriangle size={18}/><strong>{data.at_risk_students}</strong><span>À surveiller</span></article>
            <article><CheckCircle2 size={18}/><strong>{data.pending_reviews_count}</strong><span>Corrections en attente</span></article>
          </section>

          <section className="app-card monitoring-table-card">
            <div className="monitoring-toolbar">
              <div className="management-search"><Search size={15}/><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Nom, matricule, formation, session…"/></div>
              <label><input type="checkbox" checked={riskOnly} onChange={(e)=>setRiskOnly(e.target.checked)}/> Afficher uniquement les alertes</label>
            </div>
            <div className="monitoring-table">
              <div className="monitoring-row is-head"><span>Étudiant</span><span>Parcours</span><span>Progression</span><span>Présence</span><span>Résultats</span><span>Signal</span></div>
              {rows.map((row)=><div className="monitoring-row" key={row.enrollment_id}>
                <span><strong>{row.student_name}</strong><small>{row.student_code || '—'} · {row.enrollment_status}</small></span>
                <span><strong>{row.formation_title}</strong><small>{row.session_label}</small></span>
                <span>{pct(row.progress_pct)}<small>{row.submitted_assignments}/{row.total_assignments} devoirs</small></span>
                <span>{pct(row.attendance_pct)}</span>
                <span>{pct(row.grade_average_pct)}<small>{row.attempted_quizzes}/{row.total_quizzes} évaluations</small></span>
                <span><b className={'monitoring-signal '+row.alert_level}>{row.alert_level==='good'?'Stable':row.alert_level==='danger'?'À traiter':'À surveiller'}</b>{row.alert_reasons.map((reason)=><small key={reason}>{reason}</small>)}</span>
              </div>)}
              {rows.length===0&&<div className="empty-row">Aucun étudiant ne correspond aux filtres.</div>}
            </div>
          </section>
        </>
      )}
    </main>
  )
}
