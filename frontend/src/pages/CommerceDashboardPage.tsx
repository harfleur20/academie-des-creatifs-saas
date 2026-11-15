import { useEffect, useState } from 'react'
import {
  Banknote,
  AlertTriangle,
  CircleDollarSign,
  Clock3,
  Download,
  FileText,
  ShoppingCart,
  Users,
} from 'lucide-react'
import {
  ApiError,
  downloadSchoolInvoicePdf,
  getCommercialDashboard,
  listSchoolInvoices,
  listSchoolOrders,
  listCommunicationsNeedingReview,
  retryCommunicationAfterReview,
  type CommunicationNeedsReview,
  type CommercialDashboard,
  type SchoolInvoice,
  type SchoolOrder,
} from '../lib/api'
import { saveBlobFile } from '../lib/download'
import { formatSchoolMoney } from '../public/publicHelpers'

const ORDER_STATUS_LABELS: Record<string, string> = {
  pending: 'En attente',
  partially_paid: 'Paiement partiel',
  paid: 'Payée',
  late: 'En retard',
  cancelled: 'Annulée',
  payment_review: 'Paiement à vérifier',
}

export function CommerceDashboardPage() {
  const [dashboard, setDashboard] = useState<CommercialDashboard | null>(null)
  const [orders, setOrders] = useState<SchoolOrder[]>([])
  const [invoices, setInvoices] = useState<SchoolInvoice[]>([])
  const [reviewMessages, setReviewMessages] = useState<CommunicationNeedsReview[]>([])
  const [retryingMessageId, setRetryingMessageId] = useState<number | null>(null)
  const [ordersLoaded, setOrdersLoaded] = useState(false)
  const [invoicesLoaded, setInvoicesLoaded] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    void Promise.allSettled([
      getCommercialDashboard(),
      listSchoolOrders(),
      listSchoolInvoices(),
      listCommunicationsNeedingReview(),
    ])
      .then(([summary, orderRows, invoiceRows, messages]) => {
        if (!active) return
        const errors: string[] = []
        if (summary.status === 'fulfilled') setDashboard(summary.value)
        else errors.push(`Indicateurs : ${summary.reason instanceof ApiError ? summary.reason.message : 'Chargement impossible.'}`)
        if (orderRows.status === 'fulfilled') { setOrders(orderRows.value); setOrdersLoaded(true) }
        else errors.push(`Commandes : ${orderRows.reason instanceof ApiError ? orderRows.reason.message : 'Chargement impossible.'}`)
        if (invoiceRows.status === 'fulfilled') { setInvoices(invoiceRows.value); setInvoicesLoaded(true) }
        else errors.push(`Factures : ${invoiceRows.reason instanceof ApiError ? invoiceRows.reason.message : 'Chargement impossible.'}`)
        if (messages.status === 'fulfilled') setReviewMessages(messages.value)
        else errors.push(`Messages : ${messages.reason instanceof ApiError ? messages.reason.message : 'Chargement impossible.'}`)
        setError(errors.join(' '))
        setLoading(false)
      })
    return () => { active = false }
  }, [])

  async function downloadInvoice(invoice: SchoolInvoice) {
    setError('')
    try {
      const blob = await downloadSchoolInvoicePdf(invoice.id)
      saveBlobFile(blob, invoice.invoice_number + '.pdf')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Téléchargement impossible.')
    }
  }

  async function retryMessage(message: CommunicationNeedsReview) {
    setRetryingMessageId(message.id)
    setError('')
    try {
      await retryCommunicationAfterReview(message.id)
      setReviewMessages((current) => current.filter((row) => row.id !== message.id))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Reprise impossible.')
    } finally {
      setRetryingMessageId(null)
    }
  }

  return (
    <main className="app-page commerce-admin-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Commerce</span>
          <h1>Ventes & paiements étudiants</h1>
          <p>Cette comptabilité est distincte de votre abonnement à la plateforme.</p>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}
      {loading && <div className="page-state">Chargement des ventes…</div>}

      {dashboard && (
        <section className="commerce-kpis">
          <article>
            <ShoppingCart />
            <strong>{dashboard.order_count}</strong>
            <span>Commandes</span>
          </article>
          <article>
            <CircleDollarSign />
            <strong>{dashboard.totals_by_currency.length ? dashboard.totals_by_currency.map((row) => formatSchoolMoney(row.collected_cents, row.currency)).join(' · ') : '-'}</strong>
            <span>Encaissé</span>
          </article>
          <article>
            <Clock3 />
            <strong>{dashboard.totals_by_currency.length ? dashboard.totals_by_currency.map((row) => formatSchoolMoney(row.outstanding_cents, row.currency)).join(' · ') : '-'}</strong>
            <span>À encaisser</span>
          </article>
          <article>
            <Banknote />
            <strong>{dashboard.late_installments}</strong>
            <span>Échéances en retard</span>
          </article>
          <article>
            <Users />
            <strong>{dashboard.active_students}</strong>
            <span>Étudiants actifs</span>
          </article>
        </section>
      )}

      {reviewMessages.length > 0 && <section className="app-card commerce-table-card">
        <div className="table-heading"><div><span className="section-label">Notifications</span><h2>Envois à vérifier</h2></div><AlertTriangle size={18} /></div>
        <p>Un envoi a pu être accepté par le fournisseur malgré une interruption. Vérifiez son statut chez le fournisseur avant de le remettre en attente.</p>
        {reviewMessages.map((message) => <div className="student-payment-installment" key={message.id}>
          <span>{message.channel} · {message.recipient} · {message.event_key}</span>
          <small>{message.last_error || 'Résultat de l’envoi inconnu.'}</small>
          <button type="button" disabled={retryingMessageId !== null} onClick={() => void retryMessage(message)}>{retryingMessageId === message.id ? 'Reprise…' : 'Renvoyer après vérification'}</button>
        </div>)}
      </section>}

      <section className="app-card commerce-table-card">
        <div className="table-heading">
          <div>
            <span className="section-label">Commandes</span>
            <h2>Dernières ventes</h2>
          </div>
        </div>
        <div className="commerce-table">
          <div className="commerce-row is-head">
            <span>Commande</span>
            <span>Étudiant</span>
            <span>Formation / session</span>
            <span>Total</span>
            <span>Payé</span>
            <span>Statut</span>
          </div>
          {orders.map((order) => (
            <div className="commerce-row" key={order.order_id}>
              <span>
                <strong>{order.order_number}</strong>
                <small>{new Date(order.created_at).toLocaleDateString('fr-FR')}</small>
              </span>
              <span>
                <strong>{order.student_name}</strong>
                <small>{order.student_code || 'Matricule après paiement'}</small>
              </span>
              <span>
                <strong>{order.formation_title}</strong>
                <small>{order.session_label}</small>
              </span>
              <span>{formatSchoolMoney(order.final_price_cents, order.currency)}</span>
              <span>{formatSchoolMoney(order.paid_cents, order.currency)}</span>
              <span className={'order-status ' + order.status} title={order.status === 'payment_review' ? 'Paiement arrivé après la fin de la réservation : vérifier le dossier et le remboursement éventuel.' : undefined}>{ORDER_STATUS_LABELS[order.status] ?? order.status}</span>
            </div>
          ))}
          {ordersLoaded && orders.length === 0 && <div className="empty-row">Aucune commande pour cette école.</div>}
        </div>
      </section>

      <section className="app-card commerce-table-card">
        <div className="table-heading">
          <div>
            <span className="section-label">Factures & reçus</span>
            <h2>Documents émis</h2>
          </div>
          <FileText size={18} />
        </div>
        <div className="commerce-table invoice-table">
          <div className="commerce-row is-head">
            <span>N°</span>
            <span>Commande</span>
            <span>Montant</span>
            <span>Date</span>
            <span>Statut</span>
            <span />
          </div>
          {invoices.map((invoice) => (
            <div className="commerce-row" key={invoice.id}>
              <strong>{invoice.invoice_number}</strong>
              <span>#{invoice.order_id}</span>
              <span>{formatSchoolMoney(invoice.amount_cents, invoice.currency)}</span>
              <span>{new Date(invoice.issued_at).toLocaleDateString('fr-FR')}</span>
              <span>{invoice.status === 'paid' ? 'Payée' : invoice.status === 'void' ? 'Annulée' : invoice.status}</span>
              <span>
                <button
                  type="button"
                  className="document-download-button"
                  onClick={() => void downloadInvoice(invoice)}
                >
                  <Download size={13} />
                  PDF
                </button>
              </span>
            </div>
          ))}
          {invoicesLoaded && invoices.length === 0 && <div className="empty-row">Aucune facture émise.</div>}
        </div>
      </section>
    </main>
  )
}
