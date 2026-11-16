import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useState, type ReactNode } from 'react'
import {
  ArrowRight,
  BellRing,
  Calculator,
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
  X,
} from 'lucide-react'
import { BrandWordmark } from '../brand/BrandWordmark'
import { getDemoInfo, listPlans, type DemoInfo, type Plan } from '../lib/api'
import { DemoMenu } from '../components/DemoMenu'
import { LandingNavbar } from '../components/LandingNavbar'
import { commissionLabel, monthlyEquivalent, planHighlights } from '../lib/planFeatures'
import { PlanComparison } from '../components/PlanComparison'
import { useAuth } from '../auth/AuthContext'
import { readDemoState } from '../lib/demoState'
import { Link } from 'react-router-dom'
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
  liveClass: '/landing/cours-live.webp',
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
    answer: 'Oui. Vos étudiants paient en FCFA par Mobile Money, en une fois ou en plusieurs échéances. Les retards de paiement sont suivis pour vous.',
  },
  {
    question: 'Combien prenez-vous sur mes ventes ?',
    answer: 'Une commission sur chaque paiement de vos étudiants, frais de paiement compris : plus votre forfait est élevé, plus elle est basse. Le reste vous est versé quand vous le demandez, par Mobile Money ou virement.',
  },
  {
    question: 'Y a-t-il une limite au nombre d’étudiants ?',
    answer: 'Non, dans aucun forfait, même gratuit. D’un forfait à l’autre changent la taille de vos classes en live, le nombre de lives en même temps, les replays et les outils de suivi.',
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
    answer: 'Oui. Créer votre école ouvre un essai gratuit du forfait Pro, lives compris, sans moyen de paiement. À la fin de l’essai, sans forfait payé, votre école continue gratuitement en Découverte.',
  },
]

function formatPrice(amount: number, currency: string) {
  // XAF has no subunit: amounts are stored in whole francs.
  if (currency.toUpperCase() === 'XAF') {
    return new Intl.NumberFormat(activeSchoolLocale(), { style: 'currency', currency: 'XAF', maximumFractionDigits: 0 }).format(amount)
  }
  return new Intl.NumberFormat(activeSchoolLocale(), { style: 'currency', currency, maximumFractionDigits: 2 }).format(amount / 100)
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
    visual: (
      <div className="lp-live-stage">
        <Browser src={SHOTS.attendance} alt="Présences d’une séance live avec le temps passé dans la salle" address="studio-kora.academiecreatif.com/app/teacher/attendance" />
        <figure className="lp-live-window">
          <img
            src={SHOTS.liveClass}
            alt="Cours en direct dans la salle de l’école : les étudiants en visio et l’appel en cours"
            width={1200}
            height={675}
            loading="lazy"
            decoding="async"
          />
        </figure>
      </div>
    ),
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
  const [estimatorOpen, setEstimatorOpen] = useState(false)
  const [monthlySales, setMonthlySales] = useState('1000000')

  useEffect(() => {
    let active = true
    listPlans()
      .then((items) => { if (active) setPlans(items.filter((plan) => plan.is_public)) })
      .catch(() => { if (active) setFailed(true) })
    return () => { active = false }
  }, [])

  const hasAnnual = Boolean(plans?.some((plan) => (plan.annual_price_cents ?? 0) > 0))
  const trialPlan = plans?.find((plan) => plan.code === 'pro') ?? plans?.find((plan) => plan.trial_days > 0)
  const trialDays = trialPlan?.trial_days ?? 0
  const discount = (() => {
    const paid = plans?.find((plan) => (plan.monthly_price_cents ?? 0) > 0 && plan.annual_price_cents !== null)
    if (!paid || !paid.monthly_price_cents || paid.annual_price_cents === null) return 0
    return Math.round(100 - (paid.annual_price_cents * 100) / (paid.monthly_price_cents * 12))
  })()

  return (
    <section className="lp-section lp-pricing" id="tarifs">
      <div className="lp-container">
        <header className="lp-heading lp-heading--center lp-reveal">
          <h2>Un forfait pour chaque étape de votre école</h2>
          <p>
            Étudiants illimités dans tous les forfaits. Commencez gratuitement
            {trialDays > 0 && trialPlan ? `, ou essayez ${trialPlan.name} ${trialDays} jours sans moyen de paiement` : ''},
            et changez de forfait quand votre école grandit.
          </p>
          {hasAnnual && (
            <div className="lp-toggle" role="group" aria-label="Période de facturation">
              <button type="button" className={annual ? '' : 'is-active'} onClick={() => setAnnual(false)}>Mensuel</button>
              <button type="button" className={annual ? 'is-active' : ''} onClick={() => setAnnual(true)}>
                Annuel{discount > 0 && <span className="lp-toggle__save">−{discount} %</span>}
              </button>
            </div>
          )}
        </header>

        {failed || (plans !== null && plans.length === 0) ? (
          <p className="lp-pricing__empty">Les forfaits seront publiés très bientôt. Vous pouvez déjà créer votre école et l’essayer gratuitement.</p>
        ) : (
          <div className="lp-plans">
            {(plans ?? [null, null, null, null]).map((plan, index) => {
              if (plan === null) return <article className="lp-plan lp-plan--loading" key={index} aria-hidden="true" />
              const free = plan.monthly_price_cents === 0
              const perMonth = monthlyEquivalent(plan, annual && !free)
              const featured = plan.code === 'pro'
              const commission = commissionLabel(plan.sales_commission_bps)
              return (
                <article className={`lp-plan${featured ? ' lp-plan--featured' : ''}`} key={plan.id}>
                  {featured && <span className="lp-plan__flag">Recommandé</span>}
                  <h3>{plan.name}</h3>
                  <p className="lp-plan__desc">{plan.description}</p>
                  <div className="lp-plan__price">
                    {perMonth === null
                      ? <strong className="lp-plan__soon">Tarif bientôt disponible</strong>
                      : <><strong>{free ? 'Gratuit' : formatPrice(perMonth, plan.currency)}</strong>{!free && <span>/ mois</span>}</>}
                    <small>
                      {free
                        ? 'Sans abonnement, sans engagement'
                        : annual && plan.annual_price_cents !== null
                          ? `soit ${formatPrice(plan.annual_price_cents, plan.currency)} par an`
                          : 'Sans engagement'}
                    </small>
                  </div>
                  <ul>
                    {planHighlights(plan.entitlements).map((line) => (
                      <li className={line.excluded ? 'is-excluded' : undefined} key={line.key}>
                        {line.excluded ? <X size={16} /> : <Check size={16} />}
                        <span>{line.label}{line.soon && <em className="lp-plan__tag">Bientôt</em>}</span>
                      </li>
                    ))}
                  </ul>
                  {commission && (
                    <p className="lp-plan__commission">
                      <strong>{commission}</strong>, frais compris
                    </p>
                  )}
                  <a
                    className={`lp-btn ${featured ? 'lp-btn--primary' : 'lp-btn--ghost'} lp-btn--block`}
                    href={`${REGISTER_URL}&plan=${encodeURIComponent(plan.code)}&interval=${annual && !free ? 'annual' : 'monthly'}`}
                  >
                    {free ? 'Créer mon école' : featured && trialDays > 0 ? 'Commencer l’essai' : 'Choisir ce forfait'}
                  </a>
                </article>
              )
            })}
          </div>
        )}
        {plans && plans.length > 0 && (
          <>
            <PlanComparison
              plans={plans}
              highlight="pro"
              onOpenChange={(open) => { if (open) setEstimatorOpen(false) }}
              action={(
              <button
                className="lp-pricing__calculator"
                type="button"
                aria-label={estimatorOpen ? 'Fermer le calculateur de forfait' : 'Calculer abonnement et commission selon le chiffre d’affaires'}
                aria-expanded={estimatorOpen}
                aria-controls="lp-sales-estimator"
                title="Calculer le coût mensuel. Le badge 10 % indique la commission du forfait Découverte."
                onClick={() => setEstimatorOpen((open) => !open)}
              >
                <Calculator size={18} aria-hidden="true" />
                <span className="lp-pricing__calculator-badge" aria-hidden="true">10%</span>
              </button>
              )}
            />

            <section
              className={`lp-sales-estimator${estimatorOpen ? ' is-open' : ''}`}
              id="lp-sales-estimator"
              aria-label="Estimation du coût des forfaits"
              aria-hidden={!estimatorOpen}
            >
              <div className="lp-sales-estimator__inner">
                <div className="lp-sales-estimator__heading">
                  <div>
                    <strong>Estimez votre coût mensuel</strong>
                    <p>Pour chaque forfait : commission sur le chiffre d’affaires + abonnement mensuel.</p>
                  </div>
                  <label>
                    Chiffre d’affaires mensuel ({plans[0].currency})
                    <input
                      type="number"
                      min="0"
                      step={plans[0].currency.toUpperCase() === 'XAF' ? '10000' : '0.01'}
                      inputMode="decimal"
                      value={monthlySales}
                      placeholder="Ex. 1 000 000"
                      onChange={(event) => setMonthlySales(event.target.value)}
                      aria-label={`Chiffre d’affaires mensuel estimé en ${plans[0].currency}`}
                    />
                    <small>Exemple prérempli : modifiez ce montant pour comparer.</small>
                  </label>
                </div>
                <div className="lp-sales-estimator__results">
                  {plans.map((plan) => {
                    const free = plan.monthly_price_cents === 0
                    const subscriptionAmount = monthlyEquivalent(plan, annual && !free)
                    const commissionRate = plan.sales_commission_bps
                    const commissionPercent = commissionRate === undefined
                      ? null
                      : (commissionRate / 100).toLocaleString(activeSchoolLocale(), { maximumFractionDigits: 2 })
                    const salesAmount = Math.max(0, Number(monthlySales) || 0)
                    const currencyScale = plan.currency.toUpperCase() === 'XAF' ? 1 : 100
                    const commissionAmount = commissionRate === undefined
                      ? null
                      : Math.round(salesAmount * currencyScale * commissionRate / 10_000)
                    const totalAmount = subscriptionAmount === null || commissionAmount === null
                      ? null
                      : subscriptionAmount + commissionAmount

                    return (
                      <article className="lp-sales-estimator__result" key={plan.id}>
                        <strong>{plan.name}</strong>
                        <span>Abonnement {annual && !free ? '(moyenne mensuelle)' : '(par mois)'} : {subscriptionAmount === null ? '-' : formatPrice(subscriptionAmount, plan.currency)}</span>
                        <span>Commission{commissionPercent ? ` (${commissionPercent} % du CA)` : ''} : {commissionAmount === null ? '-' : formatPrice(commissionAmount, plan.currency)}</span>
                        <b>{totalAmount === null ? 'Tarif indisponible' : `${formatPrice(totalAmount, plan.currency)} / mois`}</b>
                      </article>
                    )
                  })}
                </div>
                <small className="lp-sales-estimator__note">
                  Estimation indicative, frais de paiement compris et hors options. En annuel, l’abonnement est ramené au mois.
                </small>
              </div>
            </section>
          </>
        )}
      </div>
    </section>
  )
}

export default function LandingPage() {
  useReveal()
  const { user, loading: authLoading } = useAuth()
  const signedIn = Boolean(user && !authLoading && !readDemoState())
  // The read-only demo, when the platform has a demo school.
  const [demo, setDemo] = useState<DemoInfo | null>(null)
  useEffect(() => {
    getDemoInfo().then((info) => setDemo(info.enabled ? info : null)).catch(() => setDemo(null))
  }, [])

  return (
    <main className="lp">
      <LandingNavbar />

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
              <Link className="lp-btn lp-btn--primary" to={signedIn ? '/app' : REGISTER_URL}>Créer mon école <ArrowRight size={18} /></Link>
              {demo
                ? <DemoMenu info={demo} />
                : <a className="lp-btn lp-btn--ghost" href="#tarifs">Voir les tarifs</a>}
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
            <div className="lp-hero__notifications" aria-hidden="true">
              <div className="lp-chip lp-hero__notification lp-hero__notification--live"><span className="lp-dot" /> Cours en live · 14 présents</div>
              <div className="lp-chip lp-hero__notification lp-hero__notification--signup"><BellRing size={16} /> Nouvelle inscription · Design graphique</div>
              <div className="lp-chip lp-hero__notification lp-hero__notification--activity"><ClipboardCheck size={16} /> Activité mise à jour · Projet final</div>
            </div>
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
              <Icon size={34} strokeWidth={1.7} />
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
            <img
              className="lp-faq__support-image"
              src="/landing/faq-support.png"
              alt="Équipe d’accompagnement souriante, disponible pour aider les écoles"
              loading="lazy"
              decoding="async"
            />
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
            <BrandWordmark className="lp-brand__wordmark" />
          </a>
          <nav aria-label="Liens du pied de page">
            <a href="/mentions-legales">Mentions légales</a>
            <a href="/confidentialite">Politique de confidentialité</a>
            <a href="/cgv">CGV</a>
            <a href="/cgu">CGU</a>
          </nav>
          <p>© {new Date().getFullYear()} Académie des Créatifs</p>
        </div>
      </footer>
    </main>
  )
}
