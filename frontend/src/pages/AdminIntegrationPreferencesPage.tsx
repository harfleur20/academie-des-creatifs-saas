import { useEffect, useState } from 'react'
import { CheckCircle2, Plug, Save } from 'lucide-react'
import {
  ApiError,
  listAdminIntegrationBadgePreferences,
  updateAdminIntegrationBadgePreference,
  type IntegrationBadgePreference,
} from '../lib/api'
import '../admin-integration-preferences.css'

const integrationLabels: Record<string, { name: string; detail: string }> = {
  openai: { name: 'OpenAI', detail: 'Outils IA pour les professeurs' },
  claude: { name: 'Claude', detail: 'Modèles d’intelligence artificielle Anthropic' },
  imara: { name: 'Imara', detail: 'Modèles Imara, Zuri et Flash de Consolidis' },
  google_analytics: { name: 'Google Analytics 4', detail: 'Mesure du trafic et des conversions' },
  search_console: { name: 'Google Search Console', detail: 'Indexation et visibilité SEO' },
  meta_pixel: { name: 'Meta Pixel', detail: 'Suivi des campagnes Facebook et Instagram' },
  brevo: { name: 'Brevo', detail: 'Emails et campagnes' },
  whatsapp: { name: 'WhatsApp / Wapino', detail: 'Notifications et communications' },
  google_calendar: { name: 'Google Calendar & Meet', detail: 'Calendriers et classes en ligne' },
  make_zapier: { name: 'Make / Zapier', detail: 'Automatisations externes' },
}

export function AdminIntegrationPreferencesPage() {
  const [preferences, setPreferences] = useState<IntegrationBadgePreference[]>([])
  const [drafts, setDrafts] = useState<Record<string, IntegrationBadgePreference['badge_mode']>>({})
  const [saving, setSaving] = useState('')
  const [saved, setSaved] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    listAdminIntegrationBadgePreferences()
      .then((items) => {
        setPreferences(items)
        setDrafts(Object.fromEntries(items.map((item) => [item.provider, item.badge_mode])))
      })
      .catch((cause) => setError(cause instanceof ApiError ? cause.message : 'Impossible de charger les préférences.'))
  }, [])

  async function save(provider: string) {
    const badgeMode = drafts[provider]
    if (!badgeMode) return
    setSaving(provider)
    setSaved('')
    setError('')
    try {
      const updated = await updateAdminIntegrationBadgePreference(provider, badgeMode)
      setPreferences((current) => current.map((item) => item.provider === provider ? updated : item))
      setSaved(provider)
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Enregistrement impossible.')
    } finally {
      setSaving('')
    }
  }

  return (
    <main className="admin-page">
      <header className="admin-page-header">
        <div>
          <span className="page-kicker">Super-admin</span>
          <h1>Badges des intégrations</h1>
          <p>Choisissez le badge affiché lorsqu’une intégration est disponible pour les écoles.</p>
        </div>
        <Plug size={24} aria-hidden="true" />
      </header>

      {error && <div className="form-error">{error}</div>}

      <section className="admin-card admin-integration-preferences">
        <p className="admin-integration-preferences__help">
          « À venir » s’affiche tant que le bouton indique « Bientôt disponible ». Une connexion réussie affiche toujours « Connecté ».
        </p>
        <div className="admin-integration-preferences__list">
          {preferences.map((item) => {
            const info = integrationLabels[item.provider] || { name: item.provider, detail: '' }
            const savedMode = preferences.find((savedItem) => savedItem.provider === item.provider)?.badge_mode
            const hasChanges = savedMode !== drafts[item.provider]
            return (
              <article className="admin-integration-preference" key={item.provider}>
                <div>
                  <strong>{info.name}</strong>
                  <small>{info.detail}</small>
                </div>
                <label>
                  Badge à la disponibilité
                  <select
                    value={drafts[item.provider] || item.badge_mode}
                    onChange={(event) => {
                      setDrafts((current) => ({ ...current, [item.provider]: event.target.value as IntegrationBadgePreference['badge_mode'] }))
                      setSaved('')
                    }}
                  >
                    <option value="connect">À connecter</option>
                    <option value="recommended">Recommandé</option>
                  </select>
                </label>
                <button
                  className="secondary-button"
                  type="button"
                  disabled={saving === item.provider || !hasChanges}
                  onClick={() => void save(item.provider)}
                >
                  <Save size={16} />
                  {saving === item.provider
                    ? 'Enregistrement…'
                    : saved === item.provider
                      ? <><CheckCircle2 size={15} /> Enregistré</>
                      : 'Enregistrer'}
                </button>
              </article>
            )
          })}
        </div>
      </section>
    </main>
  )
}
