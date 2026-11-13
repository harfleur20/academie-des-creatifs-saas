import {
  Banknote,
  CalendarDays,
  CheckCircle2,
  CreditCard,
  Download,
  Info,
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
import { formatSchoolMoney, formatSchoolPercent } from '../public/publicHelpers'
import { usePublicSchool } from '../public/SchoolPublicLayout'
import './school-checkout.css'

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
  // Preselected with the choice made on the formation page; used only while the plan is offered.
  const [paymentMode, setPaymentMode] = useState<'full' | 'installments'>(item?.payment_mode ?? 'full')
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
        paymentMode === 'installments' && preview.schedule_installments.length >= 2 ? 'installments' : 'full',
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
  const currency = preview?.currency || item.currency
  const money = (amount: number) => formatSchoolMoney(amount, currency)
  const hasDeposit = preview?.deposit_cents != null
  const canSplit = (preview?.schedule_installments.length ?? 0) >= 2
  const splitMode = paymentMode === 'installments' && canSplit
  const schedule = preview ? (splitMode ? preview.schedule_installments : preview.schedule_full) : []
  const dueToday = schedule[0]?.amount_cents ?? total
  const blocked = preview?.purchase_blocked_reason || ''
  const balanceDue = preview?.balance_due_date ? formatDay(preview.balance_due_date) : ''
  const splitCount = preview?.schedule_installments.length ?? 0
  const lastSplitDate = canSplit && preview ? formatDay(preview.schedule_installments[splitCount - 1].due_date) : ''
  const modeLabel = hasDeposit
    ? (splitMode ? splitDepositLabel(splitCount) : 'Acompte, puis le solde')
    : (splitMode ? `Paiement en ${splitCount} fois` : 'Paiement en une fois')

  function scheduleLabel(index: number, dueDate: string) {
    if (index === 0) return hasDeposit ? 'Acompte · aujourd’hui' : schedule.length > 1 ? '1re échéance · aujourd’hui' : 'Aujourd’hui'
    if (hasDeposit && !splitMode) return `Solde · avant le ${formatDay(dueDate)}`
    return `Échéance ${index + 1} · ${formatDay(dueDate)}`
  }

  return (
    <main className="school-section school-checkout-page">
      <header className="school-page-heading">
        <span className="school-kicker">Paiement sécurisé</span>
        <h1>Finalisez votre inscription</h1>
        <p>Choisissez comment payer : vous voyez le montant à régler aujourd’hui et chaque échéance à venir.</p>
      </header>
      {error && <div className="school-checkout-error">{error}</div>}
      {blocked && (
        <div className="school-checkout-notice">
          <Info size={16} />
          <span>{blocked} Vous voyez cette page comme un étudiant la verra.</span>
        </div>
      )}

      <div className="school-checkout-layout">
        <section className="school-checkout-main">
          <article className="school-checkout-order">
            <div className="school-checkout-item">
              {item.cover_image_url && <img src={item.cover_image_url} alt="" />}
              <div>
                <h2>{item.formation_title}</h2>
                <p>{item.format_type === 'ligne' || item.session_label === 'Accès en ligne' ? 'Formation en ligne' : `Session : ${item.session_label}`}</p>
              </div>
              <strong>{money(total)}</strong>
            </div>
            <div className="school-coupon-box">
              <Tag size={16} />
              <input
                value={coupon}
                onChange={(event) => { couponRef.current = event.target.value; setCoupon(event.target.value); setPreview(null) }}
                placeholder="Code promo"
              />
              <button type="button" onClick={() => void applyCoupon()}>
                Appliquer
              </button>
            </div>
            {preview?.total_discount_cents ? (
              <p className="school-discount-line">
                Réduction : -{money(preview.total_discount_cents)}
              </p>
            ) : null}
          </article>

          {preview && (
            <article className="school-payment-choice">
              <h3>Mode de paiement</h3>
              <div className="school-payment-options">
                <PaymentOption
                  selected={!splitMode}
                  onSelect={() => setPaymentMode('full')}
                  title={hasDeposit ? 'Acompte, puis le solde' : 'Payer en une fois'}
                  text={hasDeposit
                    ? `${money(preview.deposit_cents ?? 0)} aujourd’hui (${formatSchoolPercent(preview.deposit_percent ?? 0)}), puis ${money(preview.balance_cents ?? 0)} avant le ${balanceDue}.`
                    : `${money(total)} aujourd’hui.`}
                />
                {canSplit && (
                  <PaymentOption
                    selected={splitMode}
                    onSelect={() => setPaymentMode('installments')}
                    title={hasDeposit ? splitDepositLabel(splitCount) : `Payer en ${splitCount} fois`}
                    text={splitCount > 2
                      ? `${money(preview.schedule_installments[0].amount_cents)} aujourd’hui, puis ${splitCount - 1} échéances jusqu’au ${lastSplitDate}.`
                      : `${money(preview.schedule_installments[0].amount_cents)} aujourd’hui, puis ${money(preview.schedule_installments[1].amount_cents)} le ${lastSplitDate}.`}
                  />
                )}
              </div>
              {schedule.length > 1 && (
                <ol className="school-payment-schedule" aria-label="Échéancier">
                  {schedule.map((line, index) => (
                    <li key={line.due_date + index} className={index === 0 ? 'is-today' : ''}>
                      <span className="school-payment-schedule__icon" aria-hidden="true">
                        {index === 0 ? <Banknote size={15} /> : <CalendarDays size={15} />}
                      </span>
                      <span>{scheduleLabel(index, line.due_date)}</span>
                      <strong>{money(line.amount_cents)}</strong>
                    </li>
                  ))}
                </ol>
              )}
              {!canSplit && !hasDeposit && (
                <p className="school-payment-note">Cette formation se règle en une seule fois.</p>
              )}
            </article>
          )}

          {hasDeposit && preview && (
            <article className="school-payment-choice school-deposit-terms">
              <h3>Réservation avec acompte</h3>
              <p>
                Votre place est réservée dès l’acompte de <strong>{money(preview.deposit_cents ?? 0)}</strong>, et votre accès s’ouvre.
                {splitMode
                  ? ' Le solde suit l’échéancier ci-dessus.'
                  : <> Le solde de <strong>{money(preview.balance_cents ?? 0)}</strong> est à régler avant le {balanceDue}, 10 jours avant le début de la session.</>}
                {' '}Si une échéance n’est pas réglée à temps, votre accès est suspendu, mais votre place reste réservée.
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
            <del>{money(preview.base_price_cents)}</del>
          )}
          <strong>{money(total)}</strong>
          {preview && (
            <dl className="school-checkout-due">
              <div className="is-today">
                <dt>À payer aujourd’hui</dt>
                <dd>{money(dueToday)}</dd>
              </div>
              {schedule.slice(1).map((line, index) => (
                <div key={line.due_date + index}>
                  <dt>{scheduleLabel(index + 1, line.due_date)}</dt>
                  <dd>{money(line.amount_cents)}</dd>
                </div>
              ))}
            </dl>
          )}
          {preview && <p className="school-checkout-mode">Mode choisi : <b>{modeLabel}</b></p>}
          <button type="button" disabled={working || Boolean(blocked) || !preview || (preview.coupon_code || '').toUpperCase() !== coupon.trim().toUpperCase() || (hasDeposit && !acceptDepositTerms)} onClick={() => void pay()}>
            <CreditCard size={16} />
            {working ? 'Préparation…' : preview ? `Payer ${money(dueToday)} maintenant` : 'Payer maintenant'}
          </button>
          {schedule.length > 1 && (
            <small>Le premier paiement ouvre votre accès. Les échéances suivantes sont rappelées dans votre espace étudiant.</small>
          )}
          <small>
            <LockKeyhole size={12} /> Paiement sécurisé
          </small>
        </aside>
      </div>
    </main>
  )
}

/** With a deposit, the plan spreads the balance; a single later payment just postpones it. */
function splitDepositLabel(payments: number) {
  return payments > 2 ? `Acompte, puis le solde en ${payments - 1} fois` : 'Acompte, puis le solde plus tard'
}

function formatDay(iso: string) {
  return new Date(iso.slice(0, 10) + 'T00:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
}

function PaymentOption({ selected, onSelect, title, text }: { selected: boolean; onSelect: () => void; title: string; text: string }) {
  return (
    <label className={`school-payment-option${selected ? ' is-selected' : ''}`}>
      <input type="radio" name="payment-mode" checked={selected} onChange={onSelect} />
      <span>
        <strong>{title}</strong>
        <small>{text}</small>
      </span>
    </label>
  )
}
