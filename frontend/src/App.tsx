import {
  ArrowRight,
  BarChart3,
  BookOpenCheck,
  CalendarDays,
  Check,
  ChevronRight,
  GraduationCap,
  LayoutDashboard,
  Radio,
  ShieldCheck,
  Sparkles,
  Users,
} from 'lucide-react'

const features = [
  {
    icon: BookOpenCheck,
    title: 'Formations & sessions',
    text: 'Créez vos formations, cohortes, modules, cours et parcours depuis un seul espace.',
  },
  {
    icon: Users,
    title: 'Équipe pédagogique',
    text: 'Administrez vos professeurs, intervenants et étudiants avec des rôles adaptés.',
  },
  {
    icon: CalendarDays,
    title: 'Planning intelligent',
    text: 'Planifiez les journées, cours et séances avec une vue claire de toute votre école.',
  },
  {
    icon: Radio,
    title: 'Présentiel, live & hybride',
    text: 'Pilotez des formations physiques, en ligne ou hybrides sans multiplier les outils.',
  },
  {
    icon: BarChart3,
    title: 'Suivi pédagogique',
    text: 'Mesurez la progression, l’assiduité, les évaluations et l’activité des apprenants.',
  },
  {
    icon: ShieldCheck,
    title: 'Votre espace, vos données',
    text: 'Chaque école dispose de son environnement isolé, sécurisé et administrable.',
  },
]

const plans = [
  {
    name: 'Starter',
    price: 'Pour démarrer',
    description: 'Pour les formateurs et petites structures.',
    items: ['École personnalisée', 'Formations & sessions', 'Professeurs & étudiants', 'Cours et évaluations'],
  },
  {
    name: 'Pro',
    price: 'Pour grandir',
    description: 'Pour les écoles qui veulent automatiser leur fonctionnement.',
    items: ['Tout Starter', 'Automatisations', 'Reporting avancé', 'Domaine personnalisé'],
    featured: true,
  },
  {
    name: 'Business',
    price: 'Sur mesure',
    description: 'Pour les organismes avec plusieurs équipes et de gros volumes.',
    items: ['Tout Pro', 'Multi-administrateurs', 'White-label avancé', 'Accompagnement prioritaire'],
  },
]

function BrandMark() {
  return (
    <div className="brand">
      <span className="brand-mark">
        <span />
        <span />
      </span>
      <span>
        Académie <strong>SaaS</strong>
      </span>
    </div>
  )
}

function DashboardPreview() {
  return (
    <div className="dashboard-shell">
      <div className="dashboard-window">
        <aside className="preview-sidebar">
          <div className="preview-logo">A</div>
          <span className="preview-dot active" />
          <span className="preview-dot" />
          <span className="preview-dot" />
          <span className="preview-dot" />
        </aside>

        <div className="preview-content">
          <div className="preview-topbar">
            <div>
              <p>Bonjour Clarisse</p>
              <strong>Tableau de bord</strong>
            </div>
            <div className="preview-avatar">CM</div>
          </div>

          <div className="metric-grid">
            <div className="metric-card">
              <span>Étudiants</span>
              <strong>248</strong>
              <small>+12 ce mois</small>
            </div>
            <div className="metric-card">
              <span>Formations</span>
              <strong>12</strong>
              <small>8 actives</small>
            </div>
            <div className="metric-card">
              <span>Progression</span>
              <strong>84%</strong>
              <small>+6,4%</small>
            </div>
          </div>

          <div className="preview-main-grid">
            <div className="chart-card">
              <div className="card-title-row">
                <strong>Activité de l’école</strong>
                <span>30 jours</span>
              </div>
              <div className="chart">
                <span style={{ height: '34%' }} />
                <span style={{ height: '48%' }} />
                <span style={{ height: '42%' }} />
                <span style={{ height: '68%' }} />
                <span style={{ height: '58%' }} />
                <span style={{ height: '78%' }} />
                <span style={{ height: '88%' }} />
              </div>
            </div>

            <div className="schedule-card">
              <strong>Aujourd’hui</strong>
              <div className="schedule-item">
                <span className="schedule-time">09:00</span>
                <span>
                  <b>Design graphique</b>
                  <small>Module 4 · Live</small>
                </span>
              </div>
              <div className="schedule-item">
                <span className="schedule-time">14:30</span>
                <span>
                  <b>Motion Design</b>
                  <small>Session octobre</small>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="floating-card floating-students">
        <Users size={18} />
        <div>
          <small>Nouveaux inscrits</small>
          <strong>+32</strong>
        </div>
      </div>

      <div className="floating-card floating-live">
        <Radio size={18} />
        <div>
          <small>Live en cours</small>
          <strong>28 participants</strong>
        </div>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <main>
      <header className="site-header">
        <div className="container header-inner">
          <BrandMark />
          <nav className="desktop-nav" aria-label="Navigation principale">
            <a href="#produit">Produit</a>
            <a href="#fonctionnalites">Fonctionnalités</a>
            <a href="#tarifs">Tarifs</a>
            <a href="#faq">Ressources</a>
          </nav>
          <div className="header-actions">
            <button className="link-button">Se connecter</button>
            <button className="primary-button compact">
              Créer mon école
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </header>

      <section className="hero" id="produit">
        <div className="hero-blob hero-blob-one" />
        <div className="hero-blob hero-blob-two" />

        <div className="container hero-grid">
          <div className="hero-copy">
            <div className="eyebrow">
              <Sparkles size={16} />
              Votre école digitale, prête à fonctionner
            </div>
            <h1>
              Votre école.
              <br />
              Votre identité.
              <br />
              <span>Une seule plateforme.</span>
            </h1>
            <p className="hero-description">
              Lancez et administrez vos formations, vos professeurs, vos étudiants,
              vos lives et votre suivi pédagogique sans construire votre propre logiciel.
            </p>
            <div className="hero-actions">
              <button className="primary-button">
                Créer mon école
                <ArrowRight size={18} />
              </button>
              <button className="secondary-button">
                Voir une démo
                <ChevronRight size={17} />
              </button>
            </div>
            <div className="hero-reassurance">
              <span><Check size={15} /> Sans installation</span>
              <span><Check size={15} /> Votre branding</span>
              <span><Check size={15} /> Évolutif</span>
            </div>
          </div>

          <DashboardPreview />
        </div>
      </section>

      <section className="trust-strip">
        <div className="container">
          <p>Un seul environnement pour piloter toute votre activité de formation</p>
          <div className="trust-items">
            <span>Formation</span>
            <span>Étudiants</span>
            <span>Professeurs</span>
            <span>Évaluations</span>
            <span>Live</span>
            <span>Suivi</span>
          </div>
        </div>
      </section>

      <section className="section" id="fonctionnalites">
        <div className="container">
          <div className="section-heading">
            <div className="eyebrow">
              <LayoutDashboard size={16} />
              Tout au même endroit
            </div>
            <h2>Faites fonctionner votre école, pas vos outils.</h2>
            <p>
              La plateforme réunit les briques essentielles pour administrer une
              formation guidée de bout en bout.
            </p>
          </div>

          <div className="feature-grid">
            {features.map(({ icon: Icon, title, text }) => (
              <article className="feature-card" key={title}>
                <div className="feature-icon">
                  <Icon size={22} />
                </div>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section workflow-section">
        <div className="container workflow-grid">
          <div className="workflow-copy">
            <div className="eyebrow">
              <GraduationCap size={16} />
              Pensé pour les écoles
            </div>
            <h2>Vous vous concentrez sur la pédagogie. La plateforme structure le reste.</h2>
            <p>
              Créez votre espace, personnalisez-le, invitez votre équipe et commencez
              à administrer vos apprenants depuis un tableau de bord unique.
            </p>
            <button className="secondary-button">
              Découvrir le fonctionnement
              <ArrowRight size={17} />
            </button>
          </div>

          <div className="steps-card">
            {[
              ['01', 'Créez votre école', 'Nom, identité, logo et paramètres.'],
              ['02', 'Configurez vos formations', 'Sessions, planning, professeurs et contenus.'],
              ['03', 'Invitez vos étudiants', 'Accès sécurisé et suivi de progression.'],
              ['04', 'Pilotez votre activité', 'Statistiques, évaluations et automatisations.'],
            ].map(([number, title, text]) => (
              <div className="step-row" key={number}>
                <span>{number}</span>
                <div>
                  <strong>{title}</strong>
                  <p>{text}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section pricing-section" id="tarifs">
        <div className="container">
          <div className="section-heading centered">
            <div className="eyebrow">Des offres qui grandissent avec vous</div>
            <h2>Commencez simplement. Évoluez quand vous êtes prêt.</h2>
            <p>Les quotas et tarifs définitifs seront configurables depuis le moteur d’abonnement.</p>
          </div>

          <div className="pricing-grid">
            {plans.map((plan) => (
              <article className={`pricing-card ${plan.featured ? 'featured' : ''}`} key={plan.name}>
                {plan.featured && <div className="popular-badge">Le plus flexible</div>}
                <span className="plan-name">{plan.name}</span>
                <h3>{plan.price}</h3>
                <p>{plan.description}</p>
                <div className="plan-items">
                  {plan.items.map((item) => (
                    <span key={item}><Check size={16} /> {item}</span>
                  ))}
                </div>
                <button className={plan.featured ? 'primary-button full' : 'secondary-button full'}>
                  Découvrir l’offre
                </button>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="cta-section">
        <div className="container">
          <div className="cta-card">
            <div>
              <span>Prêt à construire votre école ?</span>
              <h2>Votre pédagogie mérite sa propre plateforme.</h2>
            </div>
            <button className="light-button">
              Créer mon école
              <ArrowRight size={18} />
            </button>
          </div>
        </div>
      </section>

      <footer className="site-footer" id="faq">
        <div className="container footer-inner">
          <BrandMark />
          <p>© 2026 Académie des Créatifs SaaS. Tous droits réservés.</p>
        </div>
      </footer>
    </main>
  )
}
