import { CreditCard, Download } from 'lucide-react'
import { useEffect, useState } from 'react'
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

export function StudentPaymentsPage() {
  const { activeOrganization } = useTenant()
  const schoolKey = activeOrganization?.slug || ''
  const [orders, setOrders] = useState<SchoolOrder[]>([])
  const [invoices, setInvoices] = useState<Record<number, SchoolInvoice[]>>({})
  const [loading, setLoading] = useState(true)
  const [workingId, setWorkingId] = useState<number | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!schoolKey) return
    let active = true
    setLoading(true)
    listPublicOrders(schoolKey).then(async (rows) => {
      if (!active) return
      setOrders(rows)
      const results = await Promise.allSettled(rows.map((row) => listPublicOrderInvoices(schoolKey, row.order_id)))
      if (active) setInvoices(Object.fromEntries(results.map((result, index) => [rows[index].order_id, result.status === 'fulfilled' ? result.value : []])))
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : 'Paiements indisponibles.')
    }).finally(() => { if (active) setLoading(false) })
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
      saveBlobFile(await downloadPublicInvoicePdf(schoolKey, invoice.id), invoice.invoice_number + '.pdf')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Téléchargement impossible.')
    }
  }

  return <main className="app-page student-payments-page">
    <header className="app-page-header"><div><span className="page-kicker">Mon compte</span><h1>Mes paiements</h1><p>Retrouvez vos échéances et vos factures.</p></div></header>
    {error && <div className="form-error">{error}</div>}
    {loading && <div className="page-state">Chargement des paiements…</div>}
    {!loading && orders.length === 0 && <div className="app-card">Aucune commande pour cette école.</div>}
    {orders.map((order) => <section className="app-card student-payment-order" key={order.order_id}>
      <div className="table-heading"><div><span className="section-label">{order.order_number}</span><h2>{order.formation_title}</h2><p>{order.session_label}</p></div><strong>{formatSchoolMoney(order.final_price_cents, order.currency)}</strong></div>
      <p>Déjà payé : {formatSchoolMoney(order.paid_cents, order.currency)}</p>
      {order.status === 'payment_review' && <p>Paiement reçu après l'expiration de la réservation : contactez l'école pour la suite.</p>}
      <div className="student-payment-installments">
        {order.installments.map((installment) => <div className="student-payment-installment" key={installment.id}>
          <span>Échéance {installment.sequence} · {new Date(installment.due_at).toLocaleDateString('fr-FR')}</span>
          <strong>{formatSchoolMoney(installment.amount_cents, order.currency)}</strong>
          <span>{installment.status === 'paid' ? 'Payée' : installment.status === 'cancelled' ? 'Annulée' : installment.status === 'late' ? 'En retard' : 'À payer'}</span>
          {!['cancelled', 'payment_review', 'refunded'].includes(order.status) && installment.status !== 'paid' && order.installments.find((row) => row.status !== 'paid')?.id === installment.id && <button type="button" disabled={workingId !== null} onClick={() => void pay(installment.id)}><CreditCard size={15} /> {workingId === installment.id ? 'Ouverture…' : 'Payer'}</button>}
        </div>)}
      </div>
      {(invoices[order.order_id] || []).length > 0 && <div className="school-receipt-list"><strong>Factures</strong>{invoices[order.order_id].map((invoice) => <button key={invoice.id} type="button" onClick={() => void download(invoice)}><Download size={14} /> {invoice.invoice_number}</button>)}</div>}
    </section>)}
  </main>
}
