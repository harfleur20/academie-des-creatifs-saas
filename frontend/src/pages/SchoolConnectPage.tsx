import { useEffect, useState } from 'react'
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  KeyRound,
  LoaderCircle,
  Plug,
  RefreshCw,
  Sparkles,
  Unplug,
  X,
} from 'lucide-react'
import {
  connectOpenAI,
  disconnectOpenAI,
  getOpenAIIntegration,
  testOpenAIIntegration,
  type OpenAIIntegrationStatus,
} from '../lib/tenantIntegrationApi'
import {
  getIntegrationBadgePreferences,
  type IntegrationBadgePreference,
} from '../lib/api'
import '../reports-connect.css'
import '../connect-openai.css'

type Integration = {
  provider: string
  name: string
  category: string
  description: string
  benefit: string
  logoUrls: string[]
  logoLabels: string[]
  available: boolean
  availableBadge: 'connect' | 'recommended'
}

const OPENAI_MODELS = [
  { id: 'gpt-6-luna', label: 'GPT-6 Luna — Rapide et économique' },
  { id: 'gpt-6.1-terra', label: 'GPT-6.1 Terra — Rapide et polyvalent' },
  { id: 'gpt-6.1-sol', label: 'GPT-6.1 Sol — Équilibre performance / coût' },
  { id: 'gpt-6-astra', label: 'GPT-6 Astra — Le plus puissant' },
] as const

const integrations: Integration[] = [
  {
    provider: 'claude',
    name: 'Claude',
    category: 'Intelligence artificielle',
    description: 'Préparer des contenus pédagogiques avec les modèles Claude d’Anthropic.',
    benefit: 'Choisir un modèle adapté à la rédaction, à l’analyse ou aux tâches plus complexes.',
    logoUrls: ['/integrations/claude-anthropic.svg'],
    logoLabels: ['Anthropic'],
    available: false,
    availableBadge: 'connect',
  },
  {
    provider: 'imara',
    name: 'Imara',
    category: 'Intelligence artificielle',
    description: 'Relier les modèles Imara de Consolidis aux outils pédagogiques de l’école.',
    benefit: 'Explorer Imara, Zuri et Flash pour l’assistance, l’analyse et les réponses rapides.',
    logoUrls: ['/integrations/imara-icon-192.png'],
    logoLabels: ['Imara by Consolidis'],
    available: false,
    availableBadge: 'connect',
  },
  {
    provider: 'google_analytics',
    name: 'Google Analytics 4',
    category: 'Analytics',
    description: 'Mesurer le trafic du site public, les pages consultées et les conversions.',
    benefit: 'Comprendre d’où viennent les visiteurs et quelles formations intéressent le plus.',
    logoUrls: ['https://cdn.simpleicons.org/googleanalytics/E37400'],
    logoLabels: ['Google Analytics'],
    available: false,
    availableBadge: 'recommended',
  },
  {
    provider: 'search_console',
    name: 'Google Search Console',
    category: 'SEO',
    description: 'Suivre l’indexation du site, les recherches Google et les erreurs SEO.',
    benefit: 'Améliorer la visibilité naturelle de l’école et de ses formations.',
    logoUrls: ['https://cdn.simpleicons.org/googlesearchconsole/458CF5'],
    logoLabels: ['Google Search Console'],
    available: false,
    availableBadge: 'recommended',
  },
  {
    provider: 'meta_pixel',
    name: 'Meta Pixel',
    category: 'Acquisition',
    description: 'Mesurer les visites et conversions issues de Facebook et Instagram.',
    benefit: 'Mieux piloter les campagnes publicitaires et le retargeting.',
    logoUrls: ['https://cdn.simpleicons.org/meta/0866FF'],
    logoLabels: ['Meta'],
    available: false,
    availableBadge: 'recommended',
  },
  {
    provider: 'brevo',
    name: 'Brevo',
    category: 'Email',
    description: 'Synchroniser les contacts et automatiser les campagnes email.',
    benefit: 'Relancer les prospects, informer les apprenants et suivre les campagnes.',
    logoUrls: ['https://cdn.simpleicons.org/brevo/0B996E'],
    logoLabels: ['Brevo'],
    available: false,
    availableBadge: 'recommended',
  },
  {
    provider: 'whatsapp',
    name: 'WhatsApp / Wapino',
    category: 'Communication',
    description: 'Envoyer des rappels, confirmations et notifications WhatsApp via votre passerelle de communication.',
    benefit: 'Réduire les oublis et centraliser les communications importantes.',
    logoUrls: ['https://cdn.simpleicons.org/whatsapp/25D366'],
    logoLabels: ['WhatsApp / Wapino'],
    available: false,
    availableBadge: 'recommended',
  },
  {
    provider: 'google_calendar',
    name: 'Google Calendar & Meet',
    category: 'Planning',
    description: 'Synchroniser les séances et faciliter l’accès aux rendez-vous en ligne.',
    benefit: 'Éviter les doubles saisies et garder les calendriers à jour.',
    logoUrls: [
      'https://cdn.simpleicons.org/googlecalendar/4285F4',
      'https://cdn.simpleicons.org/googlemeet/00897B',
    ],
    logoLabels: ['Google Calendar', 'Google Meet'],
    available: false,
    availableBadge: 'connect',
  },
  {
    provider: 'make_zapier',
    name: 'Make / Zapier',
    category: 'Automatisation',
    description: 'Déclencher des automatisations vers d’autres outils métier.',
    benefit: 'Connecter CRM, formulaires, tableaux de suivi ou outils internes sans recoder chaque workflow.',
    logoUrls: [
      'https://cdn.simpleicons.org/make/6D00CC',
      'https://cdn.simpleicons.org/zapier/FF4F00',
    ],
    logoLabels: ['Make', 'Zapier'],
    available: false,
    availableBadge: 'connect',
  },
]

const CONNECT_PAGE_SIZE = 8
const CONNECT_PROVIDER_ORDER = ['openai', ...integrations.map((integration) => integration.provider)]

export function SchoolConnectPage() {
  const [openAI, setOpenAI] = useState<OpenAIIntegrationStatus | null>(null)
  const [badgePreferences, setBadgePreferences] = useState<IntegrationBadgePreference[]>([])
  const [integrationPage, setIntegrationPage] = useState(0)
  const [openModal, setOpenModal] = useState(false)
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('gpt-6-luna')
  const [working, setWorking] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    getOpenAIIntegration()
      .then((status) => {
        if (!active) return
        setOpenAI(status)
        if (status.model) setModel(status.model)
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : 'État OpenAI indisponible.')
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    getIntegrationBadgePreferences()
      .then(setBadgePreferences)
      .catch(() => setBadgePreferences([]))
  }, [])

  async function connect() {
    if (!apiKey.trim()) return
    setWorking(true)
    setError('')
    setMessage('')
    try {
      const status = await connectOpenAI(apiKey.trim(), model.trim() || 'gpt-6-luna')
      setOpenAI(status)
      setApiKey('')
      setOpenModal(false)
      setMessage('OpenAI est connecté. Les outils IA sont maintenant disponibles aux professeurs de cette école.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Connexion OpenAI impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function testConnection() {
    setWorking(true)
    setError('')
    setMessage('')
    try {
      const status = await testOpenAIIntegration()
      setOpenAI(status)
      setMessage('Connexion OpenAI vérifiée avec succès.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Test OpenAI impossible.')
      void getOpenAIIntegration().then(setOpenAI).catch(() => undefined)
    } finally {
      setWorking(false)
    }
  }

  async function disconnect() {
    if (!window.confirm('Déconnecter OpenAI ? Les professeurs ne pourront plus utiliser la génération IA.')) return
    setWorking(true)
    setError('')
    setMessage('')
    try {
      await disconnectOpenAI()
      setOpenAI({
        provider: 'openai',
        connected: false,
        status: 'disconnected',
        model: null,
        connected_at: null,
        last_tested_at: null,
        last_error: null,
      })
      setMessage('OpenAI a été déconnecté de cette école.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Déconnexion impossible.')
    } finally {
      setWorking(false)
    }
  }

  const connected = openAI?.connected === true
  const openAIBadgeMode = badgePreferences.find((item) => item.provider === 'openai')?.badge_mode ?? 'connect'
  const statusLabel = connected
    ? 'Connecté'
    : openAIBadgeMode === 'recommended' ? 'Recommandé' : 'À connecter'
  const openAIBadgeClass = connected
    ? 'is-connected'
    : openAIBadgeMode === 'recommended' ? 'recommended' : 'is-connectable'
  const pageCount = Math.ceil(CONNECT_PROVIDER_ORDER.length / CONNECT_PAGE_SIZE)
  const visibleProviders = CONNECT_PROVIDER_ORDER.slice(
    integrationPage * CONNECT_PAGE_SIZE,
    (integrationPage + 1) * CONNECT_PAGE_SIZE,
  )
  const visibleProviderSet = new Set(visibleProviders)

  return (
    <main className="app-page school-connect-page">
      <header className="app-page-header connect-page-header">
        <div>
          <span className="page-kicker">Écosystème de l’école</span>
          <h1>Connect</h1>
          <p>Reliez progressivement vos outils externes pour mieux mesurer, communiquer, automatiser et piloter votre école.</p>
        </div>
        <span className="connect-header-icon"><Plug size={24} /></span>
      </header>

      {error && <div className="form-error">{error}</div>}
      {message && <div className="openai-connect-success"><CheckCircle2 size={16} /> {message}</div>}

      <section className="app-card connect-intro-card">
        <div>
          <span className="section-label">Centre d’intégrations</span>
          <h2>Un seul endroit pour vos connexions</h2>
          <p>OpenAI est déjà disponible pour les outils pédagogiques. Les autres connecteurs seront activés au fur et à mesure de leur branchement réel via API ou OAuth.</p>
        </div>
        <div className="connect-priority-legend">
          <span><i className="is-connectable" /> À connecter</span>
          <span><i className="is-recommended" /> Recommandé</span>
          <span><i className="is-planned" /> À venir</span>
          <span><i className="is-connected" /> Connecté</span>
        </div>
      </section>

      <section className="connect-grid">
        {visibleProviderSet.has('openai') && <article className="app-card connect-card openai-connect-card">
          <div className="connect-card-head">
            <span className="connect-brand-logos" aria-label="OpenAI">
              <span className="connect-brand-logo openai-brand-logo" title="OpenAI">
                <img
                  src="/integrations/openai-blossom.svg"
                  alt="OpenAI"
                  onError={(event) => { event.currentTarget.style.display = 'none' }}
                />
              </span>
            </span>
            <span className={`connect-status ${openAIBadgeClass}`}>
              {statusLabel}
            </span>
          </div>

          <div className="connect-card-copy">
            <small>Intelligence artificielle</small>
            <h2>OpenAI</h2>
            <p>Active la conception assistée de cours, devoirs et quiz dans l’espace professeur.</p>
          </div>

          <div className="connect-benefit">
            <strong>Pourquoi le connecter ?</strong>
            <span>L’école utilise sa propre clé API et garde la maîtrise de sa consommation OpenAI.</span>
          </div>

          {connected ? (
            <div className="openai-connected-details">
              <div><Sparkles size={15} /><span>Modèle</span><strong>{openAI?.model || 'gpt-6-luna'}</strong></div>
              <small>La clé API est chiffrée côté serveur et n’est jamais réaffichée.</small>
              {openAI?.last_error && <small className="openai-last-error">{openAI.last_error}</small>}
              <div className="openai-connect-actions">
                <button className="secondary-button" type="button" disabled={working} onClick={() => void testConnection()}>
                  {working ? <LoaderCircle className="openai-spin" size={15} /> : <RefreshCw size={15} />} Tester
                </button>
                <button className="secondary-button openai-disconnect-button" type="button" disabled={working} onClick={() => void disconnect()}>
                  <Unplug size={15} /> Déconnecter
                </button>
              </div>
            </div>
          ) : (
            <button className="primary-button openai-connect-button" type="button" onClick={() => setOpenModal(true)}>
              <KeyRound size={15} /> Connecter OpenAI
            </button>
          )}
        </article>}

        {integrations.filter((integration) => visibleProviderSet.has(integration.provider)).map((integration) => {
          const preference = badgePreferences.find((item) => item.provider === integration.provider)
          const isConnected = preference?.connected === true
          const badgeMode = preference?.badge_mode ?? integration.availableBadge
          const badgeClass = isConnected
            ? 'is-connected'
            : integration.available
              ? badgeMode === 'recommended' ? 'recommended' : 'is-connectable'
              : 'planned'
          const badgeLabel = isConnected
            ? 'Connecté'
            : integration.available
              ? badgeMode === 'recommended' ? 'Recommandé' : 'À connecter'
              : 'À venir'

          return (
            <article className="app-card connect-card" key={integration.name}>
              <div className="connect-card-head">
                <span className="connect-brand-logos" aria-label={integration.logoLabels.join(' et ')}>
                  {integration.logoUrls.map((logoUrl, index) => (
                    <span className="connect-brand-logo" key={logoUrl} title={integration.logoLabels[index]}>
                      <img
                        src={logoUrl}
                        alt={integration.logoLabels[index]}
                        loading="lazy"
                        onError={(event) => { event.currentTarget.style.display = 'none' }}
                      />
                    </span>
                  ))}
                </span>
                <span className={`connect-status ${badgeClass}`}>
                  {badgeLabel}
                </span>
              </div>
              <div className="connect-card-copy">
                <small>{integration.category}</small>
                <h2>{integration.name}</h2>
                <p>{integration.description}</p>
              </div>
              <div className="connect-benefit">
                <strong>Pourquoi le connecter ?</strong>
                <span>{integration.benefit}</span>
              </div>
              <button className="secondary-button connect-disabled-action" type="button" disabled={!integration.available || isConnected}>
                {isConnected ? 'Connecté' : integration.available ? 'Connecter' : 'Bientôt disponible'}
              </button>
            </article>
          )
        })}
      </section>

      {pageCount > 1 && (
        <nav className="connect-pagination" aria-label="Pagination des intégrations">
          <button
            className="secondary-button"
            type="button"
            disabled={integrationPage === 0}
            onClick={() => setIntegrationPage((page) => Math.max(0, page - 1))}
          >
            <ChevronLeft size={18} /> Précédent
          </button>
          <span>Page {integrationPage + 1} sur {pageCount}</span>
          <button
            className="secondary-button"
            type="button"
            disabled={integrationPage >= pageCount - 1}
            onClick={() => setIntegrationPage((page) => Math.min(pageCount - 1, page + 1))}
          >
            Suivant <ChevronRight size={18} />
          </button>
        </nav>
      )}

      {openModal && (
        <div className="openai-modal-overlay" onClick={() => !working && setOpenModal(false)}>
          <div className="openai-modal" onClick={(event) => event.stopPropagation()}>
            <header>
              <div>
                <span className="section-label">Connect · OpenAI</span>
                <h2>Activer l’IA pédagogique</h2>
                <p>La clé est testée avant enregistrement, puis chiffrée côté serveur.</p>
              </div>
              <button type="button" disabled={working} onClick={() => setOpenModal(false)} aria-label="Fermer"><X size={18} /></button>
            </header>

            <label>
              Clé API OpenAI
              <input
                type="password"
                value={apiKey}
                autoComplete="off"
                placeholder="sk-…"
                onChange={(event) => setApiKey(event.target.value)}
              />
              <small>Elle ne sera plus affichée après l’enregistrement.</small>
            </label>

            <label>
              Modèle utilisé pour les brouillons pédagogiques
              <select
                value={model}
                onChange={(event) => setModel(event.target.value)}
              >
                {!OPENAI_MODELS.some((option) => option.id === model) && (
                  <option value={model}>Modèle actuellement enregistré — {model}</option>
                )}
                {OPENAI_MODELS.map((option) => (
                  <option key={option.id} value={option.id}>{option.label}</option>
                ))}
              </select>
            </label>

            <div className="openai-modal-note">
              <Sparkles size={17} />
              <span>Les générations produisent toujours un brouillon : le professeur garde la validation finale avant publication.</span>
            </div>

            <footer>
              <button className="secondary-button" type="button" disabled={working} onClick={() => setOpenModal(false)}>Annuler</button>
              <button className="primary-button" type="button" disabled={working || apiKey.trim().length < 20} onClick={() => void connect()}>
                {working ? <LoaderCircle className="openai-spin" size={15} /> : <KeyRound size={15} />}
                {working ? 'Vérification…' : 'Tester et connecter'}
              </button>
            </footer>
          </div>
        </div>
      )}
    </main>
  )
}
