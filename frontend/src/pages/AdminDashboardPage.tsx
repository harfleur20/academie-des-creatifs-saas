import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  Building2,
  CreditCard,
  ShieldCheck,
  Users,
  WalletCards,
} from 'lucide-react'
import {
  ApiError,
  getAdminDashboard,
  type AdminDashboard,
} from '../lib/api'

function formatRevenue(amount: number, currency: string) {
  if (currency.toUpperCase() === 'XAF') {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'XAF',
      maximumFractionDigits: 0,
    }).format(amount)
  }
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency,
  }).format(amount / 100)
}

export function AdminDashboardPage() {
  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getAdminDashboard()
      .then(setDashboard)
      .catch((err) => {
        setError(
          err instanceof ApiError
            ? err.message
            : 'Impossible de charger le tableau de bord.',
        )
      })
  }, [])

  if (!dashboard && !error) {
    return <div className="admin-page-state">Chargement du SaaS…</div>
  }

  return (
    <main className="admin-page">
      <header className="admin-page-header">
        <div>
          <span className="page-kicker">Super-admin</span>
          <h1>Vue d’ensemble du SaaS</h1>
          <p>Suivez les écoles, abonnements et revenus depuis un seul espace.</p>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}

      {dashboard && (
        <>
          <section className="admin-metric-grid">
            <article>
              <span className="admin-metric-icon"><Building2 size={20} /></span>
              <small>Écoles</small>
              <strong>{dashboard.organizations_total}</strong>
              <p>{dashboard.organizations_active} actives</p>
            </article>
            <article>
              <span className="admin-metric-icon"><Users size={20} /></span>
              <small>Utilisateurs</small>
              <strong>{dashboard.users_total}</strong>
              <p>Comptes plateforme</p>
            </article>
            <article>
              <span className="admin-metric-icon"><CreditCard size={20} /></span>
              <small>Abonnements actifs</small>
              <strong>{dashboard.subscriptions_active}</strong>
              <p>{dashboard.subscriptions_trialing} en essai</p>
            </article>
            <article>
              <span className="admin-metric-icon warning"><AlertTriangle size={20} /></span>
              <small>À surveiller</small>
              <strong>
                {dashboard.subscriptions_past_due + dashboard.subscriptions_suspended}
              </strong>
              <p>
                {dashboard.subscriptions_past_due} en retard ·{' '}
                {dashboard.subscriptions_suspended} suspendus
              </p>
            </article>
          </section>

          <section className="admin-grid">
            <article className="admin-card">
              <div className="admin-card-heading">
                <div>
                  <span className="section-label">Abonnements</span>
                  <h2>État du parc</h2>
                </div>
                <ShieldCheck size={20} />
              </div>
              <div className="admin-status-list">
                <span><b>{dashboard.subscriptions_trialing}</b> Essais</span>
                <span><b>{dashboard.subscriptions_active}</b> Actifs</span>
                <span><b>{dashboard.subscriptions_past_due}</b> En retard</span>
                <span><b>{dashboard.subscriptions_suspended}</b> Suspendus</span>
              </div>
            </article>

            <article className="admin-card">
              <div className="admin-card-heading">
                <div>
                  <span className="section-label">Revenus encaissés</span>
                  <h2>Factures payées</h2>
                </div>
                <WalletCards size={20} />
              </div>
              <div className="admin-revenue-list">
                {dashboard.revenue.length === 0 ? (
                  <p className="muted-note">Aucun paiement confirmé pour le moment.</p>
                ) : (
                  dashboard.revenue.map((item) => (
                    <div key={item.currency}>
                      <span>{item.currency}</span>
                      <strong>{formatRevenue(item.amount, item.currency)}</strong>
                      <small>{item.paid_invoices} facture{item.paid_invoices > 1 ? 's' : ''}</small>
                    </div>
                  ))
                )}
              </div>
            </article>
          </section>
        </>
      )}
    </main>
  )
}
