import { Plug } from 'lucide-react'
import '../reports-connect.css'

type Integration = {
  name: string
  category: string
  description: string
  benefit: string
  logoUrls: string[]
  logoLabels: string[]
  priority: 'recommended' | 'planned'
}

const integrations: Integration[] = [
  {
    name: 'Google Analytics 4',
    category: 'Analytics',
    description: 'Mesurer le trafic du site public, les pages consultées et les conversions.',
    benefit: 'Comprendre d’où viennent les visiteurs et quelles formations intéressent le plus.',
    logoUrls: ['https://cdn.simpleicons.org/googleanalytics/E37400'],
    logoLabels: ['Google Analytics'],
    priority: 'recommended',
  },
  {
    name: 'Google Search Console',
    category: 'SEO',
    description: 'Suivre l’indexation du site, les recherches Google et les erreurs SEO.',
    benefit: 'Améliorer la visibilité naturelle de l’école et de ses formations.',
    logoUrls: ['https://cdn.simpleicons.org/googlesearchconsole/458CF5'],
    logoLabels: ['Google Search Console'],
    priority: 'recommended',
  },
  {
    name: 'Meta Pixel',
    category: 'Acquisition',
    description: 'Mesurer les visites et conversions issues de Facebook et Instagram.',
    benefit: 'Mieux piloter les campagnes publicitaires et le retargeting.',
    logoUrls: ['https://cdn.simpleicons.org/meta/0866FF'],
    logoLabels: ['Meta'],
    priority: 'recommended',
  },
  {
    name: 'Brevo',
    category: 'Email',
    description: 'Synchroniser les contacts et automatiser les campagnes email.',
    benefit: 'Relancer les prospects, informer les apprenants et suivre les campagnes.',
    logoUrls: ['https://cdn.simpleicons.org/brevo/0B996E'],
    logoLabels: ['Brevo'],
    priority: 'recommended',
  },
  {
    name: 'WhatsApp / Wapino',
    category: 'Communication',
    description: 'Envoyer des rappels, confirmations et notifications WhatsApp via votre passerelle de communication.',
    benefit: 'Réduire les oublis et centraliser les communications importantes.',
    logoUrls: ['https://cdn.simpleicons.org/whatsapp/25D366'],
    logoLabels: ['WhatsApp / Wapino'],
    priority: 'recommended',
  },
  {
    name: 'Google Calendar & Meet',
    category: 'Planning',
    description: 'Synchroniser les séances et faciliter l’accès aux rendez-vous en ligne.',
    benefit: 'Éviter les doubles saisies et garder les calendriers à jour.',
    logoUrls: [
      'https://cdn.simpleicons.org/googlecalendar/4285F4',
      'https://cdn.simpleicons.org/googlemeet/00897B',
    ],
    logoLabels: ['Google Calendar', 'Google Meet'],
    priority: 'planned',
  },
  {
    name: 'Zoom',
    category: 'Visioconférence',
    description: 'Créer ou associer des réunions Zoom aux séances live.',
    benefit: 'Piloter les sessions live depuis le même environnement.',
    logoUrls: ['https://cdn.simpleicons.org/zoom/0B5CFF'],
    logoLabels: ['Zoom'],
    priority: 'planned',
  },
  {
    name: 'Make / Zapier',
    category: 'Automatisation',
    description: 'Déclencher des automatisations vers d’autres outils métier.',
    benefit: 'Connecter CRM, formulaires, tableaux de suivi ou outils internes sans recoder chaque workflow.',
    logoUrls: [
      'https://cdn.simpleicons.org/make/6D00CC',
      'https://cdn.simpleicons.org/zapier/FF4F00',
    ],
    logoLabels: ['Make', 'Zapier'],
    priority: 'planned',
  },
]

export function SchoolConnectPage() {
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

      <section className="app-card connect-intro-card">
        <div>
          <span className="section-label">Centre d’intégrations</span>
          <h2>Un seul endroit pour vos connexions</h2>
          <p>Les connecteurs ci-dessous sont proposés par ordre d’utilité. Ils ne sont pas encore actifs : chaque connexion sera réellement branchée via API ou OAuth avant d’être rendue disponible.</p>
        </div>
        <div className="connect-priority-legend">
          <span><i className="is-recommended" /> Priorité recommandée</span>
          <span><i className="is-planned" /> Phase suivante</span>
        </div>
      </section>

      <section className="connect-grid">
        {integrations.map((integration) => (
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
              <span className={`connect-status ${integration.priority}`}>
                {integration.priority === 'recommended' ? 'Recommandé' : 'À venir'}
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
            <button className="secondary-button connect-disabled-action" type="button" disabled>
              Connexion bientôt disponible
            </button>
          </article>
        ))}
      </section>
    </main>
  )
}
