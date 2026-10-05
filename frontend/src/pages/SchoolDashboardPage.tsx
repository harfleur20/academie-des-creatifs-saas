import { useEffect, useState, type FormEvent } from 'react'
import { ArrowRight, BookOpen, Building2, CalendarDays, Clock3, GraduationCap, ShoppingCart, Users } from 'lucide-react'
import {
  createOrganization,
  getCommercialDashboard,
  getOnboardingStatus,
  listFormations,
  listMembers,
  setStoredOrganizationId,
  type CommercialDashboard,
  type FormationSummary,
  type Member,
  type OnboardingStatus,
} from '../lib/api'
import { useTenant } from '../app/TenantContext'
import { Link, useNavigate } from 'react-router-dom'

function slugify(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export function SchoolDashboardPage() {
  const navigate = useNavigate()
  const { activeOrganization, refreshOrganizations, loading } = useTenant()
  const [schoolName, setSchoolName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [onboarding, setOnboarding] = useState<OnboardingStatus | null>(null)
  const [formations, setFormations] = useState<FormationSummary[] | null>(null)
  const [members, setMembers] = useState<Member[] | null>(null)
  const [commerce, setCommerce] = useState<CommercialDashboard | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(true)
  const [summaryError, setSummaryError] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (!activeOrganization) {
      setOnboarding(null)
      setFormations(null)
      setMembers(null)
      setCommerce(null)
      setSummaryLoading(false)
      return
    }
    let active = true
    setOnboarding(null)
    setFormations(null)
    setMembers(null)
    setCommerce(null)
    setSummaryError(false)
    setSummaryLoading(true)
    void Promise.allSettled([getOnboardingStatus(), listFormations(), listMembers(), getCommercialDashboard()])
      .then(([onboardingResult, formationsResult, membersResult, commerceResult]) => {
        if (!active) return
        setOnboarding(onboardingResult.status === 'fulfilled' ? onboardingResult.value : null)
        setFormations(formationsResult.status === 'fulfilled' ? formationsResult.value : null)
        setMembers(membersResult.status === 'fulfilled' ? membersResult.value : null)
        setCommerce(commerceResult.status === 'fulfilled' ? commerceResult.value : null)
        setSummaryError([onboardingResult, formationsResult, membersResult, commerceResult].some((result) => result.status === 'rejected'))
        setSummaryLoading(false)
      })
    return () => { active = false }
  }, [activeOrganization?.id, refreshKey])

  async function createSchool(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const organization = await createOrganization({
        name: schoolName.trim(),
        slug: slugify(schoolName),
      })
      setStoredOrganizationId(organization.id)
      await refreshOrganizations()
      navigate('/app/manage/onboarding')
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
            ? { title: 'Invitez un enseignant', description: 'Confiez vos formations à un professeur pour animer les cours.', to: '/app/manage/teachers', label: 'Gérer les enseignants' }
            : activeStudents === 0
              ? { title: 'Faites connaître vos formations', description: 'Votre école est prête à accueillir ses premiers étudiants.', to: '/app/manage/site-public', label: 'Voir le site public' }
              : { title: 'Suivez la progression de l’école', description: 'Retrouvez les indicateurs pédagogiques et les résultats de vos programmes.', to: '/app/manage/performance', label: 'Voir la performance' }
    : null

  if (loading) {
    return <div className="page-state">Chargement de votre école…</div>
  }

  if (!activeOrganization) {
    return (
      <main className="app-page onboarding-page">
        <div className="onboarding-card">
          <span className="page-kicker">Première configuration</span>
          <div className="large-icon"><Building2 size={28} /></div>
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
              {!submitting && <ArrowRight size={17} />}
            </button>
          </form>
        </div>
      </main>
    )
  }

  return (
    <main className="app-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Tableau de bord</span>
          <h1>{activeOrganization.name}</h1>
          <p>{summaryText}</p>
        </div>
        <span className={`status-chip${activeOrganization.is_active ? '' : ' is-inactive'}`}>
          {activeOrganization.is_active ? 'École active' : 'École suspendue'}
        </span>
      </header>

      {summaryError && (
        <div className="dashboard-summary-error" role="alert">
          <span>Certaines données de l’école n’ont pas pu être chargées.</span>
          <button type="button" onClick={() => setRefreshKey((value) => value + 1)}>Actualiser</button>
        </div>
      )}

      <div className="dashboard-section-heading">
        <span className="section-label">Votre école en bref</span>
        <h2>Les chiffres à suivre</h2>
      </div>
      <div className="app-stat-grid">
        <article>
          <span className="stat-icon"><GraduationCap size={20} /></span>
          <small>Formations</small>
          <strong>{displayCount(formations?.length ?? null)}</strong>
          <p>{formations === null ? 'Données indisponibles.' : formations.length === 0 ? 'Créez votre premier programme.' : `${publishedCount} publiée(s) · ${draftCount} en préparation.`}</p>
          <Link className="dashboard-stat-link" to="/app/manage/formations">Voir les formations <ArrowRight size={15} /></Link>
        </article>
        <article>
          <span className="stat-icon"><Users size={20} /></span>
          <small>Étudiants actifs</small>
          <strong>{displayCount(activeStudents)}</strong>
          <p>{commerce === null ? 'Données indisponibles.' : activeStudents === 0 ? 'Aucun étudiant n’a encore rejoint l’école.' : 'Étudiants dont le parcours est actif.'}</p>
          <Link className="dashboard-stat-link" to="/app/manage/students">Voir les étudiants <ArrowRight size={15} /></Link>
        </article>
        <article>
          <span className="stat-icon"><CalendarDays size={20} /></span>
          <small>{hasGuidedFormation || !hasOnlineFormation ? 'Sessions' : 'Cours'}</small>
          <strong>{displayCount(hasGuidedFormation || !hasOnlineFormation ? sessionCount : courseCount)}</strong>
          <p>{formations === null ? 'Données indisponibles.' : hasGuidedFormation && sessionCount === 0 ? 'Ouvrez une session pour lancer les inscriptions guidées.' : hasOnlineFormation && !hasGuidedFormation ? 'Contenus de vos formations en ligne.' : `${displayCount(courseCount)} cours dans vos formations.`}</p>
          <Link className="dashboard-stat-link" to="/app/manage/formations">Voir les formations <ArrowRight size={15} /></Link>
        </article>
        <article>
          <span className="stat-icon"><BookOpen size={20} /></span>
          <small>Enseignants actifs</small>
          <strong>{displayCount(activeTeachers)}</strong>
          <p>{members === null ? 'Données indisponibles.' : activeTeachers === 0 ? 'Invitez un professeur pour animer vos cours.' : `${displayCount(activeTeam)} membre(s) actif(s) dans l’équipe.`}</p>
          <Link className="dashboard-stat-link" to="/app/manage/teachers">Voir les enseignants <ArrowRight size={15} /></Link>
        </article>
        <article>
          <span className="stat-icon"><ShoppingCart size={20} /></span>
          <small>Commandes</small>
          <strong>{displayCount(commerce?.order_count ?? null)}</strong>
          <p>{commerce === null ? 'Données indisponibles.' : commerce.order_count === 0 ? 'Les premières commandes apparaîtront ici.' : `${commerce.paid_order_count} commande(s) entièrement réglée(s).`}</p>
          <Link className="dashboard-stat-link" to="/app/manage/commerce">Voir les ventes <ArrowRight size={15} /></Link>
        </article>
        <article>
          <span className="stat-icon"><Clock3 size={20} /></span>
          <small>Échéances en retard</small>
          <strong>{displayCount(commerce?.late_installments ?? null)}</strong>
          <p>{commerce === null ? 'Données indisponibles.' : commerce.late_installments === 0 ? 'Aucun paiement en retard actuellement.' : 'Paiements à suivre auprès des étudiants.'}</p>
          <Link className="dashboard-stat-link" to="/app/manage/commerce">Suivre les paiements <ArrowRight size={15} /></Link>
        </article>
      </div>

      {onboarding && !onboarding.is_complete ? (
        <section className="dashboard-callout onboarding-dashboard-callout">
          <div>
            <span>Mise en route · {onboarding.completed_steps}/{onboarding.total_steps}</span>
            <h2>{onboarding.next_step?.label || 'Finalisez votre école'}</h2>
            <p>{onboarding.next_step?.description || 'Terminez les étapes de configuration de votre école.'}</p>
          </div>
          <Link className="primary-button" to={onboarding.next_step?.path || '/app/manage/onboarding'}>
            Continuer la configuration <ArrowRight size={17} />
          </Link>
        </section>
      ) : onboarding?.is_complete && nextAction ? (
        <section className="dashboard-callout">
          <div>
            <span>Prochaine étape</span>
            <h2>{nextAction.title}</h2>
            <p>{nextAction.description}</p>
          </div>
          <Link className="primary-button" to={nextAction.to}>
            {nextAction.label} <ArrowRight size={17} />
          </Link>
        </section>
      ) : null}
    </main>
  )
}
