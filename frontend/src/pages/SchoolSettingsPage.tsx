import { useEffect, useState, type CSSProperties, type FormEvent } from 'react'
import { CheckCircle2, Copy, Globe2, Palette, RotateCcw, Save, Trash2 } from 'lucide-react'
import { useTenant } from '../app/TenantContext'
import { SchoolLogo } from '../brand/SchoolLogo'
import { DEFAULT_BRAND_COLORS } from '../brand/branding'
import {
  ApiError,
  createOrganizationDomain,
  deleteOrganizationDomain,
  getOrganizationDomainConfig,
  getOrganizationPolicy,
  listOrganizationDomains,
  setPrimaryOrganizationDomain,
  updateCurrentOrganization,
  updateCurrentSubdomain,
  verifyOrganizationDomain,
  type OrganizationDomain,
  type OrganizationDomainConfig,
  type OrganizationPolicy,
} from '../lib/api'

export function SchoolSettingsPage() {
  const { activeOrganization, refreshOrganizations } = useTenant()
  const [name, setName] = useState('')
  const [contactEmail, setContactEmail] = useState('')
  const [timezone, setTimezone] = useState('UTC')
  const [locale, setLocale] = useState('fr-FR')
  const [logoUrl, setLogoUrl] = useState('')
  const [primaryColor, setPrimaryColor] = useState(DEFAULT_BRAND_COLORS.primary)
  const [secondaryColor, setSecondaryColor] = useState(DEFAULT_BRAND_COLORS.secondary)
  const [accentColor, setAccentColor] = useState(DEFAULT_BRAND_COLORS.accent)
  const [subdomain, setSubdomain] = useState('')
  const [domains, setDomains] = useState<OrganizationDomain[]>([])
  const [domainConfig, setDomainConfig] = useState<OrganizationDomainConfig | null>(null)
  const [organizationPolicy, setOrganizationPolicy] = useState<OrganizationPolicy | null>(null)
  const [newDomain, setNewDomain] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [domainLoading, setDomainLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function loadDomains() {
    if (!activeOrganization) return
    try {
      const [items, config, policy] = await Promise.all([
        listOrganizationDomains(),
        getOrganizationDomainConfig(),
        getOrganizationPolicy(),
      ])
      setDomains(items)
      setDomainConfig(config)
      setOrganizationPolicy(policy)
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
    setLogoUrl(activeOrganization.logo_url ?? '')
    setPrimaryColor(activeOrganization.primary_color || DEFAULT_BRAND_COLORS.primary)
    setSecondaryColor(activeOrganization.secondary_color || DEFAULT_BRAND_COLORS.secondary)
    setAccentColor(activeOrganization.accent_color || DEFAULT_BRAND_COLORS.accent)
    setSubdomain(activeOrganization.subdomain ?? '')
    void loadDomains()
  }, [activeOrganization?.id])

  if (!activeOrganization) {
    return <div className="page-state">Créez d’abord une école.</div>
  }

  const cooldownDays = organizationPolicy?.name_change_cooldown_days ?? 30
  const nextNameChangeAt = activeOrganization.name_changed_at
    ? new Date(
        new Date(activeOrganization.name_changed_at).getTime()
          + cooldownDays * 24 * 60 * 60 * 1000,
      )
    : null
  const nameChangeLocked = Boolean(
    nextNameChangeAt && nextNameChangeAt.getTime() > Date.now(),
  )

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setMessage('')
    setError('')
    try {
      await Promise.all([
        updateCurrentOrganization({
          name,
          contact_email: contactEmail || null,
          timezone,
          locale,
          logo_url: logoUrl || null,
          primary_color: primaryColor,
          secondary_color: secondaryColor,
          accent_color: accentColor,
        }),
        updateCurrentSubdomain(subdomain || null),
      ])
      await refreshOrganizations()
      setMessage('Paramètres, identité et sous-domaine enregistrés.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Enregistrement impossible.')
    } finally {
      setSubmitting(false)
    }
  }

  function resetBranding() {
    setLogoUrl('')
    setPrimaryColor(DEFAULT_BRAND_COLORS.primary)
    setSecondaryColor(DEFAULT_BRAND_COLORS.secondary)
    setAccentColor(DEFAULT_BRAND_COLORS.accent)
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

  return (
    <main className="app-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Paramètres</span>
          <h1>Informations & identité de l’école</h1>
          <p>Personnalisez l’apparence et les adresses utilisées par votre école.</p>
        </div>
      </header>

      <form className="settings-stack" onSubmit={submit}>
        <section className="app-card settings-form">
          <div className="settings-section-heading">
            <div>
              <span className="section-label">École</span>
              <h2>Informations générales</h2>
            </div>
          </div>

          <div className="settings-grid">
            <label>
              Nom de l’école
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                maxLength={180}
                disabled={nameChangeLocked}
              />
              <small className={nameChangeLocked ? 'name-change-lock' : 'settings-help'}>
                {nameChangeLocked && nextNameChangeAt
                  ? `Nom verrouillé jusqu’au ${new Intl.DateTimeFormat('fr-FR', {
                      day: '2-digit',
                      month: 'long',
                      year: 'numeric',
                    }).format(nextNameChangeAt)}. Un changement est autorisé tous les ${cooldownDays} jours.`
                  : `Le propriétaire peut renommer l’école une fois tous les ${cooldownDays} jours.`}
              </small>
            </label>
            <label>
              Email de contact
              <input type="email" value={contactEmail} onChange={(event) => setContactEmail(event.target.value)} />
            </label>
            <label>
              Fuseau horaire
              <input value={timezone} onChange={(event) => setTimezone(event.target.value)} placeholder="Europe/Paris" />
            </label>
            <label>
              Langue / locale
              <select value={locale} onChange={(event) => setLocale(event.target.value)}>
                <option value="fr-FR">Français — France</option>
                <option value="fr-CM">Français — Cameroun</option>
                <option value="en-US">English — US</option>
              </select>
            </label>
          </div>
        </section>

        <section className="app-card branding-settings-card">
          <div className="settings-section-heading">
            <div>
              <span className="section-label">White-label</span>
              <h2>Identité visuelle</h2>
              <p>Votre logo et vos couleurs sont appliqués automatiquement dans l’espace école.</p>
            </div>
            <button className="secondary-button compact-action" type="button" onClick={resetBranding}>
              <RotateCcw size={15} />
              Réinitialiser
            </button>
          </div>

          <div className="branding-settings-grid">
            <div className="branding-controls">
              <label>
                URL du logo
                <input
                  type="url"
                  value={logoUrl}
                  onChange={(event) => setLogoUrl(event.target.value)}
                  maxLength={500}
                  placeholder="https://.../logo.png"
                />
                <small>Laissez vide pour utiliser le logo icône de l’Académie des Créatifs.</small>
              </label>

              <div className="brand-color-grid">
                <label>
                  Couleur principale
                  <span className="color-field">
                    <input type="color" value={primaryColor} onChange={(event) => setPrimaryColor(event.target.value.toUpperCase())} />
                    <input value={primaryColor} onChange={(event) => setPrimaryColor(event.target.value.toUpperCase())} pattern="^#[0-9A-Fa-f]{6}$" />
                  </span>
                </label>
                <label>
                  Couleur secondaire
                  <span className="color-field">
                    <input type="color" value={secondaryColor} onChange={(event) => setSecondaryColor(event.target.value.toUpperCase())} />
                    <input value={secondaryColor} onChange={(event) => setSecondaryColor(event.target.value.toUpperCase())} pattern="^#[0-9A-Fa-f]{6}$" />
                  </span>
                </label>
                <label>
                  Couleur d’accent
                  <span className="color-field">
                    <input type="color" value={accentColor} onChange={(event) => setAccentColor(event.target.value.toUpperCase())} />
                    <input value={accentColor} onChange={(event) => setAccentColor(event.target.value.toUpperCase())} pattern="^#[0-9A-Fa-f]{6}$" />
                  </span>
                </label>
              </div>
            </div>

            <div
              className="brand-preview"
              style={{
                '--preview-primary': primaryColor,
                '--preview-secondary': secondaryColor,
                '--preview-accent': accentColor,
              } as CSSProperties}
            >
              <div className="brand-preview-sidebar">
                <SchoolLogo logoUrl={logoUrl} alt={name} />
              </div>
              <div className="brand-preview-body">
                <span className="brand-preview-chip"><Palette size={13} /> Aperçu</span>
                <SchoolLogo logoUrl={logoUrl} alt={name} className="brand-preview-logo" />
                <strong>{name || 'Votre école'}</strong>
                <small>Votre espace, votre identité.</small>
                <button type="button">Bouton principal</button>
              </div>
            </div>
          </div>
        </section>

        <section className="app-card domain-settings-card">
          <div className="settings-section-heading">
            <div>
              <span className="section-label">Adresses</span>
              <h2>Sous-domaine & domaine personnalisé</h2>
              <p>Donnez à votre école une adresse propre et reconnaissable.</p>
            </div>
          </div>

          <div className="subdomain-field">
            <label>
              Sous-domaine SaaS
              <span className="subdomain-input">
                <input
                  value={subdomain}
                  onChange={(event) => setSubdomain(event.target.value.toLowerCase())}
                  maxLength={63}
                  pattern="^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
                  placeholder="mon-ecole"
                />
                <span>
                  {domainConfig?.base_domain ? `.${domainConfig.base_domain}` : '.votre-domaine-saas'}
                </span>
              </span>
            </label>
          </div>

          <div className="custom-domain-add">
            <label>
              Domaine personnalisé
              <input
                value={newDomain}
                onChange={(event) => setNewDomain(event.target.value)}
                placeholder="formation.mondomaine.com"
                maxLength={253}
              />
            </label>
            <button
              className="secondary-button"
              type="button"
              onClick={() => void addDomain()}
              disabled={domainLoading || !newDomain.trim()}
            >
              <Globe2 size={16} />
              Ajouter
            </button>
          </div>

          <div className="domain-list">
            {domains.map((domain) => (
              <article className="domain-item" key={domain.id}>
                <div className="domain-main">
                  <Globe2 size={17} />
                  <div>
                    <strong>{domain.hostname}</strong>
                    <small>
                      {domain.status === 'verified'
                        ? 'Domaine vérifié'
                        : 'Vérification DNS requise'}
                      {domain.is_primary ? ' · Principal' : ''}
                    </small>
                  </div>
                </div>

                {domain.status !== 'verified' && (
                  <div className="dns-instructions">
                    <span>TXT</span>
                    <code>_academie-verification.{domain.hostname}</code>
                    <code>{domain.verification_token}</code>
                    <button
                      type="button"
                      className="icon-button"
                      title="Copier le token"
                      onClick={() => void navigator.clipboard.writeText(domain.verification_token)}
                    >
                      <Copy size={15} />
                    </button>
                  </div>
                )}

                <div className="domain-actions">
                  {domain.status !== 'verified' ? (
                    <button
                      type="button"
                      className="secondary-button compact-action"
                      onClick={() => void verifyDomain(domain)}
                      disabled={domainLoading}
                    >
                      <CheckCircle2 size={15} />
                      Vérifier
                    </button>
                  ) : !domain.is_primary ? (
                    <button
                      type="button"
                      className="secondary-button compact-action"
                      onClick={async () => {
                        await setPrimaryOrganizationDomain(domain.id)
                        await loadDomains()
                      }}
                    >
                      Définir principal
                    </button>
                  ) : null}

                  <button
                    type="button"
                    className="icon-button danger-icon"
                    title="Supprimer"
                    onClick={async () => {
                      await deleteOrganizationDomain(domain.id)
                      await loadDomains()
                    }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </article>
            ))}
            {domains.length === 0 && (
              <div className="empty-row">Aucun domaine personnalisé.</div>
            )}
          </div>

          {domainConfig?.cname_target && (
            <div className="cname-note">
              Pour le trafic web, faites aussi pointer votre CNAME vers <code>{domainConfig.cname_target}</code>.
            </div>
          )}
        </section>

        {message && <div className="form-success">{message}</div>}
        {error && <div className="form-error">{error}</div>}

        <div className="settings-actions">
          <button className="primary-button" disabled={submitting}>
            <Save size={17} />
            {submitting ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      </form>
    </main>
  )
}
