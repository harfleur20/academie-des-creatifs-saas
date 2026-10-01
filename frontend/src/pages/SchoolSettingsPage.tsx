import { useEffect, useState, type FormEvent } from 'react'
import { Palette, RotateCcw, Save } from 'lucide-react'
import { useTenant } from '../app/TenantContext'
import { BrandLogo } from '../brand/BrandLogo'
import { DEFAULT_BRAND_COLORS, resolveBrandLogo } from '../brand/branding'
import { ApiError, updateCurrentOrganization } from '../lib/api'

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
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

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
  }, [activeOrganization?.id])

  if (!activeOrganization) {
    return <div className="page-state">Créez d’abord une école.</div>
  }

  async function submit(event: FormEvent) {
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
        logo_url: logoUrl || null,
        primary_color: primaryColor,
        secondary_color: secondaryColor,
        accent_color: accentColor,
      })
      await refreshOrganizations()
      setMessage('Paramètres et identité visuelle enregistrés.')
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

  return (
    <main className="app-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Paramètres</span>
          <h1>Informations & identité de l’école</h1>
          <p>Personnalisez les informations et l’apparence de votre espace.</p>
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
              <input value={name} onChange={(event) => setName(event.target.value)} required maxLength={180} />
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
              } as React.CSSProperties}
            >
              <div className="brand-preview-sidebar">
                <BrandLogo logoUrl={resolveBrandLogo(logoUrl)} alt={name} />
              </div>
              <div className="brand-preview-body">
                <span className="brand-preview-chip"><Palette size={13} /> Aperçu</span>
                <BrandLogo logoUrl={resolveBrandLogo(logoUrl)} alt={name} className="brand-preview-logo" />
                <strong>{name || 'Votre école'}</strong>
                <small>Votre espace, votre identité.</small>
                <button type="button">Bouton principal</button>
              </div>
            </div>
          </div>
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
