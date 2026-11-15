import { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  AlertTriangle,
  Ban,
  Check,
  Clock3,
  CreditCard,
  ExternalLink,
  FileText,
  FlaskConical,
  LockKeyhole,
  Plus,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  X,
  XCircle,
} from 'lucide-react'
import { commissionLabel, formatMoney, monthlyEquivalent, planHighlights } from '../lib/planFeatures'
import { PlanComparison } from '../components/PlanComparison'
import { clearPlanChoice, planChoiceFromSearch } from '../lib/planChoice'
import { Link, useSearchParams } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import { toast } from '../ui/toast'
import {
  ApiError,
  getBillingUsage,
  listAddons,
  type Addon,
  type BillingUsage,
  cancelSubscriptionAtPeriodEnd,
  confirmDemoPayment,
  createDemoCheckout,
  createTaraCheckout,
  getCurrentSubscription,
  getPaymentMode,
  listBillingInvoices,
  listPlans,
  reconcileTaraPayment,
  resumeSubscription,
  type BillingInvoice,
  type DemoPaymentAttempt,
  type PaymentMode,
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

function formatPrice(amount: number | null, currency: string) {
  if (amount === null) return 'Tarif à définir'

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
    maximumFractionDigits: 2,
  }).format(amount / 100)
}

const statusLabels: Record<Subscription['status'], string> = {
  trialing: 'Période d’essai',
  active: 'Actif',
  past_due: 'Paiement en retard',
  suspended: 'Suspendu',
  cancelled: 'Résilié',
}

const invoiceStatusLabels: Record<BillingInvoice['status'], string> = {
  open: 'À payer',
  paid: 'Payée',
  void: 'Annulée',
}

export function BillingPage() {
  const { activeOrganization } = useTenant()
  const [searchParams, setSearchParams] = useSearchParams()
  const [plans, setPlans] = useState<Plan[]>([])
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [invoices, setInvoices] = useState<BillingInvoice[]>([])
  const [usage, setUsage] = useState<BillingUsage | null>(null)
  const [addons, setAddons] = useState<Addon[]>([])
  const [paymentMode, setPaymentMode] = useState<PaymentMode | null>(null)
  const [demoAttempt, setDemoAttempt] = useState<DemoPaymentAttempt | null>(null)
  const [billingInterval, setBillingInterval] = useState<'monthly' | 'annual'>('monthly')
  const [loading, setLoading] = useState(false)
  const [paymentLoading, setPaymentLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function loadBilling() {
    if (!activeOrganization) return
    setLoading(true)
    setError('')

    try {
      const [planItems, subscriptionItem, mode, invoiceItems, usageItem, addonItems] = await Promise.all([
        listPlans(),
        getCurrentSubscription().catch((err) => {
          if (err instanceof ApiError && err.status === 404) return null
          throw err
        }),
        getPaymentMode(),
        listBillingInvoices(),
        getBillingUsage().catch(() => null),
        listAddons().catch(() => []),
      ])
      setPlans(planItems)
      setSubscription(subscriptionItem)
      setPaymentMode(mode)
      setInvoices(invoiceItems)
      setUsage(usageItem)
      setAddons(addonItems)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de charger l’abonnement.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setDemoAttempt(null)
    setMessage('')
    void loadBilling()
  }, [activeOrganization?.id])

  useEffect(() => {
    const taraOrder = searchParams.get('tara_order')
    if (!taraOrder || !activeOrganization) return

    let cancelled = false
    setPaymentLoading(true)
    setError('')

    reconcileTaraPayment(taraOrder)
      .then(async (result) => {
        if (cancelled) return

        if (result.status === 'paid' && result.subscription) {
          setSubscription(result.subscription)
          setMessage(
            `Paiement TaraMoney vérifié. Le forfait ${result.subscription.plan.name} est maintenant actif.`,
          )
          await loadBilling()
        } else if (result.status === 'pending') {
          setMessage(
            'Le paiement a bien été retrouvé mais TaraMoney ne le confirme pas encore. Vous pouvez actualiser dans quelques instants.',
          )
        } else {
          setError('TaraMoney indique que ce paiement a échoué ou expiré.')
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? err.message
              : 'Impossible de vérifier le paiement TaraMoney.',
          )
        }
      })
      .finally(() => {
        if (!cancelled) {
          setPaymentLoading(false)
          const next = new URLSearchParams(searchParams)
          next.delete('tara_order')
          setSearchParams(next, { replace: true })
        }
      })

    return () => {
      cancelled = true
    }
  }, [activeOrganization?.id, searchParams, setSearchParams])

  // The plan clicked on the landing page: from the address, else the one kept on the trial.
  const requestedChoice = useMemo(() => planChoiceFromSearch(`?${searchParams.toString()}`), [searchParams])
  useEffect(() => {
    clearPlanChoice()
    if (requestedChoice) setBillingInterval(requestedChoice.interval)
  }, [requestedChoice])
  useEffect(() => {
    if (!requestedChoice && subscription?.status === 'trialing' && subscription.chosen_billing_interval) {
      setBillingInterval(subscription.chosen_billing_interval)
    }
  }, [requestedChoice, subscription?.id, subscription?.status, subscription?.chosen_billing_interval])
  const chosenCode = requestedChoice?.plan ?? (subscription?.status === 'trialing' ? subscription.chosen_plan_code ?? null : null)
  const chosenPlan = plans.find((plan) => plan.code === chosenCode) ?? null
  useEffect(() => {
    if (!chosenPlan) return
    const frame = window.requestAnimationFrame(() => {
      document.getElementById(`plan-${chosenPlan.code}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [chosenPlan?.code])

  const remainingTrialDays = useMemo(() => {
    if (!subscription?.trial_ends_at || subscription.status !== 'trialing') return null
    const diff = new Date(subscription.trial_ends_at).getTime() - Date.now()
    return Math.max(0, Math.ceil(diff / 86_400_000))
  }, [subscription])

  async function startDemoPayment(plan: Plan) {
    setPaymentLoading(true)
    setError('')
    setMessage('')
    try {
      const attempt = await createDemoCheckout(plan.code, billingInterval)
      setDemoAttempt(attempt)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de créer le paiement de test.')
    } finally {
      setPaymentLoading(false)
    }
  }

  async function confirmDemo() {
    if (!demoAttempt) return
    setPaymentLoading(true)
    setError('')
    try {
      const confirmed = await confirmDemoPayment(demoAttempt.id)
      setDemoAttempt(confirmed.payment)
      setSubscription(confirmed.subscription)
      setMessage(
        `Paiement démo confirmé. Le forfait ${confirmed.subscription.plan.name} est maintenant actif.`,
      )
      await loadBilling()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Confirmation du paiement impossible.')
    } finally {
      setPaymentLoading(false)
    }
  }

  async function startTaraPayment(plan: Plan) {
    setPaymentLoading(true)
    setError('')
    setMessage('')
    try {
      const checkout = await createTaraCheckout(plan.code, billingInterval)
      window.location.assign(checkout.checkout_url)
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Impossible de démarrer le paiement TaraMoney.',
      )
      setPaymentLoading(false)
    }
  }

  async function toggleCancellation() {
    if (!subscription) return
    setActionLoading(true)
    setError('')
    setMessage('')
    try {
      const updated = subscription.cancel_at_period_end
        ? await resumeSubscription()
        : await cancelSubscriptionAtPeriodEnd()
      setSubscription(updated)
      setMessage(
        updated.status === 'cancelled'
          ? 'L’abonnement est maintenant résilié.'
          : updated.cancel_at_period_end
            ? 'La résiliation est programmée à la fin de la période en cours.'
            : 'La résiliation programmée a été annulée.',
      )
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Impossible de modifier la résiliation.',
      )
    } finally {
      setActionLoading(false)
    }
  }

  if (!activeOrganization) {
    return <div className="page-state">Créez d’abord une école.</div>
  }

  const taraAvailable =
    paymentMode?.mode === 'production' && paymentMode.tara_configured

  // The free plan: where a school goes on when no paid plan runs (docs/FORFAITS.md).
  const freePlan = plans.find((plan) => plan.monthly_price_cents === 0) ?? null
  const running = subscription !== null && ['trialing', 'active', 'past_due'].includes(subscription.status)
  const onFreePlan = Boolean(freePlan && usage?.plan_code === freePlan.code && !running)
  const showSubscription = subscription !== null && !onFreePlan
  const effectivePlanCode = usage?.plan_code ?? subscription?.plan.code ?? null
  const effectivePlan = plans.find((plan) => plan.code === effectivePlanCode) ?? null
  const currentPaidPlan = running && effectivePlan && (effectivePlan.monthly_price_cents ?? 0) > 0
    ? effectivePlan
    : null
  const planAddons = currentPaidPlan
    ? addons.filter((addon) => addon.plan_codes.includes(currentPaidPlan.code))
    : []
  const visibleAddons = addons.filter((addon) => addon.status !== 'inactive')
  const annualDiscount = (() => {
    const paid = plans.find((plan) => (plan.monthly_price_cents ?? 0) > 0 && plan.annual_price_cents !== null)
    if (!paid || !paid.monthly_price_cents || paid.annual_price_cents === null) return 0
    return Math.round(100 - (paid.annual_price_cents * 100) / (paid.monthly_price_cents * 12))
  })()

  return (
    <main className="app-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Abonnement</span>
          <h1>Forfait de {activeOrganization.name}</h1>
          <p>Votre abonnement détermine les fonctionnalités et quotas disponibles.</p>
        </div>
        {onFreePlan && freePlan ? (
          <span className="status-chip billing-status active">{freePlan.name} · gratuit</span>
        ) : subscription && (
          <span className={`status-chip billing-status ${subscription.status}`}>
            {statusLabels[subscription.status]}
          </span>
        )}
      </header>

      {subscription?.status === 'past_due' && (
        <div className="billing-alert warning">
          <AlertTriangle size={19} />
          <div>
            <strong>Paiement en attente</strong>
            <span>
              La période payée est terminée. Régularisez avant le {formatDate(subscription.grace_period_ends_at)}
              {freePlan
                ? `, sinon votre école passera en ${freePlan.name} : gratuite, avec des cours en live limités.`
                : ' pour éviter la suspension de l’école.'}
            </span>
          </div>
        </div>
      )}

      {onFreePlan && freePlan && (
        <div className="billing-alert neutral">
          <Sparkles size={19} />
          <div>
            <strong>Votre école est en {freePlan.name}</strong>
            <span>
              {subscription
                ? `Votre ${subscription.status === 'cancelled' ? 'forfait' : 'essai ou forfait payé'} est terminé : l’école continue gratuitement. `
                : 'Votre école utilise le forfait gratuit. '}
              Choisissez un forfait ci-dessous pour retrouver les cours en live et des quotas plus larges.
            </span>
          </div>
        </div>
      )}

      {subscription?.status === 'suspended' && !onFreePlan && (
        <div className="billing-alert danger">
          <Ban size={19} />
          <div>
            <strong>Abonnement suspendu</strong>
            <span>
              Les fonctionnalités soumises au forfait sont bloquées. Un paiement confirmé réactivera l’abonnement.
            </span>
          </div>
        </div>
      )}

      {subscription?.cancel_at_period_end && subscription.status !== 'cancelled' && (
        <div className="billing-alert neutral">
          <XCircle size={19} />
          <div>
            <strong>Résiliation programmée</strong>
            <span>
              L’accès reste actif jusqu’au {formatDate(subscription.current_period_end ?? subscription.trial_ends_at)}.
            </span>
          </div>
          <button className="secondary-button" onClick={() => void toggleCancellation()} disabled={actionLoading}>
            <RotateCcw size={16} />
            Annuler la résiliation
          </button>
        </div>
      )}

      {paymentMode?.demo_enabled && (
        <div className="demo-payment-banner">
          <FlaskConical size={20} />
          <div>
            <strong>Mode paiement démo actif</strong>
            <span>
              Aucun paiement réel ne sera envoyé à Tara. Vous pouvez tester tout le parcours d’abonnement.
            </span>
          </div>
          <div className="billing-interval-switch">
            <button
              className={billingInterval === 'monthly' ? 'active' : ''}
              onClick={() => setBillingInterval('monthly')}
            >
              Mensuel
            </button>
            <button
              className={billingInterval === 'annual' ? 'active' : ''}
              onClick={() => setBillingInterval('annual')}
            >
              Annuel{annualDiscount > 0 ? ` −${annualDiscount} %` : ''}
            </button>
          </div>
        </div>
      )}

      {!paymentMode?.demo_enabled && (
        <div className="payment-provider-banner">
          <ShieldCheck size={19} />
          <div>
            <strong>
              {taraAvailable ? 'Paiements sécurisés par TaraMoney' : 'TaraMoney à configurer'}
            </strong>
            <span>
              {taraAvailable
                ? 'L’abonnement ne sera activé qu’après vérification serveur du paiement.'
                : 'Renseignez les variables TaraMoney du backend avant d’accepter de vrais paiements.'}
            </span>
          </div>
          <div className="billing-interval-switch">
            <button
              className={billingInterval === 'monthly' ? 'active' : ''}
              onClick={() => setBillingInterval('monthly')}
            >
              Mensuel
            </button>
            <button
              className={billingInterval === 'annual' ? 'active' : ''}
              onClick={() => setBillingInterval('annual')}
            >
              Annuel{annualDiscount > 0 ? ` −${annualDiscount} %` : ''}
            </button>
          </div>
        </div>
      )}

      {demoAttempt && demoAttempt.status === 'pending' && (
        <section className="demo-payment-card">
          <div>
            <span className="section-label">Paiement de test</span>
            <h2>{demoAttempt.plan.name}</h2>
            <p>
              Référence {demoAttempt.provider_reference} · montant simulé{' '}
              <strong>{formatPrice(demoAttempt.amount_cents, demoAttempt.currency)}</strong>
            </p>
          </div>
          <div className="demo-payment-actions">
            <button
              className="secondary-button"
              onClick={() => setDemoAttempt(null)}
              disabled={paymentLoading}
            >
              Annuler
            </button>
            <button
              className="primary-button"
              onClick={() => void confirmDemo()}
              disabled={paymentLoading}
            >
              <ShieldCheck size={17} />
              {paymentLoading ? 'Confirmation…' : 'Confirmer ce paiement de test'}
            </button>
          </div>
        </section>
      )}

      {message && <div className="form-success">{message}</div>}
      {error && <div className="form-error">{error}</div>}

      {showSubscription && subscription && (
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
                <strong>
                  {formatDate(
                    subscription.status === 'trialing'
                      ? subscription.trial_ends_at
                      : subscription.current_period_end,
                  )}
                </strong>
                <small>
                  {subscription.status === 'trialing' ? 'Fin de l’essai' : 'Échéance'}
                </small>
              </span>
            </div>
          </article>

          {remainingTrialDays !== null && (
            <div className="trial-banner">
              <Clock3 size={18} />
              <div>
                <strong>{remainingTrialDays} jour{remainingTrialDays > 1 ? 's' : ''} d’essai restant{remainingTrialDays > 1 ? 's' : ''}</strong>
                <span>
                  Votre essai inclut tout le forfait {subscription.plan.name}. Choisissez votre forfait avant la fin de l’essai pour continuer sans interruption
                  {freePlan ? `, sinon votre école passera en ${freePlan.name}, gratuite, avec des cours en live limités.` : '.'}
                </span>
              </div>
            </div>
          )}

          {subscription.status !== 'cancelled' && !subscription.cancel_at_period_end && (
            <div className="subscription-actions">
              <button
                className="text-danger-button"
                onClick={() => void toggleCancellation()}
                disabled={actionLoading}
              >
                {actionLoading
                  ? 'Mise à jour…'
                  : subscription.status === 'past_due'
                    ? 'Résilier maintenant'
                    : 'Résilier à la fin de la période'}
              </button>
            </div>
          )}
        </section>
      )}

      {usage && usage.plan_code && (
        <section className="app-card billing-usage">
          <div className="table-heading">
            <div>
              <span className="section-label">Votre utilisation</span>
              <h2>Forfait {usage.plan_name}</h2>
            </div>
            <span className="muted-note">Commission plateforme : {commissionLabel(usage.commission_bps)}</span>
          </div>
          <div className="billing-usage__grid">
            {usage.metrics.map((metric) => {
              const share = metric.limit ? Math.min(100, Math.round((metric.current / metric.limit) * 100)) : 0
              return (
                <div className={`billing-usage__metric${metric.extra > 0 ? ' is-over' : ''}`} key={metric.feature_key}>
                  <span>{metric.label}</span>
                  <strong>
                    {metric.current}
                    <small>{metric.limit === null ? ' · illimité' : ` / ${metric.limit}`}</small>
                  </strong>
                  {metric.limit !== null && <i className="billing-usage__bar"><b style={{ width: `${share}%` }} /></i>}
                  {metric.extra > 0 && (
                    <em>
                      {metric.unit_price_cents !== null
                        ? `${metric.extra} en plus · ${formatMoney(metric.extra_amount_cents, 'XAF')} par mois`
                        : `${metric.extra} au-delà du forfait`}
                    </em>
                  )}
                </div>
              )
            })}
          </div>
          {usage.next_payment && (
            <div className="billing-usage__next">
              <strong>Votre prochain paiement</strong>
              {usage.next_payment.lines.map((line) => (
                <div key={line.label}>
                  <span>{line.quantity > 1 ? `${line.label} × ${line.quantity}` : line.label}</span>
                  <span>{formatMoney(line.amount_cents, usage.next_payment!.currency)}</span>
                </div>
              ))}
              <div className="billing-usage__total">
                <span>Total</span>
                <span>{formatMoney(usage.next_payment.total_cents, usage.next_payment.currency)}</span>
              </div>
            </div>
          )}
        </section>
      )}

      <section className="billing-plans-section" id="billing-plans">
        {chosenPlan && (chosenPlan.monthly_price_cents ?? 0) > 0 && effectivePlanCode !== chosenPlan.code && (
          <div className="billing-alert neutral billing-choice">
            <CreditCard size={19} />
            <div>
              <strong>Vous avez choisi {chosenPlan.name}{billingInterval === 'annual' ? ' en annuel' : ''}</strong>
              <span>
                Payez-le maintenant pour l’activer
                {subscription?.status === 'trialing' && subscription.trial_ends_at
                  ? `, ou profitez d’abord de votre essai ${subscription.plan.name} jusqu’au ${formatDate(subscription.trial_ends_at)} : vous serez prévenu avant la fin.`
                  : '.'}
              </span>
            </div>
          </div>
        )}
        <div className="table-heading">
          <div>
            <span className="section-label">Forfaits</span>
            <h2>Choisissez les capacités dont votre école a besoin</h2>
          </div>
          {loading && <span className="muted-note">Chargement…</span>}
        </div>

        <div className="billing-plan-grid">
          {plans.map((plan) => {
            const current = effectivePlanCode === plan.code
            const free = plan.monthly_price_cents === 0
            const displayedPrice =
              billingInterval === 'annual'
                ? plan.annual_price_cents
                : plan.monthly_price_cents
            const perMonth = monthlyEquivalent(plan, billingInterval === 'annual')

            return (
              <article
                className={`billing-plan-card${current ? ' current' : ''}${chosenPlan?.code === plan.code && !current ? ' chosen' : ''}`}
                id={`plan-${plan.code}`}
                key={plan.id}
              >
                {current && <span className="current-badge">Forfait actuel</span>}
                {!current && chosenPlan?.code === plan.code && <span className="current-badge chosen-badge">Votre choix</span>}
                <span className="plan-code">{plan.name}</span>
                <h3>{free ? 'Gratuit' : formatPrice(displayedPrice, plan.currency)}</h3>
                <span className="billing-plan-period">
                  {free
                    ? 'Sans abonnement'
                    : displayedPrice === null
                      ? ''
                      : billingInterval === 'annual'
                        ? `par an, soit ${formatPrice(perMonth, plan.currency)} par mois`
                        : 'par mois'}
                </span>
                <p>{plan.description}</p>

                <div className="billing-plan-features">
                  {plan.entitlements.length === 0 ? (
                    <span className="pending-config">
                      <ShieldCheck size={16} />
                      Fonctionnalités et quotas à configurer
                    </span>
                  ) : (
                    planHighlights(plan.entitlements).map((line) => (
                      <span className={line.excluded ? 'is-excluded' : undefined} key={line.key}>
                        {line.excluded ? <X size={15} /> : <Check size={15} />}
                        <span className="billing-plan-feature-text">
                          {line.label}
                          {line.soon && <em className="billing-plan-soon">Bientôt</em>}
                        </span>
                      </span>
                    ))
                  )}
                  {commissionLabel(plan.sales_commission_bps) && (
                    <span className="billing-plan-commission">
                      <CreditCard size={15} />
                      {commissionLabel(plan.sales_commission_bps)}, frais compris
                    </span>
                  )}
                </div>

                {free ? (
                  <>
                    <button className="secondary-button full" disabled>
                      {current ? 'Forfait actuel' : 'Sans abonnement'}
                    </button>
                    {!current && <small className="billing-plan-note">Votre école y passe d’elle-même quand aucun forfait payé n’est en cours.</small>}
                  </>
                ) : paymentMode?.demo_enabled ? (
                  <button
                    className={current ? 'secondary-button full' : 'primary-button full'}
                    disabled={paymentLoading}
                    onClick={() => void startDemoPayment(plan)}
                  >
                    <FlaskConical size={16} />
                    {current ? 'Tester un renouvellement' : 'Tester ce forfait'}
                  </button>
                ) : taraAvailable ? (
                  <button
                    className={current ? 'secondary-button full' : 'primary-button full'}
                    disabled={paymentLoading || displayedPrice === null}
                    onClick={() => void startTaraPayment(plan)}
                  >
                    <ExternalLink size={16} />
                    {current ? 'Renouveler avec Tara' : 'Payer avec Tara'}
                  </button>
                ) : (
                  <button
                    className={current ? 'secondary-button full' : 'primary-button full'}
                    disabled
                  >
                    {current ? 'Forfait actuel' : 'Paiement indisponible'}
                  </button>
                )}
              </article>
            )
          })}
        </div>
        <PlanComparison plans={plans} highlight={effectivePlanCode} />
      </section>

      {addons.length > 0 && (
        <section className="app-card billing-addons">
          <div className="table-heading">
            <div>
              <span className="section-label">Options à l’unité</span>
              <h2>Au-delà de votre forfait</h2>
            </div>
            <span className="muted-note">
              {currentPaidPlan
                ? 'Ajoutées à votre prochaine facture, seulement si vous les utilisez.'
                : 'Options débloquées avec un forfait payant.'}
            </span>
          </div>
          <div className="billing-addons__grid">
            {visibleAddons.map((addon) => {
              const destination = addon.feature_key === 'teachers'
                ? { to: '/app/manage/teachers', label: 'Ajouter un professeur' }
                : addon.feature_key === 'active_formations'
                  ? { to: '/app/manage/formations', label: 'Ajouter une formation' }
                  : null
              const includedWithoutQuota = Boolean(currentPaidPlan && addon.feature_key && currentPaidPlan.entitlements.some(
                (entitlement) => entitlement.feature_key === addon.feature_key && entitlement.enabled && entitlement.limit_value === null,
              ))
              const locked = addon.status === 'active' && !includedWithoutQuota && !planAddons.some((eligible) => eligible.code === addon.code)
              const available = !locked && !includedWithoutQuota && addon.status === 'active' && addon.unit_price_cents !== null && destination !== null
              const eligiblePlanNames = plans
                .filter((plan) => addon.plan_codes.includes(plan.code))
                .map((plan) => plan.name)
              const availabilityLabel = eligiblePlanNames.length > 0
                ? `Disponible avec ${eligiblePlanNames.join(', ')}`
                : 'Réservée aux forfaits payants'

              function showUpgradeOptions() {
                toast.info('Passez à un forfait adapté pour débloquer cette option.')
                document.getElementById('billing-plans')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
              }

              return (
                <article className={`billing-addon${addon.status === 'coming_soon' ? ' is-soon' : ''}${locked ? ' is-locked' : ''}`} key={addon.code}>
                  <div className="billing-addon__copy">
                    <strong>
                      {locked && <LockKeyhole size={15} aria-hidden="true" />}
                      {addon.name}
                    </strong>
                    <p>{addon.description}</p>
                  </div>
                  <div className="billing-addon__pricing">
                    <span>
                      {includedWithoutQuota
                        ? 'Déjà inclus sans limite'
                        : addon.unit_price_cents === null
                          ? 'Bientôt'
                          : addon.status === 'coming_soon'
                            ? `Bientôt · ${formatMoney(addon.unit_price_cents, addon.currency)} / ${addon.unit_label}`
                            : `${formatMoney(addon.unit_price_cents, addon.currency)} / ${addon.unit_label} / mois`}
                    </span>
                    {locked && <small>{availabilityLabel}</small>}
                  </div>
                  {locked ? (
                    <button className="secondary-button billing-addon__action" type="button" onClick={showUpgradeOptions}>
                      Voir les forfaits <ArrowRight size={15} />
                    </button>
                  ) : available && destination ? (
                    <Link className="primary-button billing-addon__action" to={destination.to}>
                      <Plus size={16} /> {destination.label}
                    </Link>
                  ) : includedWithoutQuota ? (
                    <button className="secondary-button billing-addon__action" type="button" disabled>
                      Inclus dans votre forfait
                    </button>
                  ) : (
                    <button className="secondary-button billing-addon__action" type="button" disabled>
                      Bientôt
                    </button>
                  )}
                </article>
              )
            })}
          </div>
        </section>
      )}

      <section className="app-card invoice-section">
        <div className="table-heading">
          <div>
            <span className="section-label">Facturation</span>
            <h2>Factures</h2>
          </div>
          <span className="muted-note">{invoices.length} facture{invoices.length > 1 ? 's' : ''}</span>
        </div>

        <div className="invoice-table">
          <div className="invoice-row invoice-header">
            <span>Facture</span>
            <span>Forfait</span>
            <span>Période</span>
            <span>Montant</span>
            <span>Statut</span>
          </div>

          {invoices.map((invoice) => (
            <div className="invoice-row" key={invoice.id}>
              <span className="invoice-number">
                <FileText size={15} />
                <strong>{invoice.invoice_number}</strong>
              </span>
              <span>
                {invoice.plan.name}
                {invoice.lines && invoice.lines.length > 1 && (
                  <small className="invoice-lines">
                    {invoice.lines.slice(1).map((line) => `${line.label} × ${line.quantity}`).join(' · ')}
                  </small>
                )}
              </span>
              <span>
                {formatDate(invoice.period_start)} → {formatDate(invoice.period_end)}
              </span>
              <span>{formatPrice(invoice.amount_cents, invoice.currency)}</span>
              <span className={`invoice-status ${invoice.status}`}>
                {invoiceStatusLabels[invoice.status]}
              </span>
            </div>
          ))}

          {!loading && invoices.length === 0 && (
            <div className="empty-row">Aucune facture pour le moment.</div>
          )}
        </div>
      </section>
    </main>
  )
}
