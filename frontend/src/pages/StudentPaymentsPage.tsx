import {
  AlertTriangle,
  Check,
  CreditCard,
  Download,
  FileText,
  Layers3,
  ReceiptText,
  WalletCards,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useTenant } from '../app/TenantContext'
import {
  downloadPublicInvoicePdf,
  listPublicOrderInvoices,
  listPublicOrders,
  payPublicInstallment,
  type SchoolInvoice,
  type SchoolOrder,
} from '../lib/api'
import { saveBlobFile } from '../lib/download'
import { formatSchoolMoney } from '../public/publicHelpers'

type PaymentTab = 'all' | 'installments' | 'single' | 'pending'

function shortDate(value: string) {
  return new Date(value).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

function orderStatus(order: SchoolOrder) {
  if (order.status === 'paid') return { label: 'Soldé', tone: 'green' }
  if (order.status === 'late') return { label: 'Échéance en retard', tone: 'red' }
  if (order.status === 'payment_review') return { label: 'À vérifier', tone: 'yellow' }
  if (order.status === 'cancelled') return { label: 'Annulée', tone: 'gray' }
  if (order.status === 'refunded') return { label: 'Remboursée', tone: 'gray' }
  if (order.status === 'partially_paid') {
    const paid = order.installments.filter((row) => row.status === 'paid').length
    return { label: `${paid}/${order.installments.length} versements`, tone: 'blue' }
  }
  return { label: 'À régler', tone: 'blue' }
}

function aggregateMoney(orders: SchoolOrder[], selector: (order: SchoolOrder) => number) {
  const totals = new Map<string, number>()
  orders.forEach((order) => {
    totals.set(order.currency, (totals.get(order.currency) || 0) + selector(order))
  })
  if (!totals.size) return '-'
  return [...totals.entries()]
    .map(([currency, amount]) => formatSchoolMoney(amount, currency))
    .join(' · ')
}

function installmentLabel(order: { deposit_cents: number | null; installment_count: number }, sequence: number) {
  if (order.deposit_cents == null) return 'Échéance'
  if (sequence === 1) return 'Acompte'
  return order.installment_count === 2 ? 'Solde' : `Solde ${sequence - 1}/${order.installment_count - 1}`
}

export function StudentPaymentsPage() {
  const { activeOrganization } = useTenant()
  const schoolKey = activeOrganization?.slug || ''
  const [orders, setOrders] = useState<SchoolOrder[]>([])
  const [invoices, setInvoices] = useState<Record<number, SchoolInvoice[]>>({})
  const [loading, setLoading] = useState(true)
  const [workingId, setWorkingId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<PaymentTab>('all')

  useEffect(() => {
    if (!schoolKey) return
    let active = true
    setLoading(true)
    setError('')
    listPublicOrders(schoolKey).then(async (rows) => {
      if (!active) return
      setOrders(rows)
      const results = await Promise.allSettled(
        rows.map((row) => listPublicOrderInvoices(schoolKey, row.order_id)),
      )
      if (active) {
        setInvoices(Object.fromEntries(results.map((result, index) => [
          rows[index].order_id,
          result.status === 'fulfilled' ? result.value : [],
        ])))
      }
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : 'Paiements indisponibles.')
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [schoolKey])

  async function pay(installmentId: number) {
    setWorkingId(installmentId)
    setError('')
    try {
      const result = await payPublicInstallment(schoolKey, installmentId)
      if (!result.checkout_url) throw new Error('Le lien de paiement est indisponible.')
      window.location.assign(result.checkout_url)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Paiement impossible.')
      setWorkingId(null)
    }
  }

  async function download(invoice: SchoolInvoice) {
    try {
      saveBlobFile(
        await downloadPublicInvoicePdf(schoolKey, invoice.id),
        `${invoice.invoice_number}.pdf`,
      )
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Téléchargement impossible.')
    }
  }

  const activeOrders = useMemo(
    () => orders.filter((order) => !['cancelled', 'refunded'].includes(order.status)),
    [orders],
  )

  const visibleOrders = useMemo(() => orders.filter((order) => {
    if (tab === 'installments') return order.installment_count > 1
    if (tab === 'single') return order.installment_count <= 1
    if (tab === 'pending') return !['paid', 'cancelled', 'refunded'].includes(order.status)
    return true
  }), [orders, tab])

  const reminders = useMemo(() => activeOrders.flatMap((order) =>
    order.installments
      .filter((installment) => installment.status !== 'paid' && installment.status !== 'cancelled')
      .map((installment) => ({ order, installment })),
  ).sort((a, b) => new Date(a.installment.due_at).getTime() - new Date(b.installment.due_at).getTime()), [activeOrders])

  const paidTotal = aggregateMoney(activeOrders, (order) => order.paid_cents)
  const outstandingTotal = aggregateMoney(
    activeOrders,
    (order) => Math.max(0, order.final_price_cents - order.paid_cents),
  )
  const pendingCount = reminders.length

  return (
    <main className="app-page">
      <div className="dsh-page student-payments-mother">
        <div className="dsh-page__header">
          <h1>Mes paiements</h1>
          <p className="dsh-page__subtitle">
            Suivez vos règlements, vos prochaines échéances et téléchargez vos factures.
          </p>
        </div>

        {error && <div className="dsh-error">{error}</div>}
        {loading && <div className="dsh-empty">Chargement des paiements…</div>}

        {!loading && (
          <>
            <section className="pay-kpi-row" aria-label="Résumé des paiements">
              <div className="pay-kpi pay-kpi--blue">
                <span className="pay-kpi__icon"><Layers3 size={18} /></span>
                <div><strong>{orders.length}</strong><span>Formation{orders.length > 1 ? 's' : ''} achetée{orders.length > 1 ? 's' : ''}</span></div>
              </div>
              <div className="pay-kpi pay-kpi--green">
                <span className="pay-kpi__icon"><WalletCards size={18} /></span>
                <div><strong title={paidTotal}>{paidTotal}</strong><span>Total réglé</span></div>
              </div>
              <div className="pay-kpi pay-kpi--yellow">
                <span className="pay-kpi__icon"><CreditCard size={18} /></span>
                <div><strong title={outstandingTotal}>{outstandingTotal}</strong><span>Reste à régler</span></div>
              </div>
              <div className="pay-kpi pay-kpi--gray">
                <span className="pay-kpi__icon"><ReceiptText size={18} /></span>
                <div><strong>{pendingCount}</strong><span>Échéance{pendingCount > 1 ? 's' : ''} ouverte{pendingCount > 1 ? 's' : ''}</span></div>
              </div>
            </section>

            <div className="pay-tabs" role="tablist" aria-label="Filtrer les paiements">
              {([
                ['all', 'Tous'],
                ['installments', 'Paiement en plusieurs fois'],
                ['single', 'Paiement unique'],
                ['pending', 'À régler'],
              ] as Array<[PaymentTab, string]>).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className={`pay-tab${tab === value ? ' is-active' : ''}`}
                  onClick={() => setTab(value)}
                >
                  {label}
                </button>
              ))}
            </div>

            {orders.length === 0 ? (
              <div className="dsh-empty">
                <div><FileText size={28} /><strong>Aucun paiement</strong><p>Vos achats auprès de cette école apparaîtront ici.</p></div>
              </div>
            ) : visibleOrders.length === 0 ? (
              <div className="dsh-empty">Aucun paiement dans cette catégorie.</div>
            ) : (
              <div className="pay-card-list">
                {visibleOrders.map((order) => {
                  const status = orderStatus(order)
                  const orderInvoices = invoices[order.order_id] || []
                  const firstUnpaid = order.installments.find((row) => row.status !== 'paid')
                  const paymentLocked = ['cancelled', 'payment_review', 'refunded'].includes(order.status)

                  return (
                    <section className="pay-card" key={order.order_id}>
                      <div className="pay-card__head">
                        <div className="pay-card__head-left">
                          <span className="pay-type-badge">
                            {order.deposit_cents != null
                              ? `Acompte + ${order.installment_count - 1} paiement(s)`
                              : order.payment_mode === 'installments'
                              ? `${order.installment_count}× · Paiement fractionné`
                              : '1× · Paiement unique'}
                          </span>
                          <h2 className="pay-card__name">{order.formation_title}</h2>
                          <p className="pay-card__meta">{order.session_label} · {order.order_number}</p>
                        </div>

                        <div className="pay-card__head-mid">
                          <strong className="pay-card__total">{formatSchoolMoney(order.final_price_cents, order.currency)}</strong>
                          <span className="pay-card__mid-sub">
                            Déjà réglé : {formatSchoolMoney(order.paid_cents, order.currency)}
                          </span>
                        </div>

                        <div className="pay-card__head-right">
                          <span className={`pay-card__status pay-card__status--${status.tone}`}>{status.label}</span>
                          {orderInvoices.map((invoice) => (
                            <button
                              className="pay-card__dl-btn"
                              key={invoice.id}
                              type="button"
                              onClick={() => void download(invoice)}
                            >
                              <Download size={12} /> Facture {invoice.invoice_number}
                            </button>
                          ))}
                        </div>
                      </div>

                      {order.status === 'payment_review' && (
                        <div className="dsh-error" style={{ margin: '0 18px 14px' }}>
                          Paiement reçu mais en vérification par l’école. Aucun nouveau paiement n’est possible sur cette commande.
                        </div>
                      )}

                      <div className="pay-card__body">
                        <div className="pay-stepper">
                          {order.installments.map((installment, index) => {
                            const paid = installment.status === 'paid'
                            const cancelled = installment.status === 'cancelled'
                            const canPay = !paymentLocked && !paid && firstUnpaid?.id === installment.id
                            return (
                              <div className="pay-stepper__item" key={installment.id}>
                                {index > 0 && (
                                  <span className={`pay-stepper__line${order.installments[index - 1].status === 'paid' ? ' pay-stepper__line--done' : ''}`} />
                                )}
                                <span className={`pay-stepper__dot ${paid ? 'pay-stepper__dot--done' : 'pay-stepper__dot--pending'}`}>
                                  {paid ? <Check size={12} /> : installment.sequence}
                                </span>
                                <div className="pay-stepper__info">
                                  <span className="pay-stepper__label">
                                    {paid ? 'Payée' : cancelled ? 'Annulée' : installment.status === 'late' ? 'En retard' : installmentLabel(order, installment.sequence)}
                                  </span>
                                  <strong className="pay-stepper__amount">{formatSchoolMoney(installment.amount_cents, order.currency)}</strong>
                                  <span className="pay-stepper__date">Prévue le {shortDate(installment.due_at)}</span>
                                  {canPay && (
                                    <button
                                      className="pay-inline-btn"
                                      type="button"
                                      disabled={workingId !== null}
                                      onClick={() => void pay(installment.id)}
                                    >
                                      <CreditCard size={11} /> {workingId === installment.id ? 'Ouverture…' : 'Payer'}
                                    </button>
                                  )}
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    </section>
                  )
                })}
              </div>
            )}

            {reminders.length > 0 && (
              <section className="pay-reminders">
                <h2 className="pay-reminders__title"><AlertTriangle size={15} /> Prochaines échéances</h2>
                <div className="pay-reminders__list">
                  {reminders.slice(0, 6).map(({ order, installment }) => (
                    <div className="pay-reminder-item" key={installment.id}>
                      <span className="pay-reminder-item__icon"><CreditCard size={14} /></span>
                      <div className="pay-reminder-item__body">
                        <strong>{order.formation_title}</strong>
                        <span>{order.session_label} · {order.deposit_cents != null ? installmentLabel(order, installment.sequence).toLowerCase() : `échéance ${installment.sequence}/${order.installments.length}`}</span>
                      </div>
                      <div className="pay-reminder-item__right">
                        <strong>{formatSchoolMoney(installment.amount_cents, order.currency)}</strong>
                        <span className="pay-reminder-item__tag">
                          {installment.status === 'late' ? 'En retard' : `Le ${shortDate(installment.due_at)}`}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </main>
  )
}
