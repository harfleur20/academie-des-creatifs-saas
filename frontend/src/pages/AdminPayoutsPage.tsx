import { useEffect, useState } from 'react'
import { ApiError, listAdminPayouts, markAdminPayoutPaid, rejectAdminPayout, type AdminPayout, type Payout } from '../lib/api'
import { formatMoney } from '../lib/planFeatures'

const FILTERS: Array<{ value: Payout['status'] | ''; label: string }> = [
  { value: 'requested', label: 'À traiter' },
  { value: 'paid', label: 'Versés' },
  { value: 'rejected', label: 'Refusés' },
  { value: '', label: 'Tous' },
]
const METHODS: Record<Payout['method'], string> = { mobile_money: 'Mobile Money', bank: 'Virement bancaire' }

/** Super admin: transfer what schools asked for, then mark it paid (or refuse it with a reason). */
export function AdminPayoutsPage() {
  const [status, setStatus] = useState<Payout['status'] | ''>('requested')
  const [items, setItems] = useState<AdminPayout[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<number | null>(null)

  async function load(filter = status) {
    try {
      setItems(await listAdminPayouts(filter || undefined))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de charger les retraits.')
    }
  }

  useEffect(() => { void load(status) }, [status])

  async function markPaid(payout: AdminPayout) {
    const reference = window.prompt(`Référence du virement de ${formatMoney(payout.amount_cents, payout.currency)} à ${payout.organization_name} :`)
    if (!reference) return
    setBusy(payout.id)
    try {
      await markAdminPayoutPaid(payout.id, { transfer_reference: reference })
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Mise à jour impossible.')
    } finally {
      setBusy(null)
    }
  }

  async function reject(payout: AdminPayout) {
    const note = window.prompt(`Raison du refus (envoyée à ${payout.organization_name}) :`)
    if (!note) return
    setBusy(payout.id)
    try {
      await rejectAdminPayout(payout.id, note)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Mise à jour impossible.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <main className="admin-page">
      <header className="admin-page-header">
        <div>
          <span className="section-label">Reversements</span>
          <h1>Retraits des écoles</h1>
          <p>Faites le virement, puis marquez-le versé avec sa référence : l’école est prévenue.</p>
        </div>
      </header>
      <div className="admin-filter-tabs">
        {FILTERS.map((item) => (
          <button key={item.label} type="button" className={status === item.value ? 'is-active' : ''} onClick={() => setStatus(item.value)}>{item.label}</button>
        ))}
      </div>
      {error && <div className="form-error">{error}</div>}
      <section className="app-card">
        {items.length === 0 ? <p className="muted-note">Aucun retrait.</p> : (
          <ul className="revenue-list">
            {items.map((payout) => (
              <li key={payout.id}>
                <div>
                  <strong>{payout.organization_name} · {formatMoney(payout.amount_cents, payout.currency)}</strong>
                  <small>{METHODS[payout.method]} · {payout.destination} · {payout.account_name}</small>
                  <small>Demandé le {new Date(payout.requested_at).toLocaleString('fr-FR')}{payout.transfer_reference ? ` · réf. ${payout.transfer_reference}` : ''}{payout.note ? ` · ${payout.note}` : ''}</small>
                </div>
                {payout.status === 'requested' ? (
                  <span className="admin-payout-actions">
                    <button className="primary-button" type="button" disabled={busy === payout.id} onClick={() => void markPaid(payout)}>Marquer versé</button>
                    <button className="secondary-button" type="button" disabled={busy === payout.id} onClick={() => void reject(payout)}>Refuser</button>
                  </span>
                ) : <span className={`revenue-status is-${payout.status}`}>{payout.status === 'paid' ? 'Versé' : payout.status === 'rejected' ? 'Refusé' : 'Annulé'}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  )
}
