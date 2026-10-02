import {
  CheckCircle2,
  CreditCard,
  Download,
  LockKeyhole,
  Tag,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  confirmPublicDemoCheckout,
  createPublicCheckout,
  downloadPublicInvoicePdf,
  getPublicOrder,
  listPublicOrderInvoices,
  previewPublicPrice,
  reconcilePublicTaraCheckout,
  setStoredOrganizationId,
  type Checkout,
  type PricePreview,
  type SchoolInvoice,
} from '../lib/api'
import { saveBlobFile } from '../lib/download'
import { clearSchoolCart, getSchoolCart } from '../public/schoolCart'
import { formatSchoolMoney } from '../public/publicHelpers'
import { usePublicSchool } from '../public/SchoolPublicLayout'

export function SchoolCheckoutPage() {
  const { schoolSlug = '' } = useParams()
  const { school } = usePublicSchool()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const item = getSchoolCart(schoolSlug)

  const [preview, setPreview] = useState<PricePreview | null>(null)
  const [coupon, setCoupon] = useState('')
  const [paymentMode, setPaymentMode] = useState<'full' | 'installments'>('full')
  const [order, setOrder] = useState<Checkout | null>(null)
  const [invoices, setInvoices] = useState<SchoolInvoice[]>([])
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    const orderId = Number(params.get('order') || 0)
    if (!user || !orderId) return

    getPublicOrder(schoolSlug, orderId)
      .then(async (value) => {
        setOrder(value)
        if (params.get('demo') === '1' && value.status !== 'paid') {
          const next = await confirmPublicDemoCheckout(schoolSlug, orderId)
          setOrder(next)
          if (next.status === 'paid' || next.status === 'partially_paid') {
            setSuccess(true)
          }
        } else if (
          params.get('payment') === 'return' &&
          value.provider_reference
        ) {
          const next = await reconcilePublicTaraCheckout(
            schoolSlug,
            value.provider_reference,
          )
          setOrder(next)
          if (next.status === 'paid' || next.status === 'partially_paid') {
            setSuccess(true)
          }
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Commande introuvable.'))
  }, [user, schoolSlug, params])

  useEffect(() => {
    if (!user || !item) return
    previewPublicPrice(schoolSlug, item.session_id, null)
      .then(setPreview)
      .catch((err) => setError(err instanceof Error ? err.message : 'Prix indisponible.'))
  }, [user, schoolSlug, item?.session_id])

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

  async function applyCoupon() {
    if (!item || !user) return
    setError('')
    try {
      setPreview(
        await previewPublicPrice(
          schoolSlug,
          item.session_id,
          coupon.trim() || null,
        ),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Code promo invalide.')
    }
  }

  async function pay() {
    if (!item || !user) return
    setWorking(true)
    setError('')
    try {
      const created = await createPublicCheckout(
        schoolSlug,
        item.session_id,
        paymentMode,
        preview?.coupon_code || coupon.trim() || null,
      )
      setOrder(created)
      if (created.final_price_cents === 0) {
        setSuccess(true)
        clearSchoolCart(schoolSlug)
        return
      }
      if (created.checkout_url) {
        window.location.assign(created.checkout_url)
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

  function enterSpace() {
    setStoredOrganizationId(school.organization_id)
    clearSchoolCart(schoolSlug)
    navigate('/app/student')
  }

  if (success || order?.status === 'paid' || order?.status === 'partially_paid') {
    return (
      <main className="school-section school-checkout-page">
        <section className="school-payment-success">
          <CheckCircle2 size={42} />
          <span className="school-kicker">Paiement confirmé</span>
          <h1>Votre inscription est ouverte</h1>
          <p>Votre matricule et votre accès étudiant ont été créés automatiquement.</p>
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
          <button type="button" onClick={enterSpace}>
            Accéder à mon espace étudiant
          </button>
        </section>
      </main>
    )
  }

  if (!item) {
    return (
      <main className="school-section">
        <div className="school-empty">
          Votre panier est vide.{' '}
          <Link to={'/school/' + schoolSlug + '/formations'}>Voir les formations</Link>
        </div>
      </main>
    )
  }

  if (!user) {
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
                encodeURIComponent('/school/' + schoolSlug + '/checkout')
              }
            >
              Se connecter
            </Link>
            <Link
              to={
                '/login?mode=register&school=' +
                encodeURIComponent(schoolSlug) +
                '&return=' +
                encodeURIComponent('/school/' + schoolSlug + '/checkout')
              }
            >
              Créer mon compte
            </Link>
          </div>
        </section>
      </main>
    )
  }

  const total = preview?.final_price_cents ?? item.price_cents

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
            <p>Session : {item.session_label}</p>
            <div className="school-coupon-box">
              <Tag size={16} />
              <input
                value={coupon}
                onChange={(event) => setCoupon(event.target.value)}
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
                Paiement comptant
              </label>
              <label>
                <input
                  type="radio"
                  checked={paymentMode === 'installments'}
                  onChange={() => setPaymentMode('installments')}
                />
                Paiement en {preview.installment_count} tranches
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
          {paymentMode === 'installments' && preview && (
            <small>
              Le premier versement ouvre immédiatement votre accès. Les prochaines
              échéances seront visibles dans votre espace.
            </small>
          )}
          <button type="button" disabled={working} onClick={() => void pay()}>
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
