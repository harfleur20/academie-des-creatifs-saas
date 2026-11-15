import { useEffect, useState, type FormEvent } from 'react'
import { ChevronRight, BookOpen, CalendarDays, Clock3, CreditCard, GraduationCap, ShoppingCart, Store, UserPlus, Users } from 'lucide-react'
import { billingPathFor, clearPlanChoice, PAY_FIRST_PLANS, readPlanChoice } from '../lib/planChoice'
import {
  createOrganization,
  getCommercialDashboard,
  getCurrentSubscription,
  getOnboardingStatus,
  getSchoolPedagogyOverview,
  listFormations,
  listMembers,
  listPlans,
  setStoredOrganizationId,
  type CommercialDashboard,
  type FormationSummary,
  type Member,
  type OnboardingStatus,
  type Plan,
  type SchoolPedagogyOverview,
  type Subscription,
} from '../lib/api'
import { ChartCanvas } from '../components/ChartCanvas'
import { DashboardActivityFeed } from '../components/DashboardActivityFeed'
import { useTenant } from '../app/TenantContext'
import { useAuth } from '../auth/AuthContext'
import { Link, useNavigate } from 'react-router-dom'
import '../statistics.css'

function slugify(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function firstName(value?: string | null) {
  return (value || '').trim().split(/\s+/)[0] || 'vous'
}

function daysUntil(value: string | null | undefined) {
  if (!value) return null
  const diff = new Date(value).getTime() - Date.now()
  return Math.max(0, Math.ceil(diff / 86_400_000))
}

function planSortPrice(plan: Plan) {
  return plan.monthly_price_cents ?? plan.annual_price_cents ?? Number.MAX_SAFE_INTEGER
}

const subscriptionStatusLabels: Record<Subscription['status'], string> = {
  trialing: 'Période d’essai',
  active: 'Abonnement actif',
  past_due: 'Paiement en retard',
  suspended: 'Abonnement suspendu',
  cancelled: 'Abonnement résilié',
}

type DashboardSummaryCache = {
  onboarding: OnboardingStatus | null
  formations: FormationSummary[] | null
  members: Member[] | null
  commerce: CommercialDashboard | null
  pedagogy: SchoolPedagogyOverview | null
  subscription: Subscription | null
  plans: Plan[]
}

const dashboardSummaryCache = new Map<number, DashboardSummaryCache>()
const DASHBOARD_CACHE_PREFIX = 'academie_saas_dashboard_summary_'

function readDashboardSummaryCache(organizationId: number) {
  const memory = dashboardSummaryCache.get(organizationId)
  if (memory) return memory
  try {
    const raw = sessionStorage.getItem(`${DASHBOARD_CACHE_PREFIX}${organizationId}`)
    if (!raw) return undefined
    const parsed = JSON.parse(raw) as DashboardSummaryCache
    dashboardSummaryCache.set(organizationId, parsed)
    return parsed
  } catch {
    return undefined
  }
}

function writeDashboardSummaryCache(organizationId: number, summary: DashboardSummaryCache) {
  dashboardSummaryCache.set(organizationId, summary)
  try {
    sessionStorage.setItem(`${DASHBOARD_CACHE_PREFIX}${organizationId}`, JSON.stringify(summary))
  } catch {
    // Memory cache remains available if session storage is unavailable.
  }
}

export function SchoolDashboardPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const { activeOrganization, refreshOrganizations, loading } = useTenant()
  const cachedSummary = activeOrganization ? readDashboardSummaryCache(activeOrganization.id) : undefined
  const [schoolName, setSchoolName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [onboarding, setOnboarding] = useState<OnboardingStatus | null>(cachedSummary?.onboarding ?? null)
  const [formations, setFormations] = useState<FormationSummary[] | null>(cachedSummary?.formations ?? null)
  const [members, setMembers] = useState<Member[] | null>(cachedSummary?.members ?? null)
  const [commerce, setCommerce] = useState<CommercialDashboard | null>(cachedSummary?.commerce ?? null)
  const [pedagogy, setPedagogy] = useState<SchoolPedagogyOverview | null>(cachedSummary?.pedagogy ?? null)
  const [subscription, setSubscription] = useState<Subscription | null>(cachedSummary?.subscription ?? null)
  const [plans, setPlans] = useState<Plan[]>(cachedSummary?.plans ?? [])
  const [summaryLoading, setSummaryLoading] = useState(!cachedSummary)
  const [summaryError, setSummaryError] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (!activeOrganization) {
      setOnboarding(null)
      setFormations(null)
      setMembers(null)
      setCommerce(null)
      setPedagogy(null)
      setSubscription(null)
      setPlans([])
      setSummaryLoading(false)
      return
    }

    let active = true
    const cached = readDashboardSummaryCache(activeOrganization.id)
    if (cached) {
      setOnboarding(cached.onboarding)
      setFormations(cached.formations)
      setMembers(cached.members)
      setCommerce(cached.commerce)
      setPedagogy(cached.pedagogy)
      setSubscription(cached.subscription)
      setPlans(cached.plans)
      setSummaryLoading(false)
    } else {
      setOnboarding(null)
      setFormations(null)
      setMembers(null)
      setCommerce(null)
      setPedagogy(null)
      setSubscription(null)
      setPlans([])
      setSummaryLoading(true)
    }
    setSummaryError(false)

    void Promise.allSettled([
      getOnboardingStatus(),
      listFormations(),
      listMembers(),
      getCommercialDashboard(),
      getSchoolPedagogyOverview(),
      getCurrentSubscription(),
      listPlans(),
    ])
      .then(([onboardingResult, formationsResult, membersResult, commerceResult, pedagogyResult, subscriptionResult, plansResult]) => {
        if (!active) return
        const nextSummary: DashboardSummaryCache = {
          onboarding: onboardingResult.status === 'fulfilled' ? onboardingResult.value : cached?.onboarding ?? null,
          formations: formationsResult.status === 'fulfilled' ? formationsResult.value : cached?.formations ?? null,
          members: membersResult.status === 'fulfilled' ? membersResult.value : cached?.members ?? null,
          commerce: commerceResult.status === 'fulfilled' ? commerceResult.value : cached?.commerce ?? null,
          pedagogy: pedagogyResult.status === 'fulfilled' ? pedagogyResult.value : cached?.pedagogy ?? null,
          subscription: subscriptionResult.status === 'fulfilled' ? subscriptionResult.value : cached?.subscription ?? null,
          plans: plansResult.status === 'fulfilled' ? plansResult.value : cached?.plans ?? [],
        }
        writeDashboardSummaryCache(activeOrganization.id, nextSummary)
        setOnboarding(nextSummary.onboarding)
        setFormations(nextSummary.formations)
        setMembers(nextSummary.members)
        setCommerce(nextSummary.commerce)
        setPedagogy(nextSummary.pedagogy)
        setSubscription(nextSummary.subscription)
        setPlans(nextSummary.plans)
        setSummaryError([onboardingResult, formationsResult, membersResult, commerceResult, pedagogyResult].some((result) => result.status === 'rejected'))
        setSummaryLoading(false)
      })
    return () => { active = false }
  }, [activeOrganization?.id, refreshKey])

  async function createSchool(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const choice = readPlanChoice()
      const organization = await createOrganization({
        name: schoolName.trim(),
        slug: slugify(schoolName),
        ...(choice ? { plan_code: choice.plan, billing_interval: choice.interval } : {}),
      })
      setStoredOrganizationId(organization.id)
      await refreshOrganizations()
      // Every new school starts with the trial; a school that picked Starter or Business sees it next.
      if (choice && PAY_FIRST_PLANS.has(choice.plan)) {
        navigate(billingPathFor(choice))
      } else {
        clearPlanChoice()
        navigate('/app/manage/onboarding?essai=1')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible de créer cette école.')
    } finally {
      setSubmitting(false)
    }
  }

  const activeStudents = commerce?.active_students ?? null
  const activeTeachers = members?.filter((member) =>
    member.status === 'active' && (member.role === 'teacher' || member.roles.some((role) => role.role === 'teacher')),
  ).length ?? null
  const activeTeam = members?.filter((member) => member.status === 'active' && member.role !== 'student').length ?? null
  const publishedCount = formations?.filter((formation) => formation.status === 'published').length ?? null
  const draftCount = formations?.filter((formation) => formation.status === 'draft').length ?? null
  const sessionCount = formations?.reduce((sum, formation) => sum + formation.session_count, 0) ?? null
  const hasGuidedFormation = formations?.some((formation) => formation.format_type !== 'ligne') ?? false
  const hasOnlineFormation = formations?.some((formation) => formation.format_type === 'ligne') ?? false
  const courseCount = formations?.reduce((sum, formation) => sum + formation.course_count, 0) ?? null
  const displayCount = (count: number | null) => count === null ? '—' : count.toLocaleString('fr-FR')
  const unpublishedCount = formations ? Math.max(0, formations.length - (publishedCount ?? 0)) : 0
  const unpaidOrderCount = commerce ? Math.max(0, commerce.order_count - commerce.paid_order_count) : 0
  const sessionsToWatch = pedagogy
    ? pedagogy.sessions.filter((row) => row.at_risk_count > 0 || row.pending_reviews_count > 0).length
    : null
  const schoolAlerts = pedagogy || commerce
    ? (pedagogy?.at_risk_students ?? 0) + (commerce?.late_installments ?? 0) + (sessionsToWatch ?? 0)
    : null
  const paidOrderRate = commerce
    ? commerce.order_count > 0
      ? Math.round((commerce.paid_order_count / commerce.order_count) * 100)
      : 0
    : null

  const publicPlans = plans.filter((plan) => plan.is_public).sort((a, b) => planSortPrice(a) - planSortPrice(b))
  const currentPlanPrice = subscription ? planSortPrice(subscription.plan) : null
  const upgradePlan = subscription && currentPlanPrice !== null
    ? publicPlans.find((plan) => plan.code !== subscription.plan.code && planSortPrice(plan) > currentPlanPrice)
    : publicPlans[0]
  const subscriptionDeadline = subscription?.status === 'trialing'
    ? subscription.trial_ends_at
    : subscription?.status === 'past_due'
      ? subscription.grace_period_ends_at || subscription.current_period_end
      : subscription?.current_period_end
  const subscriptionDays = daysUntil(subscriptionDeadline)
  const providerLabel = subscription?.provider
    ? subscription.provider.toLowerCase().includes('tara') ? 'TaraMoney' : subscription.provider
    : 'Paiement à configurer'
  const billingIntervalLabel = subscription?.billing_interval === 'annual' ? 'Annuel' : 'Mensuel'
  const subscriptionPeriodText = !subscription
    ? 'Aucune offre souscrite pour le moment.'
    : subscription.status === 'trialing'
      ? subscriptionDays === null ? 'Essai en cours.' : `${subscriptionDays} jour${subscriptionDays > 1 ? 's' : ''} d’essai restant${subscriptionDays > 1 ? 's' : ''}.`
      : subscription.status === 'past_due'
        ? subscriptionDays === null ? 'Paiement à régulariser.' : `${subscriptionDays} jour${subscriptionDays > 1 ? 's' : ''} avant suspension.`
        : subscription.status === 'suspended'
          ? 'Régularisez votre abonnement pour rétablir tous les accès.'
          : subscription.status === 'cancelled'
            ? 'Votre abonnement est terminé.'
            : subscription.cancel_at_period_end
              ? subscriptionDays === null ? 'Résiliation programmée.' : `Se termine dans ${subscriptionDays} jour${subscriptionDays > 1 ? 's' : ''}.`
              : subscriptionDays === null ? 'Période en cours.' : `Renouvellement dans ${subscriptionDays} jour${subscriptionDays > 1 ? 's' : ''}.`
  const subscriptionActionLabel = !subscription
    ? 'Voir les offres'
    : ['past_due', 'suspended'].includes(subscription.status)
      ? 'Régulariser'
      : upgradePlan
        ? `Passer à ${upgradePlan.name}`
        : 'Gérer l’abonnement'

  const summaryText = summaryLoading
    ? 'Préparation du résumé de votre école…'
    : formations === null || commerce === null
      ? 'Une partie du résumé est momentanément indisponible.'
      : formations.length === 0
        ? 'Créez votre première formation pour commencer à construire votre école.'
        : publishedCount === 0
          ? 'Vos formations sont en préparation. Publiez-en une pour ouvrir votre catalogue.'
          : `${displayCount(activeStudents)} étudiant(s) actif(s) · ${displayCount(publishedCount)} formation(s) publiée(s)${hasGuidedFormation ? ` · ${displayCount(sessionCount)} session(s)` : ''}.`

  const nextAction = formations && members && commerce
    ? formations.length === 0
      ? { title: 'Créez votre première formation', description: 'Ajoutez un programme pour préparer les cours et les inscriptions.', to: '/app/manage/formations', label: 'Créer une formation' }
      : publishedCount === 0
        ? { title: 'Préparez votre catalogue', description: 'Vos formations existent déjà. Finalisez-en une et publiez-la sur le site de l’école.', to: '/app/manage/formations', label: 'Voir les formations' }
        : hasGuidedFormation && sessionCount === 0
          ? { title: 'Ouvrez une première session', description: 'Une session permet de planifier la formation et d’accueillir les étudiants.', to: '/app/manage/formations', label: 'Gérer les sessions' }
          : activeTeachers === 0
            ? { title: 'Invitez un enseignant', description: 'Confiez vos formations à un professeur pour animer vos cours.', to: '/app/manage/teachers', label: 'Gérer les enseignants' }
            : activeStudents === 0
              ? { title: 'Faites connaître vos formations', description: 'Votre école est prête à accueillir ses premiers étudiants.', to: '/app/manage/site-public', label: 'Voir le site public' }
              : { title: 'Supervisez l’activité de l’école', description: 'Contrôlez les sessions, les alertes et l’activité commerciale depuis la vue de pilotage.', to: '/app/manage/performance', label: 'Voir les statistiques' }
    : null

  if (loading) {
    return <div className="page-state">Chargement de votre école…</div>
  }

  if (!activeOrganization) {
    return (
      <main className="app-page onboarding-page">
        <div className="onboarding-card">
          <span className="page-kicker">Première configuration</span>
          <div className="large-icon"><span className="onboarding-school-logo" role="img" aria-label="Logo de l’Académie des Créatifs" /></div>
          <h1>Créez votre première école</h1>
          <p>
            Ce sera votre espace isolé. Vous pourrez ensuite inviter vos administrateurs,
            professeurs et étudiants.
          </p>

          <form onSubmit={createSchool}>
            <label>
              Nom de l’école
              <input
                value={schoolName}
                onChange={(event) => setSchoolName(event.target.value)}
                minLength={2}
                maxLength={180}
                required
                placeholder="Ex. Studio Créatif Academy"
              />
            </label>
            {error && <div className="form-error">{error}</div>}
            <button className="primary-button full" disabled={submitting}>
              {submitting ? 'Création…' : 'Créer mon école'}
              {!submitting && <ChevronRight size={17} />}
            </button>
          </form>
        </div>
      </main>
    )
  }

  return (
    <main className="app-page owner-dashboard-page">
      <header className="owner-dashboard-heading">
        <span className="page-kicker">Tableau de bord</span>
        <div className="owner-dashboard-title-row">
          <h1>Vue d’ensemble</h1>
          {summaryLoading && !subscription ? (
            <div className="owner-dashboard-subscription-card dashboard-subscription-loading" aria-label="Chargement de l’abonnement">
              <div className="dashboard-subscription-skeleton" />
            </div>
          ) : (
            <Link
              to="/app/manage/billing"
              className={`owner-dashboard-subscription-card${subscription ? ` is-${subscription.status}` : ' is-empty'}`}
            >
              <span className="owner-dashboard-subscription-icon"><CreditCard size={21} /></span>
              <span className="owner-dashboard-subscription-copy">
                <span className="owner-dashboard-subscription-plan">
                  {subscription ? subscription.plan.name : 'Votre abonnement'}
                </span>
                <strong>{subscription ? subscriptionStatusLabels[subscription.status] : 'Choisissez une offre'}</strong>
                <small>
                  {subscription ? `${billingIntervalLabel} · ${providerLabel} · ${subscriptionPeriodText}` : subscriptionPeriodText}
                </small>
              </span>
              <span className="owner-dashboard-subscription-action">
                {subscriptionActionLabel} <ChevronRight size={14} />
              </span>
            </Link>
          )}
        </div>
      </header>

      {summaryError && (
        <div className="dashboard-summary-error" role="alert">
          <span>Certaines données de l’école n’ont pas pu être chargées.</span>
          <button type="button" onClick={() => setRefreshKey((value) => value + 1)}>Actualiser</button>
        </div>
      )}

      <section className="owner-dashboard-overview">
        <div className="owner-dashboard-main">
          <article className="owner-dashboard-welcome">
            <span className="section-label">Aujourd’hui</span>
            <h2>Bonjour {firstName(user?.full_name)} 👋</h2>
            <p>{summaryText}</p>
            <strong className="owner-dashboard-school-name">{activeOrganization.name}</strong>

            <div className="owner-dashboard-mini-stats">
              <div><small>Étudiants actifs</small><strong>{displayCount(activeStudents)}</strong></div>
              <div><small>{hasGuidedFormation || !hasOnlineFormation ? 'Sessions' : 'Cours'}</small><strong>{displayCount(hasGuidedFormation || !hasOnlineFormation ? sessionCount : courseCount)}</strong></div>
              <div className={(commerce?.late_installments ?? 0) > 0 ? 'is-alert' : ''}><small>Paiements en retard</small><strong>{displayCount(commerce?.late_installments ?? null)}</strong></div>
            </div>

            <div className="owner-dashboard-quick-actions">
              <Link className="primary-button" to="/app/manage/formations">Créer une formation <ChevronRight size={16} /></Link>
              <Link className="owner-dashboard-action" to="/app/manage/teachers"><UserPlus size={16} /> Inviter un enseignant</Link>
              <Link className="owner-dashboard-action" to="/app/manage/site-public"><Store size={16} /> Voir le site</Link>
            </div>
          </article>

          <div className="owner-dashboard-rail-metrics">
            <Link to="/app/manage/performance" className={(sessionsToWatch ?? 0) > 0 ? 'is-alert' : ''}><CalendarDays size={18} /><span><strong>{displayCount(sessionsToWatch)}</strong><small>sessions à surveiller</small></span></Link>
            <Link to="/app/manage/formations" className={(draftCount ?? 0) > 0 ? 'is-alert' : ''}><GraduationCap size={18} /><span><strong>{displayCount(draftCount)}</strong><small>formations à finaliser</small></span></Link>
            <Link to="/app/manage/performance" className={(schoolAlerts ?? 0) > 0 ? 'is-alert' : ''}><Clock3 size={18} /><span><strong>{displayCount(schoolAlerts)}</strong><small>alertes école</small></span></Link>
            <Link to="/app/manage/commerce" className={(commerce?.late_installments ?? 0) > 0 ? 'is-alert' : ''}><ShoppingCart size={18} /><span><strong>{paidOrderRate === null ? '—' : `${paidOrderRate}%`}</strong><small>commandes réglées</small></span></Link>
          </div>

          <section className="owner-dashboard-stats-column">
            <div className="dashboard-section-heading owner-dashboard-stats-heading">
              <span className="section-label">Votre école en bref</span>
              <h2>Les chiffres à suivre</h2>
            </div>
            <div className="app-stat-grid">
              <article>
                <span className="stat-icon"><GraduationCap size={20} /></span>
                <small>Formations</small>
                <strong>{displayCount(formations?.length ?? null)}</strong>
                <p>{formations === null ? 'Données indisponibles.' : formations.length === 0 ? 'Créez votre premier programme.' : `${publishedCount} publiée(s) · ${draftCount} en préparation.`}</p>
                <Link className="dashboard-stat-link" to="/app/manage/formations">Voir les formations <ChevronRight size={15} /></Link>
              </article>
              <article>
                <span className="stat-icon"><Users size={20} /></span>
                <small>Étudiants actifs</small>
                <strong>{displayCount(activeStudents)}</strong>
                <p>{commerce === null ? 'Données indisponibles.' : activeStudents === 0 ? 'Aucun étudiant n’a encore rejoint l’école.' : 'Étudiants dont le parcours est actif.'}</p>
                <Link className="dashboard-stat-link" to="/app/manage/students">Voir les étudiants <ChevronRight size={15} /></Link>
              </article>
              <article>
                <span className="stat-icon"><CalendarDays size={20} /></span>
                <small>{hasGuidedFormation || !hasOnlineFormation ? 'Sessions' : 'Cours'}</small>
                <strong>{displayCount(hasGuidedFormation || !hasOnlineFormation ? sessionCount : courseCount)}</strong>
                <p>{formations === null ? 'Données indisponibles.' : hasGuidedFormation && sessionCount === 0 ? 'Ouvrez une session pour lancer les inscriptions guidées.' : hasOnlineFormation && !hasGuidedFormation ? 'Contenus de vos formations en ligne.' : `${displayCount(courseCount)} cours dans vos formations.`}</p>
                <Link className="dashboard-stat-link" to="/app/manage/formations">Voir les formations <ChevronRight size={15} /></Link>
              </article>
              <article>
                <span className="stat-icon"><BookOpen size={20} /></span>
                <small>Enseignants actifs</small>
                <strong>{displayCount(activeTeachers)}</strong>
                <p>{members === null ? 'Données indisponibles.' : activeTeachers === 0 ? 'Invitez un professeur pour animer vos cours.' : `${displayCount(activeTeam)} membre(s) actif(s) dans l’équipe.`}</p>
                <Link className="dashboard-stat-link" to="/app/manage/teachers">Voir les enseignants <ChevronRight size={15} /></Link>
              </article>
              <article>
                <span className="stat-icon"><ShoppingCart size={20} /></span>
                <small>Commandes</small>
                <strong>{displayCount(commerce?.order_count ?? null)}</strong>
                <p>{commerce === null ? 'Données indisponibles.' : commerce.order_count === 0 ? 'Les premières commandes apparaîtront ici.' : `${commerce.paid_order_count} commande(s) entièrement réglée(s).`}</p>
                <Link className="dashboard-stat-link" to="/app/manage/commerce">Voir les ventes <ChevronRight size={15} /></Link>
              </article>
              <article>
                <span className="stat-icon"><Clock3 size={20} /></span>
                <small>Échéances en retard</small>
                <strong>{displayCount(commerce?.late_installments ?? null)}</strong>
                <p>{commerce === null ? 'Données indisponibles.' : commerce.late_installments === 0 ? 'Aucun paiement en retard actuellement.' : 'Paiements à suivre auprès des étudiants.'}</p>
                <Link className="dashboard-stat-link" to="/app/manage/commerce">Suivre les paiements <ChevronRight size={15} /></Link>
              </article>
            </div>
            {((formations && formations.length > 0) || (commerce && commerce.order_count > 0) || (onboarding && !onboarding.is_complete) || nextAction) && (
              <section className="owner-dashboard-stats-support" aria-label="Statistiques et prochaine étape">
                {formations && formations.length > 0 && (
                  <Link to="/app/manage/performance" className="dashboard-mini-chart-link">
                    <div className="dashboard-mini-chart-head"><span>Publication des formations</span><strong>Statistiques →</strong></div>
                    <ChartCanvas
                      type="doughnut"
                      compact
                      height={78}
                      labels={['Publiées', 'Autres']}
                      datasets={[{ label: 'Formations', data: [publishedCount ?? 0, unpublishedCount] }]}
                    />
                  </Link>
                )}
                {commerce && commerce.order_count > 0 && (
                  <Link to="/app/manage/performance" className="dashboard-mini-chart-link">
                    <div className="dashboard-mini-chart-head"><span>Commandes réglées</span><strong>{commerce.paid_order_count}/{commerce.order_count}</strong></div>
                    <ChartCanvas
                      type="doughnut"
                      compact
                      height={78}
                      labels={['Réglées', 'À régler']}
                      datasets={[{ label: 'Commandes', data: [commerce.paid_order_count, unpaidOrderCount] }]}
                    />
                  </Link>
                )}
                {(onboarding && !onboarding.is_complete) ? (
                  <section className="owner-dashboard-next-card">
                    <span className="section-label">Mise en route</span>
                    <h3>{onboarding.next_step?.label || 'Finalisez votre école'}</h3>
                    <p>{onboarding.next_step?.description || 'Terminez les étapes de configuration de votre école.'}</p>
                    <div className="owner-dashboard-progress"><span style={{ width: `${Math.min(100, Math.round((onboarding.completed_steps / Math.max(1, onboarding.total_steps)) * 100))}%` }} /></div>
                    <small>{onboarding.completed_steps}/{onboarding.total_steps} étapes terminées</small>
                    <Link to={onboarding.next_step?.path || '/app/manage/onboarding'}>Continuer <ChevronRight size={15} /></Link>
                  </section>
                ) : nextAction ? (
                  <section className="owner-dashboard-next-card">
                    <span className="section-label">Prochaine étape</span>
                    <h3>{nextAction.title}</h3>
                    <p>{nextAction.description}</p>
                    <Link to={nextAction.to}>{nextAction.label} <ChevronRight size={15} /></Link>
                  </section>
                ) : null}
              </section>
            )}
          </section>
        </div>

        <aside className="owner-dashboard-rail">
          <DashboardActivityFeed />

          <section className="owner-dashboard-priority-card">
            <div className="owner-dashboard-card-title">
              <span>À surveiller</span>
              <small>Priorités de l’école</small>
            </div>
            <Link to="/app/manage/commerce" className={(commerce?.late_installments ?? 0) > 0 ? 'is-alert' : ''}>
              <span className="owner-dashboard-priority-icon"><Clock3 size={18} /></span>
              <span><strong>{displayCount(commerce?.late_installments ?? null)} échéance(s)</strong><small>paiement(s) en retard</small></span>
              <ChevronRight size={15} />
            </Link>
            <Link to="/app/manage/formations">
              <span className="owner-dashboard-priority-icon"><CalendarDays size={18} /></span>
              <span><strong>{displayCount(sessionCount)} session(s)</strong><small>dans vos formations</small></span>
              <ChevronRight size={15} />
            </Link>
            <Link to="/app/manage/students">
              <span className="owner-dashboard-priority-icon"><Users size={18} /></span>
              <span><strong>{displayCount(activeStudents)} étudiant(s)</strong><small>actuellement actifs</small></span>
              <ChevronRight size={15} />
            </Link>
          </section>

        </aside>
      </section>
    </main>
  )
}
