import { useEffect, useState, type FormEvent } from 'react'
import { ArrowDownToLine, Banknote, Clock3, Percent, Wallet } from 'lucide-react'
import {
  ApiError,
  cancelPayout,
  getRevenueSummary,
  listLedgerEntries,
  listPayouts,
  requestPayout,
  type LedgerEntry,
  type Payout,
  type RevenueSummary,
} from '../lib/api'
import { commissionLabel, formatMoney } from '../lib/planFeatures'

const PAYOUT_STATUS: Record<Payout['status'], string> = {
  requested: 'En cours',
  paid: 'Versé',
  rejected: 'Refusé',
  cancelled: 'Annulé',
}
const METHODS: Record<Payout['method'], string> = { mobile_money: 'Mobile Money', bank: 'Virement bancaire' }

function dateLabel(value: string) {
  return new Date(value).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })
}

/** What the school earned from its sales, net of the platform's commission, and its payouts (docs/FORFAITS.md). */
export function SchoolRevenuePage() {
  const [summary, setSummary] = useState<RevenueSummary | null>(null)
  const [entries, setEntries] = useState<LedgerEntry[]>([])
  const [payouts, setPayouts] = useState<Payout[]>([])
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState<Payout['method']>('mobile_money')
  const [destination, setDestination] = useState('')
  const [accountName, setAccountName] = useState('')

  async function load() {
    try {
      const [summaryItem, entryItems, payoutItems] = await Promise.all([getRevenueSummary(), listLedgerEntries(), listPayouts()])
      setSummary(summaryItem)
      setEntries(entryItems)
      setPayouts(payoutItems)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de charger vos revenus.')
    }
  }

  useEffect(() => { void load() }, [])

  const pending = payouts.find((item) => item.status === 'requested')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setMessage('')
    setBusy(true)
    try {
      await requestPayout({ amount_cents: Number(amount), method, destination, account_name: accountName })
      setMessage('Votre demande de retrait est enregistrée. Vous serez prévenu dès le versement.')
      setAmount('')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Demande de retrait impossible.')
    } finally {
      setBusy(false)
    }
  }

  async function cancel(payout: Payout) {
    setBusy(true)
    setError('')
    try {
      await cancelPayout(payout.id)
      setMessage('Votre demande de retrait est annulée.')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Annulation impossible.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="app-page revenue-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Ventes & visibilité</span>
          <h1>Revenus & retraits</h1>
          <p>
            Vos étudiants paient sur la plateforme. Chaque paiement vous est crédité, moins la commission de votre
            forfait{summary ? ` (${commissionLabel(summary.commission_bps)})` : ''}, frais de paiement compris.
          </p>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}
      {message && <div className="form-success">{message}</div>}

      {summary && (
        <section className="commerce-kpis revenue-kpis">
          <article>
            <Wallet />
            <strong>{formatMoney(summary.available_cents, summary.currency)}</strong>
            <span>Disponible au retrait</span>
          </article>
          <article>
            <Banknote />
            <strong>{formatMoney(summary.gross_cents, summary.currency)}</strong>
            <span>Payé par vos étudiants</span>
          </article>
          <article>
            <Percent />
            <strong>{formatMoney(summary.commission_cents, summary.currency)}</strong>
            <span>Commission plateforme</span>
          </article>
          <article>
            <ArrowDownToLine />
            <strong>{formatMoney(summary.paid_out_cents, summary.currency)}</strong>
            <span>Déjà versé</span>
          </article>
          <article>
            <Clock3 />
            <strong>{formatMoney(summary.pending_payout_cents, summary.currency)}</strong>
            <span>Retrait en cours</span>
          </article>
        </section>
      )}

      <div className="revenue-columns">
        <section className="app-card revenue-request">
          <div className="table-heading"><div><span className="section-label">Retrait</span><h2>Demander un versement</h2></div></div>
          {pending ? (
            <div className="revenue-pending">
              <p>
                Un retrait de <strong>{formatMoney(pending.amount_cents, pending.currency)}</strong> est en cours
                ({METHODS[pending.method]}, {pending.destination}), demandé le {dateLabel(pending.requested_at)}.
              </p>
              <button className="secondary-button" type="button" disabled={busy} onClick={() => void cancel(pending)}>Annuler la demande</button>
            </div>
          ) : (
            <form className="revenue-form" onSubmit={submit}>
              <label>
                Montant (FCFA)
                <input
                  type="number"
                  min={summary?.min_payout_cents ?? 10000}
                  max={summary?.available_cents}
                  step={1}
                  required
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  placeholder={summary ? String(summary.available_cents) : ''}
                />
                <small>Minimum {formatMoney(summary?.min_payout_cents ?? 10000, 'XAF')}.</small>
              </label>
              <label>
                Moyen de versement
                <select value={method} onChange={(event) => setMethod(event.target.value as Payout['method'])}>
                  <option value="mobile_money">Mobile Money</option>
                  <option value="bank">Virement bancaire</option>
                </select>
              </label>
              <label>
                {method === 'mobile_money' ? 'Numéro Mobile Money' : 'IBAN ou numéro de compte'}
                <input required value={destination} onChange={(event) => setDestination(event.target.value)} placeholder={method === 'mobile_money' ? '+237 6XX XX XX XX' : 'CM21 …'} />
              </label>
              <label>
                Titulaire du compte
                <input required value={accountName} onChange={(event) => setAccountName(event.target.value)} />
              </label>
              <button className="primary-button" type="submit" disabled={busy || !summary || summary.available_cents < summary.min_payout_cents}>
                Demander le versement
              </button>
            </form>
          )}
        </section>

        <section className="app-card revenue-history">
          <div className="table-heading"><div><span className="section-label">Historique</span><h2>Vos retraits</h2></div></div>
          {payouts.length === 0 ? <p className="muted-note">Aucun retrait pour le moment.</p> : (
            <ul className="revenue-list">
              {payouts.map((payout) => (
                <li key={payout.id}>
                  <div>
                    <strong>{formatMoney(payout.amount_cents, payout.currency)}</strong>
                    <small>{METHODS[payout.method]} · {dateLabel(payout.requested_at)}{payout.transfer_reference ? ` · réf. ${payout.transfer_reference}` : ''}</small>
                    {payout.note && <small>{payout.note}</small>}
                  </div>
                  <span className={`revenue-status is-${payout.status}`}>{PAYOUT_STATUS[payout.status]}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="app-card">
        <div className="table-heading"><div><span className="section-label">Détail</span><h2>Paiements de vos étudiants</h2></div></div>
        {entries.length === 0 ? <p className="muted-note">Les paiements de vos étudiants apparaîtront ici.</p> : (
          <div className="revenue-table">
            <div className="revenue-row revenue-row--head"><span>Date</span><span>Paiement</span><span>Payé</span><span>Commission</span><span>Pour vous</span></div>
            {entries.map((entry) => (
              <div className="revenue-row" key={entry.id}>
                <span>{dateLabel(entry.occurred_at)}</span>
                <span>{entry.description}</span>
                <span>{formatMoney(entry.gross_cents, entry.currency)}</span>
                <span>{formatMoney(entry.commission_cents, entry.currency)} <small>({(entry.commission_bps / 100).toLocaleString('fr-FR')} %)</small></span>
                <strong>{formatMoney(entry.amount_cents, entry.currency)}</strong>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}
