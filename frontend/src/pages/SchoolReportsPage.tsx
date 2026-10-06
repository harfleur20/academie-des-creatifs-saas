import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  Banknote,
  BarChart3,
  BookOpen,
  CalendarDays,
  FileText,
  GraduationCap,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  ApiError,
  getCommercialDashboard,
  getSchoolPedagogyOverview,
  listFormations,
  type CommercialDashboard,
  type FormationSummary,
  type SchoolPedagogyOverview,
} from '../lib/api'
import { formatSchoolMoney } from '../public/publicHelpers'
import '../reports-connect.css'

const errorMessage = (error: unknown) => error instanceof ApiError ? error.message : 'Chargement impossible.'

export function SchoolReportsPage() {
  const [pedagogy, setPedagogy] = useState<SchoolPedagogyOverview | null>(null)
  const [commerce, setCommerce] = useState<CommercialDashboard | null>(null)
  const [formations, setFormations] = useState<FormationSummary[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void Promise.allSettled([getSchoolPedagogyOverview(), getCommercialDashboard(), listFormations()])
      .then(([pedagogyResult, commerceResult, formationsResult]) => {
        if (!active) return
        const messages: string[] = []
        if (pedagogyResult.status === 'fulfilled') setPedagogy(pedagogyResult.value)
        else messages.push(`Suivi pédagogique : ${errorMessage(pedagogyResult.reason)}`)
        if (commerceResult.status === 'fulfilled') setCommerce(commerceResult.value)
        else messages.push(`Commerce : ${errorMessage(commerceResult.reason)}`)
        if (formationsResult.status === 'fulfilled') setFormations(formationsResult.value)
        else messages.push(`Catalogue : ${errorMessage(formationsResult.reason)}`)
        setError(messages.join(' · '))
        setLoading(false)
      })
    return () => { active = false }
  }, [])

  const published = formations?.filter((formation) => formation.status === 'published').length ?? 0
  const drafts = formations?.filter((formation) => formation.status === 'draft').length ?? 0
  const sessionsToWatch = pedagogy?.sessions.filter((row) => row.at_risk_count > 0 || row.pending_reviews_count > 0) ?? []
  const alerts = sessionsToWatch.length + (commerce?.late_installments ?? 0) + (pedagogy?.at_risk_students ?? 0)
  const collected = commerce?.totals_by_currency.length
    ? commerce.totals_by_currency.map((row) => formatSchoolMoney(row.collected_cents, row.currency)).join(' · ')
    : '—'
  const outstanding = commerce?.totals_by_currency.length
    ? commerce.totals_by_currency.map((row) => formatSchoolMoney(row.outstanding_cents, row.currency)).join(' · ')
    : '—'

  return (
    <main className="app-page school-reports-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Direction & supervision</span>
          <h1>Rapports</h1>
          <p>Une synthèse claire pour savoir où en est votre école, ce qui fonctionne et les points qui demandent votre attention.</p>
        </div>
      </header>

      {loading && <div className="page-state">Préparation des rapports…</div>}
      {error && <div className="form-error">{error}</div>}

      {!loading && (
        <>
          <section className="reports-summary-grid">
            <article className="app-card reports-summary-card">
              <span><GraduationCap size={17} /> Catalogue</span>
              <strong>{formations ? `${published}/${formations.length}` : '—'}</strong>
              <small>{formations ? `${drafts} formation(s) à finaliser` : 'Donnée indisponible'}</small>
            </article>
            <article className="app-card reports-summary-card">
              <span><Banknote size={17} /> Encaissements</span>
              <strong>{collected}</strong>
              <small>{commerce ? `${commerce.paid_order_count}/${commerce.order_count} commande(s) réglée(s)` : 'Donnée indisponible'}</small>
            </article>
            <article className="app-card reports-summary-card">
              <span><CalendarDays size={17} /> Sessions à surveiller</span>
              <strong>{pedagogy ? sessionsToWatch.length : '—'}</strong>
              <small>{pedagogy ? `${pedagogy.active_sessions} session(s) active(s)` : 'Donnée indisponible'}</small>
            </article>
            <article className="app-card reports-summary-card">
              <span><AlertTriangle size={17} /> Alertes école</span>
              <strong>{pedagogy || commerce ? alerts : '—'}</strong>
              <small>{commerce ? `${commerce.late_installments} échéance(s) en retard` : 'Vue consolidée'}</small>
            </article>
          </section>

          <section className="reports-layout">
            <article className="app-card reports-executive-card">
              <div className="reports-heading">
                <div>
                  <span className="section-label">Résumé exécutif</span>
                  <h2>État actuel de l’école</h2>
                  <p>Les données ci-dessous sont issues des vues déjà utilisées pour le pilotage de l’école.</p>
                </div>
                <FileText size={22} />
              </div>

              <div className="reports-executive-list">
                <div>
                  <strong>Catalogue</strong>
                  <span>{formations ? `${published} formation(s) publiée(s), ${drafts} à finaliser.` : 'Catalogue indisponible.'}</span>
                </div>
                <div>
                  <strong>Commerce</strong>
                  <span>{commerce ? `${commerce.paid_order_count} commande(s) réglée(s). Reste à encaisser : ${outstanding}.` : 'Données commerciales indisponibles.'}</span>
                </div>
                <div>
                  <strong>Exécution</strong>
                  <span>{pedagogy ? `${pedagogy.active_sessions} session(s) active(s), ${sessionsToWatch.length} à surveiller.` : 'Données de sessions indisponibles.'}</span>
                </div>
                <div>
                  <strong>Attention direction</strong>
                  <span>{alerts > 0 ? `${alerts} signal(aux) nécessitent une vérification.` : 'Aucun signal majeur remonté actuellement.'}</span>
                </div>
              </div>
            </article>

            <aside className="reports-links-stack">
              <Link className="app-card reports-link-card" to="/app/manage/performance">
                <span className="reports-link-icon"><BarChart3 size={20} /></span>
                <div><strong>Statistiques détaillées</strong><small>Charts, tendances et indicateurs de supervision.</small></div>
                <ArrowRight size={17} />
              </Link>
              <Link className="app-card reports-link-card" to="/app/manage/commerce">
                <span className="reports-link-icon"><Banknote size={20} /></span>
                <div><strong>Rapport commercial</strong><small>Commandes, paiements, échéances et encaissements.</small></div>
                <ArrowRight size={17} />
              </Link>
              <Link className="app-card reports-link-card" to="/app/manage/formations">
                <span className="reports-link-icon"><BookOpen size={20} /></span>
                <div><strong>État du catalogue</strong><small>Formations publiées, brouillons et contenu à finaliser.</small></div>
                <ArrowRight size={17} />
              </Link>
              <Link className="app-card reports-link-card" to="/app/manage/pedagogy">
                <span className="reports-link-icon"><CalendarDays size={20} /></span>
                <div><strong>Supervision pédagogique</strong><small>Suivre les sessions sans se substituer aux enseignants.</small></div>
                <ArrowRight size={17} />
              </Link>
            </aside>
          </section>
        </>
      )}
    </main>
  )
}
