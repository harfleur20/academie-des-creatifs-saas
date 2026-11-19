import { useEffect, useState, type FormEvent } from 'react'
import { AlertTriangle, CalendarClock, CheckCircle2, Copy, Globe2, RotateCcw, Save, Trash2 } from 'lucide-react'
import { useTenant } from '../app/TenantContext'
import { activeSchoolLocale, setSchoolInterfaceLocale } from '../app/schoolLocale'
import {
  ApiError,
  createOrganizationDomain,
  cancelOrganizationDeletion,
  deleteOrganizationDomain,
  getOrganizationDomainConfig,
  getOrganizationPolicy,
  listOrganizationDomains,
  requestOrganizationDeletion,
  setPrimaryOrganizationDomain,
  updateCurrentOrganization,
  updateCurrentSubdomain,
  verifyOrganizationDomain,
  type OrganizationDomain,
  type OrganizationDomainConfig,
  type OrganizationPolicy,
} from '../lib/api'

type SettingsSection = 'school' | 'domains'

const popularTimezones = [
  { value: 'UTC', label: 'UTC' },
  { value: 'Africa/Douala', label: 'Afrique centrale - Douala' },
  { value: 'Africa/Abidjan', label: 'Afrique de l’Ouest - Abidjan' },
  { value: 'Africa/Dakar', label: 'Afrique de l’Ouest - Dakar' },
  { value: 'Africa/Lagos', label: 'Afrique de l’Ouest - Lagos' },
  { value: 'Africa/Casablanca', label: 'Afrique du Nord - Casablanca' },
  { value: 'Africa/Johannesburg', label: 'Afrique australe - Johannesburg' },
  { value: 'Europe/Paris', label: 'Europe - Paris' },
  { value: 'Europe/Brussels', label: 'Europe - Bruxelles' },
  { value: 'Europe/London', label: 'Europe - Londres' },
  { value: 'Europe/Berlin', label: 'Europe - Berlin' },
  { value: 'America/New_York', label: 'Amérique - New York' },
  { value: 'America/Toronto', label: 'Amérique - Toronto' },
  { value: 'America/Los_Angeles', label: 'Amérique - Los Angeles' },
  { value: 'America/Sao_Paulo', label: 'Amérique du Sud - São Paulo' },
  { value: 'Asia/Dubai', label: 'Moyen-Orient - Dubaï' },
  { value: 'Asia/Kolkata', label: 'Asie - Kolkata' },
  { value: 'Asia/Singapore', label: 'Asie - Singapour' },
  { value: 'Asia/Tokyo', label: 'Asie - Tokyo' },
  { value: 'Australia/Sydney', label: 'Océanie - Sydney' },
]

export function SchoolSettingsPage({ section = 'school' }: { section?: SettingsSection }) {
  const { activeOrganization, accessProfile, refreshOrganizations } = useTenant()
  const [name, setName] = useState('')
  const [contactEmail, setContactEmail] = useState('')
  const [timezone, setTimezone] = useState('UTC')
  const [locale, setLocale] = useState('fr-FR')
  const [subdomain, setSubdomain] = useState('')
  const [domains, setDomains] = useState<OrganizationDomain[]>([])
  const [domainConfig, setDomainConfig] = useState<OrganizationDomainConfig | null>(null)
  const [organizationPolicy, setOrganizationPolicy] = useState<OrganizationPolicy | null>(null)
  const [newDomain, setNewDomain] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [domainLoading, setDomainLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [deletionConfirmation, setDeletionConfirmation] = useState('')
  const [deletionBusy, setDeletionBusy] = useState(false)
  const [deletionError, setDeletionError] = useState('')

  async function loadDomains() {
    if (!activeOrganization) return
    try {
      const [items, config] = await Promise.all([
        listOrganizationDomains(),
        getOrganizationDomainConfig(),
      ])
      setDomains(items)
      setDomainConfig(config)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de charger les domaines.')
    }
  }

  useEffect(() => {
    if (!activeOrganization) return
    setName(activeOrganization.name)
    setContactEmail(activeOrganization.contact_email ?? '')
    setTimezone(activeOrganization.timezone)
    setLocale(activeOrganization.locale)
    setSubdomain(activeOrganization.subdomain ?? '')
    setMessage('')
    setError('')
  }, [activeOrganization?.id])

  useEffect(() => {
    if (!activeOrganization) return
    if (section === 'domains') {
      void loadDomains()
      return
    }

    getOrganizationPolicy()
      .then(setOrganizationPolicy)
      .catch(() => setOrganizationPolicy(null))
  }, [activeOrganization?.id, section])

  if (!activeOrganization) return <div className="page-state">Créez d’abord une école.</div>

  const cooldownDays = organizationPolicy?.name_change_cooldown_days ?? 30
  const nextNameChangeAt = activeOrganization.name_changed_at
    ? new Date(new Date(activeOrganization.name_changed_at).getTime() + cooldownDays * 24 * 60 * 60 * 1000)
    : null
  const nameChangeLocked = Boolean(nextNameChangeAt && nextNameChangeAt.getTime() > Date.now())
  const deletionDate = activeOrganization.deletion_scheduled_at
    ? new Intl.DateTimeFormat(activeSchoolLocale(), {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(activeOrganization.deletion_scheduled_at))
    : ''

  async function submitSchool(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setMessage('')
    setError('')
    try {
      await updateCurrentOrganization({
        name,
        contact_email: contactEmail || null,
        timezone,
        locale,
      })
      await refreshOrganizations()
      setMessage('Les informations de l’école ont été enregistrées.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Enregistrement impossible.')
    } finally {
      setSubmitting(false)
    }
  }

  async function scheduleSchoolDeletion() {
    if (!activeOrganization || deletionConfirmation.trim() !== activeOrganization.name) return
    setDeletionBusy(true)
    setDeletionError('')
    try {
      await requestOrganizationDeletion(deletionConfirmation)
      setDeletionConfirmation('')
      await refreshOrganizations()
    } catch (err) {
      setDeletionError(err instanceof ApiError ? err.message : 'Impossible de programmer la suppression.')
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
    } catch (err) {
      setDeletionError(err instanceof ApiError ? err.message : 'Impossible d’annuler la suppression.')
    } finally {
      setDeletionBusy(false)
    }
  }

  async function submitSubdomain(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setMessage('')
    setError('')
    try {
      await updateCurrentSubdomain(subdomain || null)
      await refreshOrganizations()
      setMessage('Le sous-domaine a été enregistré.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Enregistrement impossible.')
    } finally {
      setSubmitting(false)
    }
  }

  async function addDomain() {
    if (!newDomain.trim()) return
    setDomainLoading(true)
    setError('')
    setMessage('')
    try {
      await createOrganizationDomain(newDomain)
      setNewDomain('')
      await loadDomains()
      setMessage('Domaine ajouté. Configurez maintenant le TXT de vérification.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible d’ajouter ce domaine.')
    } finally {
      setDomainLoading(false)
    }
  }

  async function verifyDomain(domain: OrganizationDomain) {
    setDomainLoading(true)
    setError('')
    setMessage('')
    try {
      await verifyOrganizationDomain(domain.id)
      await loadDomains()
      setMessage('Domaine vérifié avec succès.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Vérification impossible.')
    } finally {
      setDomainLoading(false)
    }
  }

  if (section === 'school') {
    return (
      <div className="settings-stack identity-settings-form">
      <form className="settings-stack" onSubmit={submitSchool}>
        <section className="app-card settings-form">
          <div className="settings-section-heading">
            <div>
              <span className="section-label">Informations générales</span>
              <h2>Votre école</h2>
              <p>Ces informations identifient votre école dans les espaces de gestion.</p>
            </div>
          </div>
          <div className="settings-grid">
            <label>
              Nom de l’école
              <input value={name} onChange={(event) => setName(event.target.value)} required maxLength={180} disabled={nameChangeLocked} />
              <small className={nameChangeLocked ? 'name-change-lock' : 'settings-help'}>
                {nameChangeLocked && nextNameChangeAt
                  ? `Nom verrouillé jusqu’au ${new Intl.DateTimeFormat(activeSchoolLocale(), { day: '2-digit', month: 'long', year: 'numeric' }).format(nextNameChangeAt)}. Un changement est autorisé tous les ${cooldownDays} jours.`
                  : `Le propriétaire peut renommer l’école une fois tous les ${cooldownDays} jours.`}
              </small>
            </label>
            <label>
              Email de contact
              <input type="email" value={contactEmail} onChange={(event) => setContactEmail(event.target.value)} />
            </label>
            <label>
              Fuseau horaire
              <select value={timezone} onChange={(event) => setTimezone(event.target.value)}>
                {!popularTimezones.some((item) => item.value === timezone) && (
                  <option value={timezone}>{timezone} - fuseau actuel</option>
                )}
                {popularTimezones.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </label>
            <label>
              Langue / locale
              <select value={locale} onChange={(event) => {
                const nextLocale = event.target.value
                setLocale(nextLocale)
                setSchoolInterfaceLocale(nextLocale)
              }}>
                <option value="fr-FR">Français - France</option>
                <option value="fr-CM">Français - Cameroun</option>
                <option value="en-US">English - US</option>
              </select>
            </label>
          </div>
        </section>
        {message && <div className="form-success">{message}</div>}
        {error && <div className="form-error">{error}</div>}
        <div className="settings-actions">
          <button className="primary-button" disabled={submitting}>
            <Save size={17} />{submitting ? 'Enregistrement…' : 'Enregistrer les informations'}
          </button>
        </div>
      </form>
      {accessProfile?.roles.includes('owner') && (
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
      )}
      </div>
    )
  }

  return (
    <div className="settings-stack identity-settings-form">
      <form onSubmit={submitSubdomain}>
        <section className="app-card domain-settings-card">
          <div className="settings-section-heading">
            <div>
              <span className="section-label">Adresse de l’école</span>
              <h2>Sous-domaine</h2>
              <p>Choisissez l’adresse incluse avec votre école.</p>
            </div>
          </div>
          <div className="subdomain-field">
            <label>
              Sous-domaine
              <span className="subdomain-input">
                <input value={subdomain} onChange={(event) => setSubdomain(event.target.value.toLowerCase())} maxLength={63} pattern="^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$" placeholder="mon-ecole" />
                <span>{domainConfig?.base_domain ? `.${domainConfig.base_domain}` : '.votre-domaine-saas'}</span>
              </span>
            </label>
          </div>
          {message && <div className="form-success">{message}</div>}
          {error && <div className="form-error">{error}</div>}
          <div className="settings-actions">
            <button className="primary-button" disabled={submitting}>
              <Save size={17} />{submitting ? 'Enregistrement…' : 'Enregistrer le sous-domaine'}
            </button>
          </div>
        </section>
      </form>

      <section className="app-card domain-settings-card">
        <div className="settings-section-heading">
          <div>
            <span className="section-label">Adresse externe</span>
            <h2>Domaine personnalisé</h2>
            <p>Reliez un nom de domaine qui appartient à votre école.</p>
          </div>
        </div>
        <div className="custom-domain-add">
          <label>
            Domaine personnalisé
            <input value={newDomain} onChange={(event) => setNewDomain(event.target.value)} placeholder="formation.mondomaine.com" maxLength={253} />
          </label>
          <button className="secondary-button" type="button" onClick={() => void addDomain()} disabled={domainLoading || !newDomain.trim()}>
            <Globe2 size={16} />Ajouter
          </button>
        </div>
        <div className="domain-list">
          {domains.map((domain) => (
            <article className="domain-item" key={domain.id}>
              <div className="domain-main">
                <Globe2 size={17} />
                <div>
                  <strong>{domain.hostname}</strong>
                  <small>{domain.status === 'verified' ? 'Domaine vérifié' : 'Vérification DNS requise'}{domain.is_primary ? ' · Principal' : ''}</small>
                </div>
              </div>
              {domain.status !== 'verified' && (
                <div className="dns-instructions">
                  <span>TXT</span><code>_academie-verification.{domain.hostname}</code><code>{domain.verification_token}</code>
                  <button className="icon-button" type="button" title="Copier le token" onClick={() => void navigator.clipboard.writeText(domain.verification_token)}><Copy size={15} /></button>
                </div>
              )}
              <div className="domain-actions">
                {domain.status !== 'verified' ? (
                  <button className="secondary-button compact-action" type="button" onClick={() => void verifyDomain(domain)} disabled={domainLoading}><CheckCircle2 size={15} />Vérifier</button>
                ) : !domain.is_primary ? (
                  <button className="secondary-button compact-action" type="button" disabled={domainLoading} onClick={async () => { await setPrimaryOrganizationDomain(domain.id); await loadDomains() }}>Définir principal</button>
                ) : null}
                <button className="icon-button danger-icon" type="button" title="Supprimer" disabled={domainLoading} onClick={async () => { await deleteOrganizationDomain(domain.id); await loadDomains() }}><Trash2 size={16} /></button>
              </div>
            </article>
          ))}
          {domains.length === 0 && <div className="empty-row">Aucun domaine personnalisé.</div>}
        </div>
        {domainConfig?.cname_target && <div className="cname-note">Pour le trafic web, faites aussi pointer votre CNAME vers <code>{domainConfig.cname_target}</code>.</div>}
        {message && <div className="form-success">{message}</div>}
        {error && <div className="form-error">{error}</div>}
      </section>
    </div>
  )
}
