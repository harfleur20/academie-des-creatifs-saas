import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, Banknote, CalendarDays, GraduationCap, TrendingUp, Users } from 'lucide-react'
import {
  ApiError,
  getCommercialDashboard,
  getSchoolPedagogyOverview,
  listFormations,
  type CommercialDashboard,
  type FormationSummary,
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
  const [formations, setFormations] = useState<FormationSummary[] | null>(null)
  const [pedagogyError, setPedagogyError] = useState('')
  const [commerceError, setCommerceError] = useState('')
  const [formationsError, setFormationsError] = useState('')
  const [loading, setLoading] = useState(true)

  const moneyByCurrency = (field: 'collected_cents' | 'outstanding_cents') =>
    commerce?.totals_by_currency.length
      ? commerce.totals_by_currency.map((row) => formatSchoolMoney(row[field], row.currency)).join(' · ')
      : '—'

  useEffect(() => {
    let active = true
    void Promise.allSettled([getSchoolPedagogyOverview(), getCommercialDashboard(), listFormations()])
      .then(([pedagogyResult, commerceResult, formationsResult]) => {
        if (!active) return
        if (pedagogyResult.status === 'fulfilled') setPedagogy(pedagogyResult.value)
        else setPedagogyError(`Suivi pédagogique : ${errorMessage(pedagogyResult.reason)}`)
        if (commerceResult.status === 'fulfilled') setCommerce(commerceResult.value)
        else setCommerceError(`Commerce : ${errorMessage(commerceResult.reason)}`)
        if (formationsResult.status === 'fulfilled') setFormations(formationsResult.value)
        else setFormationsError(`Formations : ${errorMessage(formationsResult.reason)}`)
        setLoading(false)
      })
    return () => { active = false }
  }, [])

  const sessions = pedagogy?.sessions.slice(0, 8) ?? []
  const sessionsToWatch = pedagogy?.sessions.filter((row) =>
    row.at_risk_count > 0
    || row.pending_reviews_count > 0
    || (row.attendance_rate_pct !== null && row.attendance_rate_pct < 75)
  ) ?? []
  const paidOrders = commerce?.paid_order_count ?? 0
  const totalOrders = commerce?.order_count ?? 0
  const unpaidOrders = Math.max(0, totalOrders - paidOrders)
  const publishedFormations = formations?.filter((formation) => formation.status === 'published').length ?? 0
  const draftFormations = formations?.filter((formation) => formation.status === 'draft').length ?? 0
  const archivedFormations = formations?.filter((formation) => formation.status === 'archived').length ?? 0
  const globalAlerts = (pedagogy?.at_risk_students ?? 0) + (commerce?.late_installments ?? 0) + sessionsToWatch.length

  return <main className="app-page school-statistics-page">
    <header className="app-page-header">
      <div>
        <span className="page-kicker">Pilotage de l’école</span>
        <h1>Statistiques</h1>
        <p>Supervisez le catalogue, les sessions, l’activité commerciale et les signaux qui nécessitent votre attention.</p>
      </div>
    </header>

    {loading && <div className="page-state">Chargement des statistiques…</div>}
    {pedagogyError && <div className="form-error">{pedagogyError}</div>}
    {commerceError && <div className="form-error">{commerceError}</div>}
    {formationsError && <div className="form-error">{formationsError}</div>}

    {(pedagogy || commerce || formations) && <>
      <section className="statistics-kpi-grid">
        <article className="statistics-kpi-card">
          <span><GraduationCap size={16}/> Catalogue</span>
          <strong>{formations ? `${publishedFormations}/${formations.length}` : '—'}</strong>
          <small>{formations ? `${draftFormations} formation(s) à finaliser` : 'Donnée catalogue indisponible'}</small>
        </article>
        <article className="statistics-kpi-card">
          <span><CalendarDays size={16}/> Sessions à surveiller</span>
          <strong>{pedagogy ? sessionsToWatch.length : '—'}</strong>
          <small>{pedagogy ? `${pedagogy.active_sessions} session(s) active(s)` : 'Donnée de session indisponible'}</small>
        </article>
        <article className="statistics-kpi-card">
          <span><Banknote size={16}/> Situation commerciale</span>
          <strong>{commerce ? moneyByCurrency('collected_cents') : '—'}</strong>
          <small>{commerce ? `${commerce.paid_order_count}/${commerce.order_count} commande(s) réglée(s)` : 'Donnée commerciale indisponible'}</small>
        </article>
        <article className="statistics-kpi-card">
          <span><AlertTriangle size={16}/> Alertes école</span>
          <strong>{pedagogy || commerce ? globalAlerts : '—'}</strong>
          <small>{commerce ? `${commerce.late_installments} échéance(s) en retard` : 'Vue consolidée des points à surveiller'}</small>
        </article>
      </section>

      <section className="statistics-layout">
        <div className="statistics-stack">
          <article className="statistics-chart-card">
            <div className="statistics-chart-heading">
              <div>
                <span className="section-label">Supervision des sessions</span>
                <h2>Remplissage et présence</h2>
                <p>Une vue de pilotage pour repérer rapidement les sessions qui décrochent ou se remplissent mal.</p>
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
            /> : <div className="statistics-empty">Les indicateurs apparaîtront dès qu’une session disposera de données.</div>}
          </article>

          <article className="statistics-chart-card">
            <div className="statistics-chart-heading">
              <div>
                <span className="section-label">Points d’attention</span>
                <h2>Signaux par session</h2>
                <p>Ces données servent à superviser l’exécution pédagogique ; les actions restent dans l’espace enseignant et le suivi pédagogique.</p>
              </div>
              <AlertTriangle size={20}/>
            </div>
            {sessionsToWatch.length > 0 ? <ChartCanvas
              type="bar"
              horizontal
              showLegend
              height={Math.max(280, Math.min(8, sessionsToWatch.length) * 52)}
              labels={sessionsToWatch.slice(0, 8).map((row) => row.session_label || row.formation_title)}
              datasets={[
                { label: 'Étudiants à risque', data: sessionsToWatch.slice(0, 8).map((row) => row.at_risk_count) },
                { label: 'Corrections en attente', data: sessionsToWatch.slice(0, 8).map((row) => row.pending_reviews_count) },
              ]}
            /> : <div className="statistics-empty">Aucun signal particulier sur les sessions actuellement.</div>}
          </article>

          <article className="statistics-chart-card">
            <div className="statistics-chart-heading">
              <div>
                <span className="section-label">Qualité globale</span>
                <h2>Avancement de l’école</h2>
                <p>La progression et la présence sont affichées ici comme indicateurs globaux de qualité, pas comme tâches administratives.</p>
              </div>
              <TrendingUp size={20}/>
            </div>
            {pedagogy ? <ChartCanvas
              type="bar"
              max={100}
              valueSuffix="%"
              height={260}
              labels={['Progression moyenne', 'Présence moyenne']}
              datasets={[{
                label: 'École',
                data: [pedagogy.average_progress_pct, pedagogy.average_attendance_pct ?? 0],
              }]}
            /> : <div className="statistics-empty">Données pédagogiques indisponibles.</div>}
          </article>
        </div>

        <aside className="statistics-stack">
          <article className="statistics-chart-card">
            <div className="statistics-chart-heading">
              <div><span className="section-label">Catalogue</span><h3>État des formations</h3><p>Répartition entre formations publiées, en préparation et archivées.</p></div>
              <GraduationCap size={19}/>
            </div>
            {formations && formations.length > 0 ? <ChartCanvas
              type="doughnut"
              showLegend
              height={250}
              labels={['Publiées', 'À finaliser', 'Archivées']}
              datasets={[{ label: 'Formations', data: [publishedFormations, draftFormations, archivedFormations] }]}
            /> : <div className="statistics-empty">Le catalogue apparaîtra ici dès la création des premières formations.</div>}
          </article>

          <article className="statistics-chart-card">
            <div className="statistics-chart-heading">
              <div><span className="section-label">Commerce</span><h3>Commandes réglées</h3><p>Répartition globale des commandes encaissées et restantes.</p></div>
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
              <div><span className="section-label">Activité</span><h3>École en activité</h3><p>Volume d’étudiants et de sessions actuellement actifs.</p></div>
              <Users size={19}/>
            </div>
            {pedagogy || commerce ? <ChartCanvas
              type="bar"
              height={230}
              labels={['Étudiants actifs', 'Sessions actives']}
              datasets={[{
                label: 'Volume',
                data: [pedagogy?.active_students ?? commerce?.active_students ?? 0, pedagogy?.active_sessions ?? 0],
              }]}
            /> : <div className="statistics-empty">Données d’activité indisponibles.</div>}
          </article>
        </aside>
      </section>
    </>}
  </main>
}
