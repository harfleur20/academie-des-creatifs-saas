import { useState } from 'react'
import { AlertTriangle, CalendarClock, RotateCcw, Trash2 } from 'lucide-react'
import { useTenant } from '../app/TenantContext'
import { activeSchoolLocale } from '../app/schoolLocale'
import { ApiError, cancelOrganizationDeletion, requestOrganizationDeletion } from '../lib/api'

export function OrganizationDangerZone() {
  const { activeOrganization, accessProfile, refreshOrganizations } = useTenant()
  const [deletionConfirmation, setDeletionConfirmation] = useState('')
  const [deletionBusy, setDeletionBusy] = useState(false)
  const [deletionError, setDeletionError] = useState('')

  if (!activeOrganization || !accessProfile?.roles.includes('owner')) return null

  const deletionDate = activeOrganization.deletion_scheduled_at
    ? new Intl.DateTimeFormat(activeSchoolLocale(), {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(activeOrganization.deletion_scheduled_at))
    : ''

  async function scheduleSchoolDeletion() {
    if (!activeOrganization || deletionConfirmation.trim() !== activeOrganization.name) return
    setDeletionBusy(true)
    setDeletionError('')
    try {
      await requestOrganizationDeletion(deletionConfirmation)
      setDeletionConfirmation('')
      await refreshOrganizations()
    } catch (error) {
      setDeletionError(error instanceof ApiError ? error.message : 'Impossible de programmer la suppression.')
    } finally {
      setDeletionBusy(false)
    }
  }

  async function undoSchoolDeletion() {
    setDeletionBusy(true)
    setDeletionError('')
    try {
      await cancelOrganizationDeletion()
      await refreshOrganizations()
    } catch (error) {
      setDeletionError(error instanceof ApiError ? error.message : 'Impossible d’annuler la suppression.')
    } finally {
      setDeletionBusy(false)
    }
  }

  return (
    <section className="app-card organization-danger-zone" aria-labelledby="organization-danger-title">
      <div className="settings-section-heading">
        <div>
          <span className="section-label">Zone dangereuse</span>
          <h2 id="organization-danger-title">Supprimer cette école</h2>
          <p>Le site public sera désactivé dès la demande. La suppression définitive et irréversible des données intervient après 20 jours.</p>
        </div>
        <AlertTriangle size={24} aria-hidden="true" />
      </div>
      {activeOrganization.status === 'deletion_pending' ? (
        <>
          <div className="organization-deletion-pending" role="status">
            <CalendarClock size={22} aria-hidden="true" />
            <div>
              <strong>Suppression programmée</strong>
              <p>La suppression définitive est prévue le {deletionDate}. Le propriétaire peut encore annuler jusque-là.</p>
            </div>
          </div>
          <p className="organization-danger-note">Les données de l’école seront effacées. Les comptes personnels des membres ne seront pas supprimés.</p>
          <button className="secondary-button" type="button" onClick={() => void undoSchoolDeletion()} disabled={deletionBusy}>
            <RotateCcw size={16} />{deletionBusy ? 'Annulation…' : 'Annuler la suppression'}
          </button>
        </>
      ) : (
        <>
          <p className="organization-danger-note">Pendant ces 20 jours, seul le propriétaire peut accéder à l’école pour annuler. Après l’échéance, la suppression ne pourra plus être annulée. Les sauvegardes techniques suivent leur propre durée de conservation.</p>
          <label className="organization-deletion-confirmation">
            Pour confirmer, saisissez exactement le nom de l’école : <strong>{activeOrganization.name}</strong>
            <input
              value={deletionConfirmation}
              onChange={(event) => setDeletionConfirmation(event.target.value)}
              autoComplete="off"
              spellCheck={false}
              aria-label="Nom exact de l’école à supprimer"
            />
          </label>
          <button
            className="organization-danger-button"
            type="button"
            onClick={() => void scheduleSchoolDeletion()}
            disabled={deletionBusy || deletionConfirmation.trim() !== activeOrganization.name}
          >
            <Trash2 size={16} />{deletionBusy ? 'Programmation…' : 'Programmer la suppression'}
          </button>
        </>
      )}
      {deletionError && <div className="form-error" role="alert">{deletionError}</div>}
    </section>
  )
}
