import { useEffect, useMemo, useState } from 'react'
import { Check, Clock3, CreditCard, ShieldCheck } from 'lucide-react'
import { useTenant } from '../app/TenantContext'
import {
  ApiError,
  getCurrentSubscription,
  listPlans,
  type Plan,
  type Subscription,
} from '../lib/api'

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  }).format(new Date(value))
}

function formatPrice(cents: number | null, currency: string) {
  if (cents === null) return 'Tarif à définir'
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(cents / 100)
}

const statusLabels: Record<Subscription['status'], string> = {
  trialing: 'Période d’essai',
  active: 'Actif',
  past_due: 'Paiement en retard',
  suspended: 'Suspendu',
  cancelled: 'Résilié',
}

export function BillingPage() {
  const { activeOrganization } = useTenant()
  const [plans, setPlans] = useState<Plan[]>([])
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!activeOrganization) return

    setLoading(true)
    setError('')

    Promise.all([
      listPlans(),
      getCurrentSubscription().catch((err) => {
        if (err instanceof ApiError && err.status === 404) return null
        throw err
      }),
    ])
      .then(([planItems, subscriptionItem]) => {
        setPlans(planItems)
        setSubscription(subscriptionItem)
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : 'Impossible de charger l’abonnement.')
      })
      .finally(() => setLoading(false))
  }, [activeOrganization?.id])

  const remainingTrialDays = useMemo(() => {
    if (!subscription?.trial_ends_at || subscription.status !== 'trialing') return null
    const diff = new Date(subscription.trial_ends_at).getTime() - Date.now()
    return Math.max(0, Math.ceil(diff / 86_400_000))
  }, [subscription])

  if (!activeOrganization) {
    return <div className="page-state">Créez d’abord une école.</div>
  }

  return (
    <main className="app-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Abonnement</span>
          <h1>Forfait de {activeOrganization.name}</h1>
          <p>Votre abonnement détermine les fonctionnalités et quotas disponibles.</p>
        </div>
        {subscription && (
          <span className="status-chip">{statusLabels[subscription.status]}</span>
        )}
      </header>

      {error && <div className="form-error">{error}</div>}

      {subscription && (
        <section className="billing-summary">
          <article className="current-plan-card">
            <div className="current-plan-icon"><CreditCard size={22} /></div>
            <div>
              <span className="section-label">Forfait actuel</span>
              <h2>{subscription.plan.name}</h2>
              <p>{subscription.plan.description}</p>
            </div>
            <div className="current-plan-meta">
              <span>
                <strong>{statusLabels[subscription.status]}</strong>
                <small>Statut</small>
              </span>
              <span>
                <strong>
                  {subscription.billing_interval === 'annual' ? 'Annuel' : 'Mensuel'}
                </strong>
                <small>Facturation</small>
              </span>
              <span>
                <strong>{formatDate(subscription.trial_ends_at)}</strong>
                <small>Fin de l’essai</small>
              </span>
            </div>
          </article>

          {remainingTrialDays !== null && (
            <div className="trial-banner">
              <Clock3 size={18} />
              <div>
                <strong>{remainingTrialDays} jour{remainingTrialDays > 1 ? 's' : ''} d’essai restant{remainingTrialDays > 1 ? 's' : ''}</strong>
                <span>Aucun tarif n’est encore déclenché tant que la grille commerciale n’est pas configurée.</span>
              </div>
            </div>
          )}
        </section>
      )}

      <section className="billing-plans-section">
        <div className="table-heading">
          <div>
            <span className="section-label">Forfaits</span>
            <h2>Choisissez les capacités dont votre école a besoin</h2>
          </div>
          {loading && <span className="muted-note">Chargement…</span>}
        </div>

        <div className="billing-plan-grid">
          {plans.map((plan) => {
            const current = subscription?.plan.code === plan.code
            return (
              <article className={current ? 'billing-plan-card current' : 'billing-plan-card'} key={plan.id}>
                {current && <span className="current-badge">Forfait actuel</span>}
                <span className="plan-code">{plan.name}</span>
                <h3>{formatPrice(plan.monthly_price_cents, plan.currency)}</h3>
                <p>{plan.description}</p>

                <div className="billing-plan-features">
                  {plan.entitlements.length === 0 ? (
                    <span className="pending-config">
                      <ShieldCheck size={16} />
                      Fonctionnalités et quotas à configurer
                    </span>
                  ) : (
                    plan.entitlements
                      .filter((item) => item.enabled)
                      .map((item) => (
                        <span key={item.feature_key}>
                          <Check size={15} />
                          {item.feature_key}
                          {item.limit_value !== null ? ` · ${item.limit_value}` : ''}
                        </span>
                      ))
                  )}
                </div>

                <button
                  className={current ? 'secondary-button full' : 'primary-button full'}
                  disabled
                >
                  {current ? 'Forfait actuel' : 'Sélection bientôt disponible'}
                </button>
              </article>
            )
          })}
        </div>
      </section>
    </main>
  )
}
