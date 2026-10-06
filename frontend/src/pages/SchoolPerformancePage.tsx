import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, Banknote, CalendarDays, GraduationCap, TrendingUp, Users } from 'lucide-react'
import {
  ApiError,
  getCommercialDashboard,
  getSchoolPedagogyOverview,
  type CommercialDashboard,
  type SchoolPedagogyOverview,
} from '../lib/api'
import { ChartCanvas } from '../components/ChartCanvas'
import { formatSchoolMoney } from '../public/publicHelpers'
import '../statistics.css'

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

  const sessions = pedagogy?.sessions.slice(0, 8) ?? []
  const teachers = pedagogy?.teachers.slice(0, 8) ?? []
  const paidOrders = commerce?.paid_order_count ?? 0
  const totalOrders = commerce?.order_count ?? 0
  const unpaidOrders = Math.max(0, totalOrders - paidOrders)

  return <main className="app-page school-statistics-page">
    <header className="app-page-header">
      <div>
        <span className="page-kicker">Pilotage</span>
        <h1>Statistiques</h1>
        <p>Suivez les ventes, les inscriptions et la performance pédagogique avec des graphiques interactifs.</p>
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
                <p>Comparez le niveau d’avancement des sessions les plus actives.</p>
              </div>
              <TrendingUp size={20}/>
            </div>
            {sessions.length > 0 ? <ChartCanvas
              type="bar"
              horizontal
              max={100}
              valueSuffix="%"
              height={Math.max(280, sessions.length * 48)}
              labels={sessions.map((row) => row.session_label || row.formation_title)}
              datasets={[{ label: 'Progression', data: sessions.map((row) => row.progress_pct) }]}
            /> : <div className="statistics-empty">Aucune session à afficher pour le moment.</div>}
          </article>

          <article className="statistics-chart-card">
            <div className="statistics-chart-heading">
              <div>
                <span className="section-label">Sessions</span>
                <h2>Remplissage et présence</h2>
                <p>Deux indicateurs essentiels pour repérer les sessions à renforcer.</p>
              </div>
              <CalendarDays size={20}/>
            </div>
            {sessions.length > 0 ? <ChartCanvas
              type="bar"
              max={100}
              valueSuffix="%"
              showLegend
              height={320}
              labels={sessions.map((row) => row.session_label || row.formation_title)}
              datasets={[
                { label: 'Remplissage', data: sessions.map((row) => row.fill_rate_pct) },
                { label: 'Présence', data: sessions.map((row) => row.attendance_rate_pct ?? 0) },
              ]}
            /> : <div className="statistics-empty">Les comparaisons apparaîtront dès qu’une session aura des données.</div>}
          </article>

          {teachers.length > 0 && <article className="statistics-chart-card">
            <div className="statistics-chart-heading">
              <div>
                <span className="section-label">Enseignants</span>
                <h2>Progression des groupes</h2>
                <p>La progression moyenne des étudiants suivis par chaque enseignant.</p>
              </div>
              <GraduationCap size={20}/>
            </div>
            <ChartCanvas
              type="bar"
              horizontal
              max={100}
              valueSuffix="%"
              height={Math.max(260, teachers.length * 48)}
              labels={teachers.map((row) => row.teacher_name)}
              datasets={[{ label: 'Progression', data: teachers.map((row) => row.progress_pct) }]}
            />
          </article>}
        </div>

        <aside className="statistics-stack">
          <article className="statistics-chart-card">
            <div className="statistics-chart-heading">
              <div><span className="section-label">Commerce</span><h3>Commandes réglées</h3><p>Répartition des commandes payées et restantes.</p></div>
              <Banknote size={19}/>
            </div>
            {totalOrders > 0 ? <ChartCanvas
              type="doughnut"
              showLegend
              height={250}
              labels={['Réglées', 'À régler']}
              datasets={[{ label: 'Commandes', data: [paidOrders, unpaidOrders] }]}
            /> : <div className="statistics-empty">Les commandes apparaîtront ici après les premières ventes.</div>}
          </article>

          <article className="statistics-chart-card">
            <div className="statistics-chart-heading">
              <div><span className="section-label">Santé pédagogique</span><h3>Vue d’ensemble</h3><p>Progression et présence moyennes de l’école.</p></div>
              <Activity size={19}/>
            </div>
            {pedagogy ? <ChartCanvas
              type="bar"
              max={100}
              valueSuffix="%"
              height={240}
              labels={['Progression', 'Présence']}
              datasets={[{
                label: 'Moyenne',
                data: [pedagogy.average_progress_pct, pedagogy.average_attendance_pct ?? 0],
              }]}
            /> : <div className="statistics-empty">Données pédagogiques indisponibles.</div>}
          </article>
        </aside>
      </section>
    </>}
  </main>
}
