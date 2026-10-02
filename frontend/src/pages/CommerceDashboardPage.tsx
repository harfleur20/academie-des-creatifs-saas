import { useEffect, useState } from 'react'
import {
  Banknote,
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
  type CommercialDashboard,
  type SchoolInvoice,
  type SchoolOrder,
} from '../lib/api'
import { saveBlobFile } from '../lib/download'
import { formatSchoolMoney } from '../public/publicHelpers'

export function CommerceDashboardPage() {
  const [dashboard, setDashboard] = useState<CommercialDashboard | null>(null)
  const [orders, setOrders] = useState<SchoolOrder[]>([])
  const [invoices, setInvoices] = useState<SchoolInvoice[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      getCommercialDashboard(),
      listSchoolOrders(),
      listSchoolInvoices(),
    ])
      .then(([summary, orderRows, invoiceRows]) => {
        setDashboard(summary)
        setOrders(orderRows)
        setInvoices(invoiceRows)
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Chargement impossible.'),
      )
  }, [])

  const money = (value: number) =>
    formatSchoolMoney(value, dashboard?.currency || 'XAF')

  async function downloadInvoice(invoice: SchoolInvoice) {
    setError('')
    try {
      const blob = await downloadSchoolInvoicePdf(invoice.id)
      saveBlobFile(blob, invoice.invoice_number + '.pdf')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Téléchargement impossible.')
    }
  }

  return (
    <main className="app-page commerce-admin-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Commerce</span>
          <h1>Ventes & paiements étudiants</h1>
          <p>Cette comptabilité est distincte de votre abonnement SaaS.</p>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}

      {dashboard && (
        <section className="commerce-kpis">
          <article>
            <ShoppingCart />
            <strong>{dashboard.order_count}</strong>
            <span>Commandes</span>
          </article>
          <article>
            <CircleDollarSign />
            <strong>{money(dashboard.collected_cents)}</strong>
            <span>Encaissé</span>
          </article>
          <article>
            <Clock3 />
            <strong>{money(dashboard.outstanding_cents)}</strong>
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
              <span className={'order-status ' + order.status}>{order.status}</span>
            </div>
          ))}
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
              <span>{invoice.status}</span>
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
        </div>
      </section>
    </main>
  )
}
