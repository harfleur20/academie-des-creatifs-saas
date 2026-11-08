import {
  CheckCircle2,
  CreditCard,
  Download,
  LockKeyhole,
  Tag,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useTenant } from '../app/TenantContext'
import {
  cancelPublicOrder,
  confirmPublicDemoCheckout,
  createPublicCheckout,
  downloadPublicInvoicePdf,
  getPublicOrder,
  listPublicOrderInvoices,
  listPublicOrders,
  payPublicInstallment,
  previewPublicPrice,
  reconcilePublicTaraCheckout,
  setStoredOrganizationId,
  type Checkout,
  type PricePreview,
  type SchoolInvoice,
  type OrderInstallment,
} from '../lib/api'
import { saveBlobFile } from '../lib/download'
import { clearSchoolCart, getSchoolCart } from '../public/schoolCart'
import { formatSchoolMoney } from '../public/publicHelpers'
import { usePublicSchool } from '../public/SchoolPublicLayout'

export function SchoolCheckoutPage() {
  const { schoolSlug = '' } = useParams()
  const { school } = usePublicSchool()
  const { user } = useAuth()
  const { refreshOrganizations } = useTenant()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const storedItem = getSchoolCart(schoolSlug)
  const item = storedItem?.organization_id === school.organization_id
    ? storedItem
    : null

  const [preview, setPreview] = useState<PricePreview | null>(null)
  const [coupon, setCoupon] = useState('')
  const couponRef = useRef('')
  const [paymentMode, setPaymentMode] = useState<'full' | 'installments'>('full')
  const [acceptDepositTerms, setAcceptDepositTerms] = useState(false)
  const [order, setOrder] = useState<Checkout | null>(null)
  const [orderInstallments, setOrderInstallments] = useState<OrderInstallment[]>([])
  const [invoices, setInvoices] = useState<SchoolInvoice[]>([])
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)
  const [success, setSuccess] = useState(false)
  const orderId = Number(params.get('order') || 0)
  const [loadingOrder, setLoadingOrder] = useState(Boolean(orderId))
  const [retry, setRetry] = useState(0)
  const redirectStartedRef = useRef(false)

  const accessReady = Boolean(
    order?.access_status === 'active'
    && (order.status === 'paid' || order.status === 'partially_paid'),
  )

  const openStudentSpace = useCallback(async () => {
    if (redirectStartedRef.current) return
    redirectStartedRef.current = true
    setStoredOrganizationId(school.organization_id)
    clearSchoolCart(schoolSlug)
    setError('')

    try {
      await Promise.race([
        refreshOrganizations(),
        new Promise<void>((resolve) => window.setTimeout(resolve, 2500)),
      ])
    } catch {
      // The full reload below performs a fresh tenant/access lookup anyway.
    }

    window.location.replace('/app/student')
  }, [refreshOrganizations, school.organization_id, schoolSlug])

  useEffect(() => {
    if (!user || !accessReady || loadingOrder || redirectStartedRef.current) return
    const timer = window.setTimeout(() => {
      void openStudentSpace()
    }, 450)
    return () => window.clearTimeout(timer)
  }, [user?.id, accessReady, loadingOrder, openStudentSpace])

  useEffect(() => {
    if (!user || !orderId) return

    getPublicOrder(schoolSlug, orderId)
      .then(async (value) => {
        setOrder(value)
        setOrderInstallments(value.installments)
        const paymentRef = params.get('payment_ref')
        if (params.get('demo') === '1' && value.status !== 'paid') {
          await confirmPublicDemoCheckout(schoolSlug, orderId, paymentRef)
          const refreshed = await getPublicOrder(schoolSlug, orderId)
          setOrder(refreshed)
          setOrderInstallments(refreshed.installments)
          setSuccess(
            refreshed.access_status === 'active'
            && (refreshed.status === 'paid' || refreshed.status === 'partially_paid'),
          )
        } else if (
          params.get('payment') === 'return' &&
          (paymentRef || value.provider_reference)
        ) {
          await reconcilePublicTaraCheckout(
            schoolSlug,
            paymentRef || value.provider_reference!,
          )
          const refreshed = await getPublicOrder(schoolSlug, orderId)
          setOrder(refreshed)
          setOrderInstallments(refreshed.installments)
          setSuccess(
            refreshed.access_status === 'active'
            && (refreshed.status === 'paid' || refreshed.status === 'partially_paid'),
          )
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Commande introuvable.'))
      .finally(() => setLoadingOrder(false))
  }, [user, schoolSlug, params, orderId])

  useEffect(() => {
    if (!user || !item || orderId) return
    let active = true
    listPublicOrders(schoolSlug)
      .then((orders) => {
        if (!active) return
        const pending = orders.find((row) => row.session_id === item.session_id && row.status === 'pending')
        if (pending) {
          setOrder(pending)
          setOrderInstallments(pending.installments)
          return
        }
        return previewPublicPrice(schoolSlug, item.session_id, null).then((value) => {
          if (active && !couponRef.current) setPreview(value)
        })
      })
      .catch((err) => { if (active) setError(err instanceof Error ? err.message : 'Prix indisponible.') })
    return () => { active = false }
  }, [user, schoolSlug, item?.session_id, orderId, retry])

  useEffect(() => {
    if (
      !user ||
      !order?.order_id ||
      !(success || order.status === 'paid' || order.status === 'partially_paid')
    ) {
      return
    }
    listPublicOrderInvoices(schoolSlug, order.order_id)
      .then(setInvoices)
      .catch(() => setInvoices([]))
  }, [user, schoolSlug, order?.order_id, order?.status, success])

  useEffect(() => {
    if (order && order.paid_cents > 0) clearSchoolCart(schoolSlug)
  }, [order?.order_id, order?.paid_cents, schoolSlug])

  async function applyCoupon() {
    if (!item || !user) return
    setError('')
    const requestedCode = coupon.trim().toUpperCase()
    try {
      const value = await previewPublicPrice(schoolSlug, item.session_id, requestedCode || null)
      if (couponRef.current.trim().toUpperCase() === requestedCode) setPreview(value)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Code promo invalide.')
    }
  }

  async function pay() {
    if (!item || !user || !preview || (preview.coupon_code || '').toUpperCase() !== coupon.trim().toUpperCase()) return
    setWorking(true)
    setError('')
    try {
      const created = await createPublicCheckout(
        schoolSlug,
        item.session_id,
        paymentMode,
        coupon.trim() || null,
        acceptDepositTerms,
      )
      setOrder(created)
      if (created.final_price_cents === 0) {
        setSuccess(true)
        clearSchoolCart(schoolSlug)
        return
      }
      if (created.checkout_url) {
        window.location.assign(created.checkout_url)
      } else {
        setError('Le lien de paiement est indisponible. Réessayez depuis vos paiements.')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Paiement impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function downloadInvoice(invoice: SchoolInvoice) {
    setError('')
    try {
      const blob = await downloadPublicInvoicePdf(schoolSlug, invoice.id)
      saveBlobFile(blob, invoice.invoice_number + '.pdf')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Téléchargement impossible.')
    }
  }

  async function resumePayment() {
    if (!order) return
    const installment = orderInstallments.find((row) => row.status !== 'paid')
    setWorking(true)
    setError('')
    try {
      const url = installment
        ? (await payPublicInstallment(schoolSlug, installment.id)).checkout_url
        : order.checkout_url
      if (!url) throw new Error('Le lien de paiement est indisponible.')
      window.location.assign(url)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Paiement impossible.')
      setWorking(false)
    }
  }

  async function cancelOrder() {
    if (!order) return
    setWorking(true)
    setError('')
    try {
      await cancelPublicOrder(schoolSlug, order.order_id)
      navigate('/school/' + schoolSlug + '/checkout', { replace: true })
      setOrder(null)
      setOrderInstallments([])
      setRetry((value) => value + 1)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Annulation impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function enterSpace() {
    redirectStartedRef.current = false
    await openStudentSpace()
  }

  if (success || accessReady) {
    return (
      <main className="school-section school-checkout-page">
        <section className="school-payment-success">
          <CheckCircle2 size={42} />
          <span className="school-kicker">Paiement confirmé</span>
          <h1>Votre inscription est ouverte</h1>
          <p>Votre accès étudiant est prêt. Ouverture automatique de votre espace…</p>
          {error && <div className="school-checkout-error">{error}</div>}
          {invoices.length > 0 && (
            <div className="school-receipt-list">
              <strong>Vos documents de paiement</strong>
              {invoices.map((invoice) => (
                <button
                  key={invoice.id}
                  type="button"
                  onClick={() => void downloadInvoice(invoice)}
                >
                  <Download size={14} />
                  {invoice.invoice_number}
                </button>
              ))}
            </div>
          )}
          <button type="button" onClick={() => void enterSpace()}>
            Accéder à mon espace étudiant
          </button>
        </section>
      </main>
    )
  }

  if (!user) {
    const returnPath = '/school/' + schoolSlug + '/checkout' + (params.toString() ? '?' + params.toString() : '')
    return (
      <main className="school-section school-checkout-page">
        <section className="school-login-required">
          <LockKeyhole size={28} />
          <h1>Connectez-vous pour finaliser votre inscription</h1>
          <p>Votre compte servira ensuite à accéder à votre espace étudiant.</p>
          <div>
            <Link
              to={
                '/login?school=' +
                encodeURIComponent(schoolSlug) +
                '&return=' +
                encodeURIComponent(returnPath)
              }
            >
              Se connecter
            </Link>
            <Link
              to={
                '/login?mode=register&school=' +
                encodeURIComponent(schoolSlug) +
                '&return=' +
                encodeURIComponent(returnPath)
              }
            >
              Créer mon compte
            </Link>
          </div>
        </section>
      </main>
    )
  }

  if (loadingOrder) return <main className="school-section"><div className="school-empty">Chargement de votre commande…</div></main>

  if (order && (orderId || order.status === 'pending')) {
    return <main className="school-section school-checkout-page"><section className="school-login-required">
      <CreditCard size={28} />
      <h1>{order.status === 'paid' ? 'Commande payée' : order.status === 'payment_review' ? 'Paiement en vérification' : order.status === 'cancelled' ? 'Réservation expirée' : 'Paiement de votre commande'}</h1>
      <p>{order.formation_title}{order.session_label === 'Accès en ligne' ? ' · Formation en ligne' : ` · ${order.session_label}`}</p>
      <strong>{formatSchoolMoney(order.final_price_cents, order.currency)}</strong>
      {error && <div className="school-checkout-error">{error}</div>}
      {order.status === 'payment_review' && <p>Votre paiement est arrivé après l'expiration de la réservation. L'école doit vérifier votre dossier avant de vous donner accès ou de procéder à un remboursement.</p>}
      {order.status === 'cancelled' && <p>{order.session_label === 'Accès en ligne' ? 'Cette commande a expiré. Vous pouvez en créer une nouvelle si la formation est encore disponible.' : 'Cette réservation ne retient plus de place. Vous pouvez créer une nouvelle commande si la session est encore disponible.'}</p>}
      {!['cancelled', 'payment_review', 'refunded'].includes(order.status) && orderInstallments.some((row) => row.status !== 'paid') && <button type="button" disabled={working} onClick={() => void resumePayment()}>{working ? 'Ouverture…' : 'Reprendre le paiement'}</button>}
      {order.status === 'pending' && <button type="button" disabled={working} onClick={() => void cancelOrder()}>Annuler cette commande</button>}
      {order.status === 'paid' && <button type="button" onClick={() => void enterSpace()}>Accéder à mon espace étudiant</button>}
    </section></main>
  }

  if (!item) {
    return <main className="school-section"><div className="school-empty">Votre panier est vide. <Link to={'/school/' + schoolSlug + '/formations'}>Voir les formations</Link></div></main>
  }

  const total = preview?.final_price_cents ?? item.price_cents
  const hasDeposit = preview?.deposit_cents != null
  const balanceDue = preview?.balance_due_date
    ? new Date(preview.balance_due_date + 'T00:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
    : ''

  return (
    <main className="school-section school-checkout-page">
      <header className="school-page-heading">
        <span className="school-kicker">Paiement sécurisé</span>
        <h1>Finalisez votre inscription</h1>
      </header>
      {error && <div className="school-checkout-error">{error}</div>}

      <div className="school-checkout-layout">
        <section className="school-checkout-main">
          <article className="school-checkout-order">
            <h2>{item.formation_title}</h2>
            <p>{item.format_type === 'ligne' || item.session_label === 'Accès en ligne' ? 'Formation en ligne' : `Session : ${item.session_label}`}</p>
            <div className="school-coupon-box">
              <Tag size={16} />
              <input
                value={coupon}
                onChange={(event) => { couponRef.current = event.target.value; setCoupon(event.target.value); setPreview(null); setPaymentMode('full') }}
                placeholder="Code promo"
              />
              <button type="button" onClick={() => void applyCoupon()}>
                Appliquer
              </button>
            </div>
            {preview?.total_discount_cents ? (
              <p className="school-discount-line">
                Réduction : -
                {formatSchoolMoney(
                  preview.total_discount_cents,
                  preview.currency,
                )}
              </p>
            ) : null}
          </article>

          {preview?.installments_allowed && (
            <article className="school-payment-choice">
              <h3>Mode de paiement</h3>
              <label>
                <input
                  type="radio"
                  checked={paymentMode === 'full'}
                  onChange={() => setPaymentMode('full')}
                />
                {hasDeposit ? `Acompte aujourd’hui, puis le solde avant le ${balanceDue}` : 'Paiement comptant'}
              </label>
              <label>
                <input
                  type="radio"
                  checked={paymentMode === 'installments'}
                  onChange={() => setPaymentMode('installments')}
                />
                {hasDeposit
                  ? `Acompte aujourd’hui, puis le solde en ${preview.installment_count - 1} paiements`
                  : `Paiement en ${preview.installment_count} tranches`}
              </label>
            </article>
          )}

          {hasDeposit && preview && (
            <article className="school-payment-choice school-deposit-terms">
              <h3>Réservation avec acompte</h3>
              <p>
                Vous réservez votre place avec un acompte de{' '}
                <strong>{formatSchoolMoney(preview.deposit_cents ?? 0, preview.currency)}</strong> ({preview.deposit_percent} %), réglé aujourd’hui.
                {paymentMode === 'full' && <> Le solde de <strong>{formatSchoolMoney(preview.balance_cents ?? 0, preview.currency)}</strong> est à régler avant le {balanceDue}, 10 jours avant le début de la session.</>}
                {' '}Si le solde n’est pas réglé à temps, votre accès est suspendu, mais votre place reste réservée.
              </p>
              <label>
                <input type="checkbox" checked={acceptDepositTerms} onChange={(event) => setAcceptDepositTerms(event.target.checked)} />
                J’accepte que l’acompte ne soit pas remboursable.
              </label>
            </article>
          )}
        </section>

        <aside className="school-checkout-summary">
          <span>Total de la formation</span>
          {preview && preview.total_discount_cents > 0 && (
            <del>{formatSchoolMoney(preview.base_price_cents, preview.currency)}</del>
          )}
          <strong>
            {formatSchoolMoney(total, preview?.currency || item.currency)}
          </strong>
          {hasDeposit && preview && (
            <small>À régler aujourd’hui : {formatSchoolMoney(preview.deposit_cents ?? 0, preview.currency)}</small>
          )}
          {paymentMode === 'installments' && preview && (
            <small>
              Le premier versement ouvre immédiatement votre accès. Les prochaines
              échéances seront visibles dans votre espace.
            </small>
          )}
          <button type="button" disabled={working || !preview || (preview.coupon_code || '').toUpperCase() !== coupon.trim().toUpperCase() || (hasDeposit && !acceptDepositTerms)} onClick={() => void pay()}>
            <CreditCard size={16} />
            {working ? 'Préparation…' : 'Payer maintenant'}
          </button>
          <small>
            <LockKeyhole size={12} /> Paiement sécurisé
          </small>
        </aside>
      </div>
    </main>
  )
}
