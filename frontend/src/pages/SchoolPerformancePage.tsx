import { useEffect, useState, type CSSProperties } from 'react'
import { Activity, AlertTriangle, Banknote, CalendarDays, GraduationCap, TrendingUp, Users } from 'lucide-react'
import {
  ApiError,
  getCommercialDashboard,
  getSchoolPedagogyOverview,
  type CommercialDashboard,
  type SchoolPedagogyOverview,
} from '../lib/api'
import { formatSchoolMoney } from '../public/publicHelpers'
import '../statistics.css'

const pct = (value: number | null) => value === null ? '—' : value.toFixed(1) + '%'
const errorMessage = (error: unknown) => error instanceof ApiError ? error.message : 'Chargement impossible.'
const clampPercent = (value: number | null | undefined) => Math.max(0, Math.min(100, value ?? 0))
const barStyle = (value: number | null | undefined) => ({ '--bar-value': `${clampPercent(value)}%` } as CSSProperties)

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

  const paidOrderRate = commerce && commerce.order_count > 0
    ? Math.round((commerce.paid_order_count / commerce.order_count) * 100)
    : 0
  const donutOffset = 314.16 * (1 - paidOrderRate / 100)
  const sessions = pedagogy?.sessions.slice(0, 8) ?? []
  const teachers = pedagogy?.teachers.slice(0, 6) ?? []

  return <main className="app-page school-statistics-page">
    <header className="app-page-header">
      <div>
        <span className="page-kicker">Pilotage</span>
        <h1>Statistiques</h1>
        <p>Une vue visuelle des ventes, inscriptions, sessions et performances pédagogiques de l’école.</p>
      </div>
    </header>

    {loading && <div className="page-state">Chargement des statistiques…</div>}
    {pedagogyError && <div className="form-error">{pedagogyError}</div>}
    {commerceError && <div className="form-error">{commerceError}</div>}

    {(pedagogy || commerce) && <>
      <section className="statistics-kpi-grid">
        <article className="statistics-kpi-card">
          <span><Users size={16}/> Étudiants actifs</span>
          <strong>{pedagogy?.active_students ?? commerce?.active_students ?? '—'}</strong>
          <small>{pedagogy ? `${pedagogy.active_sessions} session(s) active(s)` : 'Donnée commerciale disponible'}</small>
        </article>
        <article className="statistics-kpi-card">
          <span><Activity size={16}/> Progression moyenne</span>
          <strong>{pedagogy ? pct(pedagogy.average_progress_pct) : '—'}</strong>
          <small>{pedagogy ? `${pedagogy.at_risk_students} étudiant(s) à surveiller` : 'Donnée pédagogique indisponible'}</small>
        </article>
        <article className="statistics-kpi-card">
          <span><Banknote size={16}/> Encaissé</span>
          <strong>{commerce ? moneyByCurrency('collected_cents') : '—'}</strong>
          <small>{commerce ? `${commerce.paid_order_count}/${commerce.order_count} commande(s) réglée(s)` : 'Donnée commerciale indisponible'}</small>
        </article>
        <article className="statistics-kpi-card">
          <span><AlertTriangle size={16}/> Paiements en retard</span>
          <strong>{commerce?.late_installments ?? '—'}</strong>
          <small>{commerce ? `${moneyByCurrency('outstanding_cents')} restant à encaisser` : 'Donnée commerciale indisponible'}</small>
        </article>
      </section>

      <section className="statistics-layout">
        <div className="statistics-stack">
          <article className="statistics-chart-card">
            <div className="statistics-chart-heading">
              <div>
                <span className="section-label">Pédagogie</span>
                <h2>Progression par session</h2>
                <p>Les sessions les plus actives et leur niveau d’avancement.</p>
              </div>
              <TrendingUp size={20}/>
            </div>
            {sessions.length > 0 ? <div className="statistics-bar-list">
              {sessions.map((row) => <div className="statistics-bar-row" key={row.session_id}>
                <div className="statistics-bar-label">
                  <strong>{row.formation_title}</strong>
                  <small>{row.session_label}</small>
                </div>
                <div className="statistics-bar-track"><div className="statistics-bar-fill" style={barStyle(row.progress_pct)} /></div>
                <span className="statistics-bar-value">{pct(row.progress_pct)}</span>
              </div>)}
            </div> : <div className="statistics-empty">Aucune session à afficher pour le moment.</div>}
          </article>

          <article className="statistics-chart-card">
            <div className="statistics-chart-heading">
              <div>
                <span className="section-label">Sessions</span>
                <h2>Présence et remplissage</h2>
                <p>Comparez le remplissage de chaque session à son taux de présence.</p>
              </div>
              <CalendarDays size={20}/>
            </div>
            {sessions.length > 0 ? <div className="statistics-comparison-list">
              {sessions.map((row) => <div className="statistics-comparison-row" key={row.session_id}>
                <div><strong>{row.formation_title}</strong><small>{row.enrolled_count} inscrit(s)</small></div>
                <div className="statistics-comparison-bars">
                  <div className="statistics-bar-track" title={`Remplissage ${pct(row.fill_rate_pct)}`}><div className="statistics-bar-fill" style={barStyle(row.fill_rate_pct)} /></div>
                  <div className="statistics-bar-track is-secondary" title={`Présence ${pct(row.attendance_rate_pct)}`}><div className="statistics-bar-fill" style={barStyle(row.attendance_rate_pct)} /></div>
                </div>
              </div>)}
            </div> : <div className="statistics-empty">Les comparaisons apparaîtront dès qu’une session aura des données.</div>}
          </article>

          {teachers.length > 0 && <article className="statistics-chart-card">
            <div className="statistics-chart-heading">
              <div>
                <span className="section-label">Enseignants</span>
                <h2>Progression des étudiants par enseignant</h2>
                <p>Une lecture rapide des groupes suivis par l’équipe pédagogique.</p>
              </div>
              <GraduationCap size={20}/>
            </div>
            <div className="statistics-bar-list">
              {teachers.map((row) => <div className="statistics-bar-row" key={row.teacher_id}>
                <div className="statistics-bar-label"><strong>{row.teacher_name}</strong><small>{row.students_count} étudiant(s) · {row.sessions_count} session(s)</small></div>
                <div className="statistics-bar-track"><div className="statistics-bar-fill" style={barStyle(row.progress_pct)} /></div>
                <span className="statistics-bar-value">{pct(row.progress_pct)}</span>
              </div>)}
            </div>
          </article>}
        </div>

        <aside className="statistics-stack">
          <article className="statistics-chart-card">
            <div className="statistics-chart-heading">
              <div><span className="section-label">Commerce</span><h3>Commandes réglées</h3></div>
              <Banknote size={19}/>
            </div>
            <div className="statistics-donut-wrap">
              <svg className="statistics-donut" viewBox="0 0 120 120" aria-label={`${paidOrderRate}% des commandes réglées`}>
                <circle className="track" cx="60" cy="60" r="50" />
                <circle className="value" cx="60" cy="60" r="50" style={{ '--donut-offset': donutOffset } as CSSProperties} />
              </svg>
              <div className="statistics-donut-copy">
                <strong>{paidOrderRate}%</strong>
                <span>des commandes sont réglées</span>
                <small>{commerce?.paid_order_count ?? 0} sur {commerce?.order_count ?? 0}</small>
              </div>
            </div>
          </article>

          <article className="statistics-chart-card">
            <div className="statistics-chart-heading">
              <div><span className="section-label">Santé pédagogique</span><h3>Vue d’ensemble</h3></div>
              <Activity size={19}/>
            </div>
            <div className="statistics-bar-list">
              <div className="statistics-bar-row">
                <div className="statistics-bar-label"><strong>Progression</strong><small>Moyenne école</small></div>
                <div className="statistics-bar-track"><div className="statistics-bar-fill" style={barStyle(pedagogy?.average_progress_pct)} /></div>
                <span className="statistics-bar-value">{pedagogy ? pct(pedagogy.average_progress_pct) : '—'}</span>
              </div>
              <div className="statistics-bar-row">
                <div className="statistics-bar-label"><strong>Présence</strong><small>Moyenne école</small></div>
                <div className="statistics-bar-track"><div className="statistics-bar-fill" style={barStyle(pedagogy?.average_attendance_pct)} /></div>
                <span className="statistics-bar-value">{pedagogy ? pct(pedagogy.average_attendance_pct) : '—'}</span>
              </div>
            </div>
          </article>
        </aside>
      </section>
    </>}
  </main>
}
