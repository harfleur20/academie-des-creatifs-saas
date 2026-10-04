import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, Banknote, CalendarDays, GraduationCap, TrendingUp, Users } from 'lucide-react'
import {
  ApiError,
  getCommercialDashboard,
  getSchoolPedagogyOverview,
  type CommercialDashboard,
  type SchoolPedagogyOverview,
} from '../lib/api'
import { formatSchoolMoney } from '../public/publicHelpers'

const pct = (value: number | null) => value === null ? '—' : value.toFixed(1) + '%'
const errorMessage = (error: unknown) => error instanceof ApiError ? error.message : 'Chargement impossible.'

export function SchoolPerformancePage() {
  const [pedagogy, setPedagogy] = useState<SchoolPedagogyOverview | null>(null)
  const [commerce, setCommerce] = useState<CommercialDashboard | null>(null)
  const [pedagogyError, setPedagogyError] = useState('')
  const [commerceError, setCommerceError] = useState('')
  const [loading, setLoading] = useState(true)
  const moneyByCurrency = (field: 'collected_cents' | 'outstanding_cents') =>
    commerce?.totals_by_currency.length
      ? commerce.totals_by_currency.map((row) => formatSchoolMoney(row[field], row.currency)).join(' · ')
      : '—'

  useEffect(() => {
    let active = true
    void Promise.allSettled([getSchoolPedagogyOverview(), getCommercialDashboard()])
      .then(([pedagogyResult, commerceResult]) => {
        if (!active) return
        if (pedagogyResult.status === 'fulfilled') setPedagogy(pedagogyResult.value)
        else setPedagogyError(`Suivi pédagogique : ${errorMessage(pedagogyResult.reason)}`)
        if (commerceResult.status === 'fulfilled') setCommerce(commerceResult.value)
        else setCommerceError(`Commerce : ${errorMessage(commerceResult.reason)}`)
        setLoading(false)
      })
    return () => { active = false }
  }, [])

  return <main className="app-page school-performance-page">
    <header className="app-page-header">
      <div><span className="page-kicker">Pilotage</span><h1>Performance</h1><p>Revenus, inscriptions, qualité des sessions et performance des enseignants.</p></div>
    </header>
    {loading && <div className="page-state">Chargement des indicateurs…</div>}
    {pedagogyError && <div className="form-error">{pedagogyError}</div>}
    {commerceError && <div className="form-error">{commerceError}</div>}
    {(pedagogy || commerce) && <section className="management-kpi-grid performance-kpis">
      {commerce && <article><Banknote size={18}/><strong>{moneyByCurrency('collected_cents')}</strong><span>Encaissé</span></article>}
      {pedagogy && <>
        <article><Users size={18}/><strong>{pedagogy.active_students}</strong><span>Étudiants actifs</span></article>
        <article><Activity size={18}/><strong>{pct(pedagogy.average_progress_pct)}</strong><span>Progression moyenne</span></article>
        <article><AlertTriangle size={18}/><strong>{pedagogy.at_risk_students}</strong><span>Alertes pédagogiques</span></article>
      </>}
    </section>}
    {pedagogy && <>
      <section className="app-card performance-school-card">
        <div className="settings-section-heading"><div><span className="section-label">Sessions</span><h2>Sessions à surveiller</h2></div><CalendarDays size={18}/></div>
        <div className="performance-school-table">
          <div className="performance-school-row is-head"><span>Session</span><span>Inscrits</span><span>Remplissage</span><span>Progression</span><span>Présence</span><span>Corrections</span><span>Alertes</span></div>
          {pedagogy.sessions.map((row) => <div className="performance-school-row" key={row.session_id}><span><strong>{row.formation_title}</strong><small>{row.session_label} · {row.status}</small></span><span>{row.enrolled_count}/{row.seat_capacity || '—'}</span><span>{pct(row.fill_rate_pct)}</span><span>{pct(row.progress_pct)}</span><span>{pct(row.attendance_rate_pct)}</span><span>{row.pending_reviews_count}</span><span>{row.at_risk_count}</span></div>)}
          {pedagogy.sessions.length === 0 && <div className="empty-row">Aucune session pour cette école.</div>}
        </div>
      </section>
      <section className="app-card performance-school-card">
        <div className="settings-section-heading"><div><span className="section-label">Enseignants</span><h2>Performance pédagogique</h2></div><GraduationCap size={18}/></div>
        <div className="performance-school-table teacher">
          <div className="performance-school-row is-head"><span>Enseignant</span><span>Sessions</span><span>Étudiants</span><span>Progression</span><span>Présence</span><span>Corrections</span></div>
          {pedagogy.teachers.map((row) => <div className="performance-school-row" key={row.teacher_id}><span><strong>{row.teacher_name}</strong><small>{row.teacher_code || '—'}</small></span><span>{row.sessions_count}</span><span>{row.students_count}</span><span>{pct(row.progress_pct)}</span><span>{pct(row.attendance_rate_pct)}</span><span>{row.pending_reviews_count}</span></div>)}
          {pedagogy.teachers.length === 0 && <div className="empty-row">Aucun enseignant affecté à une session.</div>}
        </div>
      </section>
    </>}
    {commerce && <section className="performance-commercial-summary">
      <article><TrendingUp/><div><strong>{commerce.order_count}</strong><span>Commandes</span></div></article>
      <article><Banknote/><div><strong>{moneyByCurrency('outstanding_cents')}</strong><span>Reste à encaisser</span></div></article>
      <article><AlertTriangle/><div><strong>{commerce.late_installments}</strong><span>Échéances en retard</span></div></article>
    </section>}
  </main>
}
