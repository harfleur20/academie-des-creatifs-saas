import { useEffect, useState, type FormEvent } from 'react'
import { Save } from 'lucide-react'
import { useTenant } from '../app/TenantContext'
import { ApiError, updateCurrentOrganization } from '../lib/api'

export function SchoolSettingsPage() {
  const { activeOrganization, refreshOrganizations } = useTenant()
  const [name, setName] = useState('')
  const [contactEmail, setContactEmail] = useState('')
  const [timezone, setTimezone] = useState('UTC')
  const [locale, setLocale] = useState('fr-FR')
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!activeOrganization) return
    setName(activeOrganization.name)
    setContactEmail(activeOrganization.contact_email ?? '')
    setTimezone(activeOrganization.timezone)
    setLocale(activeOrganization.locale)
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
      })
      await refreshOrganizations()
      setMessage('Paramètres enregistrés.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Enregistrement impossible.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="app-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Paramètres</span>
          <h1>Informations de l’école</h1>
          <p>Ces informations seront utilisées dans les différents espaces de votre école.</p>
        </div>
      </header>

      <form className="app-card settings-form" onSubmit={submit}>
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
