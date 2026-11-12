import { useEffect, useState, type ReactNode } from 'react'
import {
  ArrowRight,
  BellRing,
  CalendarDays,
  Check,
  ClipboardCheck,
  CreditCard,
  FileText,
  Globe,
  LayoutGrid,
  MapPin,
  MonitorPlay,
  Palette,
  Radio,
  Smartphone,
  Tag,
  Timer,
} from 'lucide-react'
import { BrandLogo } from '../brand/BrandLogo'
import { listPlans, type Plan, type PlanEntitlement } from '../lib/api'
import '../landing.css'

const REGISTER_URL = '/login?mode=register'
const LOGIN_URL = '/login'

/** Screenshots of the platform, taken on a fictional demo school (Studio Kora). */
const SHOTS = {
  dashboard: '/landing/dashboard-prof.webp',
  progress: '/landing/progression-mobile.webp',
  siteHome: '/landing/site-accueil.webp',
  catalogue: '/landing/site-catalogue.webp',
  siteCheckout: '/landing/site-formation-mobile.webp',
  attendance: '/landing/presences-live.webp',
  management: '/landing/pilotage-direction.webp',
}

type Feature = {
  id: string
  title: string
  text: string
  points: string[]
  visual: ReactNode
}

/** What a school's own website does for it: the part of the product that brings in students. */
const SITE_POINTS = [
  { icon: Globe, title: 'À votre adresse', text: 'votre-ecole.academiecreatif.com dès la création, ou votre propre nom de domaine.' },
  { icon: Palette, title: 'À vos couleurs', text: 'Logo, couleurs, polices, bandeau d’annonce et page de présentation.' },
  { icon: LayoutGrid, title: 'Catalogue et sessions', text: 'Programme, prochaines sessions, places restantes et prix en FCFA.' },
  { icon: CreditCard, title: 'Paiement en ligne', text: 'Mobile Money ou carte, en une fois ou en plusieurs échéances.' },
  { icon: Tag, title: 'Promotions', text: 'Réductions et codes promo pour remplir vos prochaines sessions.' },
  { icon: FileText, title: 'Pages légales', text: 'Mentions légales, CGV, confidentialité et remboursement intégrés.' },
]

const FORMATS = [
  { icon: Radio, title: 'En live', text: 'La classe se tient dans la plateforme, à vos couleurs.' },
  { icon: MonitorPlay, title: 'En ligne', text: 'Des parcours que vos étudiants suivent à leur rythme.' },
  { icon: MapPin, title: 'En présentiel', text: 'Planning, présences et comptes rendus de séance.' },
]

const STEPS = [
  { title: 'Créez votre école', text: 'Nom, logo, couleurs et adresse en ligne : votre espace est prêt en quelques minutes.' },
  { title: 'Publiez vos formations', text: 'Programme, sessions, prix et échéances de paiement, puis vos professeurs.' },
  { title: 'Accueillez vos étudiants', text: 'Ils s’inscrivent et paient en ligne, suivent les cours et vous suivez leurs progrès.' },
]

const FAQ = [
  {
    question: 'Mes étudiants peuvent-ils payer par Mobile Money ?',
    answer: 'Oui. Les paiements passent par Tara Money, en FCFA : Mobile Money ou carte bancaire, en une fois ou en plusieurs échéances. Les retards de paiement sont suivis pour vous.',
  },
  {
    question: 'Mon école aura-t-elle sa propre adresse ?',
    answer: 'Dès sa création, votre école a son site en votre-ecole.academiecreatif.com, avec votre logo et vos couleurs. Vous pouvez aussi y brancher votre propre nom de domaine.',
  },
  {
    question: 'Faut-il installer une application pour les cours en live ?',
    answer: 'Non. La classe s’ouvre dans le navigateur, sur ordinateur comme sur téléphone, sans rien installer. Le professeur garde la main : micros, appel, fin du cours.',
  },
  {
    question: 'Comment savoir si un étudiant a vraiment suivi le cours ?',
    answer: 'La plateforme mesure le temps passé dans la salle et le professeur peut faire l’appel en un clic. Au rapport de séance, les présences sont proposées à partir de ces preuves, et le professeur peut les corriger.',
  },
  {
    question: 'Les données de mon école sont-elles séparées des autres ?',
    answer: 'Oui. Chaque école a son espace isolé : ses formations, ses étudiants, ses paiements et ses documents ne sont visibles que par son équipe.',
  },
  {
    question: 'Puis-je essayer avant de payer ?',
    answer: 'Oui. Créer votre école lance une période d’essai gratuite, sans moyen de paiement à fournir. Vous choisissez un forfait quand vous êtes prêt.',
  },
]

const FEATURE_LABELS: Record<string, (limit: number | null) => string> = {
  students: (limit) => (limit === null ? 'Étudiants illimités' : `Jusqu’à ${limit.toLocaleString('fr-FR')} étudiants`),
  teachers: (limit) => (limit === null ? 'Professeurs illimités' : `Jusqu’à ${limit} professeurs`),
  active_formations: (limit) => (limit === null ? 'Formations illimitées' : `${limit} formations actives`),
  live: (limit) => limit === null ? 'Cours en live inclus' : `Cours en live inclus · ${limit} étudiants max par classe`,
  custom_domain: () => 'Votre propre nom de domaine',
  automations: () => 'Relances et rappels automatiques',
  advanced_reporting: () => 'Rapports avancés',
}

function entitlementLabel(item: PlanEntitlement) {
  const label = FEATURE_LABELS[item.feature_key]
  if (label) return label(item.limit_value)
  const name = item.feature_key.replace(/_/g, ' ')
  const text = name.charAt(0).toUpperCase() + name.slice(1)
  return item.limit_value === null ? text : `${text} : ${item.limit_value}`
}

function formatPrice(amount: number, currency: string) {
  // XAF has no subunit: amounts are stored in whole francs.
  if (currency.toUpperCase() === 'XAF') {
    return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'XAF', maximumFractionDigits: 0 }).format(amount)
  }
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency, maximumFractionDigits: 2 }).format(amount / 100)
}

/** Fades sections in as they scroll into view; everything stays visible without it. */
function useReveal() {
  useEffect(() => {
    const items = Array.from(document.querySelectorAll<HTMLElement>('.lp-reveal'))
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce || typeof IntersectionObserver === 'undefined') return undefined
    document.documentElement.classList.add('lp-motion')
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-in')
          observer.unobserve(entry.target)
        }
      })
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 })
    items.forEach((item) => observer.observe(item))
    return () => {
      observer.disconnect()
      document.documentElement.classList.remove('lp-motion')
    }
  }, [])
}

function Browser({ src, alt, address, eager = false }: { src: string; alt: string; address: string; eager?: boolean }) {
  return (
    <figure className="lp-browser">
      <div className="lp-browser__bar" aria-hidden="true">
        <span /><span /><span />
        <em>{address}</em>
      </div>
      <img
        src={src}
        alt={alt}
        width={1600}
        height={1000}
        loading={eager ? 'eager' : 'lazy'}
        decoding="async"
        {...(eager ? { fetchPriority: 'high' as const } : {})}
      />
    </figure>
  )
}

function Phone({ src, alt, className = '' }: { src: string; alt: string; className?: string }) {
  return (
    <figure className={`lp-phone ${className}`}>
      <img src={src} alt={alt} width={520} height={1125} loading="lazy" decoding="async" />
    </figure>
  )
}

const FEATURES: Feature[] = [
  {
    id: 'live',
    title: 'Des cours en direct, et des présences qui ne mentent pas',
    text: 'La classe s’ouvre dans la plateforme, sans lien à partager. Vous savez qui était là, et combien de temps.',
    points: [
      'Un seul appareil par étudiant, salle réservée aux inscrits',
      'Temps passé dans la salle et appel en un clic',
      'Présences pré-remplies au rapport de séance',
    ],
    visual: <Browser src={SHOTS.attendance} alt="Présences d’une séance live avec le temps passé dans la salle" address="studio-kora.academiecreatif.com/app/teacher/attendance" />,
  },
  {
    id: 'suivi',
    title: 'Un suivi qui donne envie d’aller jusqu’au bout',
    text: 'Quiz, devoirs corrigés, notes et badges de progression : chaque étudiant voit où il en est et ce qui le fera progresser.',
    points: [
      'Quiz corrigés automatiquement, devoirs notés par le professeur',
      'Badges de progression, d’Aventurier à Professionnel',
      'Certificats vérifiables en ligne en fin de parcours',
    ],
    visual: (
      <div className="lp-feature__phone-stage">
        <Phone src={SHOTS.progress} alt="Page de progression d’une étudiante sur téléphone" />
        <div className="lp-chip lp-chip--badge">
          <img className="lp-chip__badge" src="/student-badges/intermediaire.svg" alt="" aria-hidden="true" />
          Niveau Intermédiaire atteint
        </div>
        <div className="lp-chip lp-chip--quiz"><ClipboardCheck size={16} /> Quiz réussi · 100 %</div>
      </div>
    ),
  },
  {
    id: 'pilotage',
    title: 'Toute votre école d’un coup d’œil',
    text: 'Inscriptions, paiements, professeurs, sessions et comptes rendus : la direction voit ce qui avance et ce qui demande son attention.',
    points: [
      'Paiements encaissés et échéances en retard',
      'Comptes rendus de séance de chaque professeur',
      'Alertes quand un étudiant décroche',
    ],
    visual: <Browser src={SHOTS.management} alt="Tableau de bord de la direction d’une école" address="studio-kora.academiecreatif.com/app/manage" />,
  },
]

function Pricing() {
  const [plans, setPlans] = useState<Plan[] | null>(null)
  const [failed, setFailed] = useState(false)
  const [annual, setAnnual] = useState(false)

  useEffect(() => {
    let active = true
    listPlans()
      .then((items) => { if (active) setPlans(items.filter((plan) => plan.is_public)) })
      .catch(() => { if (active) setFailed(true) })
    return () => { active = false }
  }, [])

  const hasAnnual = Boolean(plans?.some((plan) => plan.annual_price_cents !== null))
  const trialDays = plans?.find((plan) => plan.code === 'starter')?.trial_days ?? plans?.[0]?.trial_days ?? 0

  return (
    <section className="lp-section lp-pricing" id="tarifs">
      <div className="lp-container">
        <header className="lp-heading lp-heading--center lp-reveal">
          <h2>Un forfait pour chaque étape de votre école</h2>
          <p>
            {trialDays > 0
              ? `Commencez par ${trialDays} jours d’essai gratuit, sans moyen de paiement. Changez de forfait quand votre école grandit.`
              : 'Commencez gratuitement et changez de forfait quand votre école grandit.'}
          </p>
          {hasAnnual && (
            <div className="lp-toggle" role="group" aria-label="Période de facturation">
              <button type="button" className={annual ? '' : 'is-active'} onClick={() => setAnnual(false)}>Mensuel</button>
              <button type="button" className={annual ? 'is-active' : ''} onClick={() => setAnnual(true)}>Annuel</button>
            </div>
          )}
        </header>

        {failed || (plans !== null && plans.length === 0) ? (
          <p className="lp-pricing__empty">Les forfaits seront publiés très bientôt. Vous pouvez déjà créer votre école et l’essayer gratuitement.</p>
        ) : (
          <div className="lp-plans">
            {(plans ?? [null, null, null]).map((plan, index) => {
              if (plan === null) return <article className="lp-plan lp-plan--loading" key={index} aria-hidden="true" />
              const amount = annual ? plan.annual_price_cents : plan.monthly_price_cents
              const featured = plan.code === 'pro'
              const features = plan.entitlements.filter((item) => item.enabled)
              return (
                <article className={`lp-plan${featured ? ' lp-plan--featured' : ''}`} key={plan.id}>
                  {featured && <span className="lp-plan__flag">Recommandé</span>}
                  <h3>{plan.name}</h3>
                  <p className="lp-plan__desc">{plan.description}</p>
                  <div className="lp-plan__price">
                    {amount === null
                      ? <strong className="lp-plan__soon">Tarif bientôt disponible</strong>
                      : <><strong>{formatPrice(amount, plan.currency)}</strong><span>{annual ? '/ an' : '/ mois'}</span></>}
                  </div>
                  {features.length > 0 && (
                    <ul>
                      {features.map((item) => <li key={item.feature_key}><Check size={16} /> {entitlementLabel(item)}</li>)}
                    </ul>
                  )}
                  <a className={`lp-btn ${featured ? 'lp-btn--primary' : 'lp-btn--ghost'} lp-btn--block`} href={REGISTER_URL}>
                    Commencer l’essai
                  </a>
                </article>
              )
            })}
          </div>
        )}
      </div>
    </section>
  )
}

export default function LandingPage() {
  useReveal()

  return (
    <main className="lp">
      <header className="lp-header">
        <div className="lp-container lp-header__inner">
          <a className="lp-brand" href="/" aria-label="Académie des Créatifs, accueil">
            <BrandLogo className="lp-brand__logo" />
            <span>
              <strong>Académie des Créatifs</strong>
              <small>pour les écoles</small>
            </span>
          </a>
          <nav className="lp-nav" aria-label="Navigation principale">
            <a href="#fonctionnalites">Fonctionnalités</a>
            <a href="#fonctionnement">Comment ça marche</a>
            <a href="#tarifs">Tarifs</a>
            <a href="#faq">Questions</a>
          </nav>
          <div className="lp-header__actions">
            <a className="lp-link" href={LOGIN_URL}>Se connecter</a>
            <a className="lp-btn lp-btn--primary lp-btn--small" href={REGISTER_URL}>
              Créer mon école <ArrowRight size={16} />
            </a>
          </div>
        </div>
      </header>

      <section className="lp-hero">
        <div className="lp-container lp-hero__grid">
          <div className="lp-hero__copy">
            <h1>
              Votre école de formation, <span>en ligne et à votre nom.</span>
            </h1>
            <p className="lp-hero__lead">
              Site de l’école, inscriptions et paiements Mobile Money, cours en live, suivi des étudiants
              jusqu’au certificat : tout est prêt, à vos couleurs.
            </p>
            <div className="lp-hero__actions">
              <a className="lp-btn lp-btn--primary" href={REGISTER_URL}>Créer mon école <ArrowRight size={18} /></a>
              <a className="lp-btn lp-btn--ghost" href="#tarifs">Voir les tarifs</a>
            </div>
            <ul className="lp-hero__proof">
              <li><Check size={15} /> Essai gratuit</li>
              <li><Check size={15} /> Paiements en FCFA</li>
              <li><Check size={15} /> Rien à installer</li>
            </ul>
          </div>

          <div className="lp-hero__visual">
            <Browser src={SHOTS.dashboard} alt="Espace professeur d’une école sur la plateforme" address="studio-kora.academiecreatif.com" eager />
            <Phone src={SHOTS.progress} alt="Progression d’une étudiante sur téléphone" className="lp-hero__phone" />
            <div className="lp-chip lp-chip--live"><span className="lp-dot" /> Cours en live · 14 présents</div>
            <p className="lp-hero__caption">Captures réelles de la plateforme, sur une école de démonstration.</p>
          </div>
        </div>
      </section>

      <section className="lp-section lp-site" id="site-ecole">
        <div className="lp-container">
          <header className="lp-heading lp-heading--center lp-reveal">
            <h2>Chaque école a son site, prêt à vendre ses formations</h2>
            <p>
              Vos futurs étudiants découvrent vos formations, choisissent leur session et paient en ligne,
              sur un site à votre nom. Vous n’avez rien à construire.
            </p>
          </header>
          <div className="lp-site__stage lp-reveal">
            <Browser src={SHOTS.siteHome} alt="Page d’accueil du site d’une école" address="studio-kora.academiecreatif.com" />
            <Phone src={SHOTS.siteCheckout} alt="Choix de la session et prix d’une formation sur téléphone" className="lp-site__phone" />
          </div>
          <div className="lp-site__points">
            {SITE_POINTS.map(({ icon: Icon, title, text }) => (
              <div className="lp-site__point lp-reveal" key={title}>
                <span className="lp-icon"><Icon size={20} /></span>
                <div>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="lp-site__cta lp-reveal">
            <a className="lp-btn lp-btn--primary" href={REGISTER_URL}>Créer le site de mon école <ArrowRight size={18} /></a>
            <span>Votre site est en ligne dès la création de l’école.</span>
          </div>
        </div>
      </section>

      <section className="lp-section" id="fonctionnalites">
        <div className="lp-container">
          <header className="lp-heading lp-heading--center lp-reveal">
            <h2>De l’inscription au certificat, sans jongler entre dix outils</h2>
            <p>Vous gardez votre pédagogie. La plateforme s’occupe des cours, des présences, du suivi et de la gestion.</p>
          </header>

          <div className="lp-features">
            {FEATURES.map(({ id, title, text, points, visual }, index) => (
              <article className={`lp-feature lp-reveal${index % 2 ? ' lp-feature--flip' : ''}`} key={id} id={`fonction-${id}`}>
                <div className="lp-feature__copy">
                  <h3>{title}</h3>
                  <p>{text}</p>
                  <ul className="lp-checks">
                    {points.map((point) => <li key={point}><Check size={16} /> {point}</li>)}
                  </ul>
                </div>
                <div className="lp-feature__visual">{visual}</div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-section lp-band">
        <div className="lp-container lp-band__grid">
          {[
            { icon: CalendarDays, title: 'Planning et rapports', text: 'Séances, professeurs et comptes rendus.' },
            { icon: BellRing, title: 'Notifications', text: 'Rappels de cours, devoirs et paiements.' },
            { icon: Smartphone, title: 'Sur téléphone', text: 'Tout fonctionne sur mobile, sans application.' },
            { icon: Timer, title: 'Rattrapage', text: 'Devoirs en retard et quiz à repasser.' },
          ].map(({ icon: Icon, title, text }) => (
            <div className="lp-band__item lp-reveal" key={title}>
              <Icon size={20} />
              <strong>{title}</strong>
              <span>{text}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="lp-section" id="fonctionnement">
        <div className="lp-container">
          <header className="lp-heading lp-heading--center lp-reveal">
            <h2>Votre école en ligne en trois étapes</h2>
          </header>
          <ol className="lp-steps">
            {STEPS.map((step, index) => (
              <li className="lp-step lp-reveal" key={step.title}>
                <span className="lp-step__number">{index + 1}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <Pricing />

      <section className="lp-section" id="faq">
        <div className="lp-container lp-faq">
          <header className="lp-heading lp-reveal">
            <h2>Ce que les écoles nous demandent</h2>
            <p>Une autre question ? Créez votre école et écrivez-nous depuis votre espace.</p>
          </header>
          <div className="lp-faq__list">
            {FAQ.map((item) => (
              <details className="lp-faq__item lp-reveal" key={item.question}>
                <summary>{item.question}</summary>
                <p>{item.answer}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-section lp-formats" aria-label="Formats de formation">
        <div className="lp-container">
          <header className="lp-heading lp-heading--center lp-reveal">
            <h2>Des formats de cours adaptés à votre école</h2>
            <p>En direct, à distance ou en salle : accompagnez vos étudiants dans chaque façon d’apprendre.</p>
          </header>
          <div className="lp-formats__grid">
            {FORMATS.map(({ icon: Icon, title, text }) => (
              <article className="lp-format lp-reveal" key={title}>
                <span className="lp-icon"><Icon size={20} /></span>
                <div>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-section lp-cta-wrap">
        <div className="lp-container">
          <div className="lp-cta lp-reveal">
            <div>
              <h2>Votre pédagogie mérite sa propre école en ligne.</h2>
              <p>Créez votre école aujourd’hui, publiez votre première formation demain.</p>
            </div>
            <a className="lp-btn lp-btn--mint" href={REGISTER_URL}>Créer mon école <ArrowRight size={18} /></a>
          </div>
        </div>
      </section>

      <footer className="lp-footer">
        <div className="lp-container lp-footer__inner">
          <a className="lp-brand lp-brand--footer" href="/">
            <BrandLogo className="lp-brand__logo" />
            <span>
              <strong>Académie des Créatifs</strong>
              <small>pour les écoles</small>
            </span>
          </a>
          <nav aria-label="Liens du pied de page">
            <a href="#site-ecole">Le site de l’école</a>
            <a href="#fonctionnalites">Fonctionnalités</a>
            <a href="#tarifs">Tarifs</a>
            <a href="#faq">Questions</a>
            <a href={LOGIN_URL}>Se connecter</a>
          </nav>
          <p>© {new Date().getFullYear()} Académie des Créatifs</p>
        </div>
      </footer>
    </main>
  )
}
