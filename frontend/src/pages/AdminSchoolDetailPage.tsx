import { useEffect, useState, type FormEvent } from 'react'
import {
  ArrowLeft,
  CalendarPlus,
  CheckCircle2,
  Gift,
  LifeBuoy,
  ShieldAlert,
  XCircle,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { SchoolLogo } from '../brand/SchoolLogo'
import {
  ApiError,
  cancelAdminCommercialAccess,
  extendAdminTrial,
  getAdminOrganization,
  grantAdminCommercialAccess,
  listAdminPlans,
  reactivateAdminOrganization,
  startAdminSupportMode,
  suspendAdminOrganization,
  type AdminOrganizationDetail,
  type AdminPlan,
} from '../lib/api'

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

const actionLabels: Record<string, string> = {
  'organization.suspended': 'École suspendue',
  'organization.reactivated': 'École réactivée',
  'subscription.trial_extended': 'Essai prolongé',
  'commercial_access.granted': 'Accès commercial temporaire accordé',
  'commercial_access.cancelled': 'Accès commercial temporaire retiré',
  'support.started': 'Session support ouverte',
  'support.ended': 'Session support terminée',
}

export function AdminSchoolDetailPage() {
  const params = useParams()
  const organizationId = Number(params.schoolId)
  const [school, setSchool] = useState<AdminOrganizationDetail | null>(null)
  const [plans, setPlans] = useState<AdminPlan[]>([])
  const [reason, setReason] = useState('')
  const [trialDays, setTrialDays] = useState(7)
  const [commercialPlanId, setCommercialPlanId] = useState<number | null>(null)
  const [commercialDays, setCommercialDays] = useState(30)
  const [commercialReason, setCommercialReason] = useState('')
  const [supportReason, setSupportReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function loadSchool() {
    if (!Number.isInteger(organizationId)) return
    try {
      setSchool(await getAdminOrganization(organizationId))
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Impossible de charger cette école.',
      )
    }
  }

  useEffect(() => {
    void loadSchool()
    listAdminPlans()
      .then((items) => {
        const activePlans = items.filter((item) => item.is_active)
        setPlans(activePlans)
        setCommercialPlanId((current) => current ?? activePlans[0]?.id ?? null)
      })
      .catch(() => {
        // La fiche reste utilisable même si la liste des plans ne charge pas.
      })
  }, [organizationId])

  async function runStatusAction() {
    if (!school || reason.trim().length < 3) {
      setError('Indiquez un motif d’au moins 3 caractères.')
      return
    }
    setSubmitting(true)
    setError('')
    setMessage('')
    try {
      const updated = school.is_active
        ? await suspendAdminOrganization(school.id, reason.trim())
        : await reactivateAdminOrganization(school.id, reason.trim())
      setSchool(updated)
      setReason('')
      setMessage(
        updated.is_active
          ? 'École réactivée.'
          : 'École suspendue. Ses membres ne peuvent plus entrer dans cet espace.',
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Action impossible.')
    } finally {
      setSubmitting(false)
    }
  }

  async function extendTrial(event: FormEvent) {
    event.preventDefault()
    if (!school || reason.trim().length < 3) {
      setError('Indiquez un motif avant de prolonger l’essai.')
      return
    }
    setSubmitting(true)
    setError('')
    setMessage('')
    try {
      const updated = await extendAdminTrial(
        school.id,
        trialDays,
        reason.trim(),
      )
      setSchool(updated)
      setReason('')
      setMessage(`Essai prolongé de ${trialDays} jours.`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Prolongation impossible.')
    } finally {
      setSubmitting(false)
    }
  }

  async function grantCommercialAccess(event: FormEvent) {
    event.preventDefault()
    if (!school || !commercialPlanId) {
      setError('Choisissez un forfait temporaire.')
      return
    }
    if (commercialReason.trim().length < 3) {
      setError('Indiquez le motif de cette dérogation commerciale.')
      return
    }

    setSubmitting(true)
    setError('')
    setMessage('')
    try {
      const updated = await grantAdminCommercialAccess(
        school.id,
        commercialPlanId,
        commercialDays,
        commercialReason.trim(),
      )
      setSchool(updated)
      setCommercialReason('')
      setMessage(
        `Accès ${updated.commercial_access?.plan_name || 'temporaire'} accordé pour ${commercialDays} jours.`,
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Dérogation impossible.')
    } finally {
      setSubmitting(false)
    }
  }

  async function removeCommercialAccess() {
    if (!school || commercialReason.trim().length < 3) {
      setError('Indiquez le motif du retrait de l’accès temporaire.')
      return
    }

    setSubmitting(true)
    setError('')
    setMessage('')
    try {
      const updated = await cancelAdminCommercialAccess(
        school.id,
        commercialReason.trim(),
      )
      setSchool(updated)
      setCommercialReason('')
      setMessage('Accès commercial temporaire retiré.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Retrait impossible.')
    } finally {
      setSubmitting(false)
    }
  }

  async function enterSupportMode() {
    if (!school || supportReason.trim().length < 3) {
      setError('Indiquez la raison de la session support.')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      await startAdminSupportMode(school.id, supportReason.trim())
      window.location.assign('/app')
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Impossible d’ouvrir le mode support.',
      )
      setSubmitting(false)
    }
  }

  if (!school && !error) {
    return <div className="admin-page-state">Chargement de l’école…</div>
  }

  if (!school) {
    return (
      <main className="admin-page">
        <div className="form-error">{error}</div>
        <Link className="secondary-button" to="/admin/schools">
          <ArrowLeft size={16} /> Retour aux écoles
        </Link>
      </main>
    )
  }

  const trialExtendable =
    school.subscription?.trial_ends_at &&
    ['trialing', 'suspended'].includes(school.subscription.status)

  return (
    <main className="admin-page">
      <Link className="admin-back-link" to="/admin/schools">
        <ArrowLeft size={15} />
        Toutes les écoles
      </Link>

      <header className="admin-school-detail-header">
        <div className="admin-school-detail-title">
          <SchoolLogo logoUrl={school.logo_url} alt={school.name} className="admin-school-detail-logo" />
          <div>
            <span className="page-kicker">École cliente</span>
            <h1>{school.name}</h1>
            <p>{school.owner_email || school.contact_email || school.slug}</p>
          </div>
        </div>
        <span
          className={`admin-subscription-status ${
            school.is_active ? 'active' : 'suspended'
          }`}
        >
          {school.is_active ? 'École active' : 'École suspendue'}
        </span>
      </header>

      {message && <div className="form-success">{message}</div>}
      {error && <div className="form-error">{error}</div>}

      <section className="admin-detail-grid">
        <article className="admin-card">
          <span className="section-label">Compte</span>
          <h2>Informations</h2>
          <dl className="admin-detail-list">
            <div><dt>Propriétaire</dt><dd>{school.owner_name || '—'}</dd></div>
            <div><dt>Email</dt><dd>{school.owner_email || school.contact_email || '—'}</dd></div>
            <div><dt>Membres</dt><dd>{school.member_count}</dd></div>
            <div><dt>Sous-domaine</dt><dd>{school.subdomain || 'Non configuré'}</dd></div>
            <div><dt>Domaines vérifiés</dt><dd>{school.verified_domain_count}</dd></div>
            <div><dt>Créée le</dt><dd>{formatDate(school.created_at)}</dd></div>
          </dl>
        </article>

        <article className="admin-card">
          <span className="section-label">Abonnement réel</span>
          <h2>{school.subscription?.plan_name || 'Aucun forfait'}</h2>
          <dl className="admin-detail-list">
            <div><dt>Statut</dt><dd>{school.subscription?.status || '—'}</dd></div>
            <div><dt>Périodicité</dt><dd>{school.subscription?.billing_interval || '—'}</dd></div>
            <div><dt>Fin d’essai</dt><dd>{formatDate(school.subscription?.trial_ends_at || null)}</dd></div>
            <div><dt>Échéance</dt><dd>{formatDate(school.subscription?.current_period_end || null)}</dd></div>
            <div><dt>Grâce jusqu’au</dt><dd>{formatDate(school.subscription?.grace_period_ends_at || null)}</dd></div>
            <div><dt>Fournisseur</dt><dd>{school.subscription?.provider || 'Interne / essai'}</dd></div>
          </dl>

          {school.commercial_access && (
            <div className="commercial-access-summary">
              <Gift size={17} />
              <span>
                <strong>Accès temporaire : {school.commercial_access.plan_name}</strong>
                <small>Jusqu’au {formatDate(school.commercial_access.ends_at)}</small>
              </span>
            </div>
          )}
        </article>
      </section>

      <section className="admin-card admin-usage-card">
        <div className="admin-card-heading">
          <div>
            <span className="section-label">Utilisation & quotas</span>
            <h2>
              {school.effective_plan_name
                ? `Droits effectifs : ${school.effective_plan_name}`
                : 'Aucun droit actif'}
            </h2>
            <p>
              {school.effective_plan_source === 'commercial_access'
                ? 'Les limites ci-dessous viennent de la dérogation commerciale temporaire.'
                : 'Les limites ci-dessous viennent de l’abonnement actuellement actif.'}
            </p>
          </div>
        </div>

        <div className="admin-usage-grid">
          {school.usage_metrics.map((metric) => {
            const hasLimit = metric.enabled && metric.limit_value !== null
            const ratio = hasLimit && metric.limit_value
              ? Math.min(100, Math.round((metric.current_value / metric.limit_value) * 100))
              : metric.enabled
                ? 0
                : 100

            return (
              <article
                className={`admin-usage-item ${metric.over_limit ? 'over' : ''}`}
                key={metric.feature_key}
              >
                <div className="admin-usage-item-heading">
                  <span>{metric.label}</span>
                  <strong>
                    {metric.current_value}
                    {' / '}
                    {!metric.enabled
                      ? 'Non inclus'
                      : metric.limit_value === null
                        ? 'Illimité'
                        : metric.limit_value}
                  </strong>
                </div>
                <div className="admin-usage-progress">
                  <span style={{ width: `${ratio}%` }} />
                </div>
                <small>
                  {metric.over_limit
                    ? 'Quota dépassé ou fonctionnalité non incluse'
                    : !metric.enabled
                      ? 'Fonctionnalité non incluse'
                      : metric.limit_value === null
                        ? 'Sans limite numérique'
                        : `${Math.max(metric.limit_value - metric.current_value, 0)} restant(s)`}
                </small>
              </article>
            )
          })}
        </div>
      </section>

      <section className="admin-detail-grid">
        <article className="admin-card admin-action-card">
          <div>
            <span className="section-label">Administration</span>
            <h2>{school.is_active ? 'Suspendre l’école' : 'Réactiver l’école'}</h2>
            <p>
              {school.is_active
                ? 'La suspension bloque immédiatement l’accès tenant, sans supprimer les données.'
                : 'La réactivation rend de nouveau l’espace accessible. L’état de l’abonnement reste indépendant.'}
            </p>
          </div>

          <label>
            Motif obligatoire
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              maxLength={500}
              placeholder="Expliquez la raison de cette intervention…"
            />
          </label>

          <button
            className={school.is_active ? 'admin-danger-button' : 'primary-button'}
            onClick={() => void runStatusAction()}
            disabled={submitting}
          >
            {school.is_active ? <ShieldAlert size={16} /> : <CheckCircle2 size={16} />}
            {school.is_active ? 'Suspendre l’école' : 'Réactiver l’école'}
          </button>
        </article>

        <form className="admin-card admin-action-card" onSubmit={extendTrial}>
          <div>
            <span className="section-label">Essai</span>
            <h2>Prolonger la période d’essai</h2>
            <p>La prolongation est enregistrée dans le journal d’audit.</p>
          </div>

          <label>
            Nombre de jours
            <input
              type="number"
              min={1}
              max={365}
              value={trialDays}
              onChange={(event) => setTrialDays(Number(event.target.value))}
              disabled={!trialExtendable}
            />
          </label>

          <button
            className="secondary-button"
            disabled={submitting || !trialExtendable}
          >
            <CalendarPlus size={16} />
            {trialExtendable ? 'Prolonger l’essai' : 'Essai non prolongeable'}
          </button>
        </form>
      </section>

      <section className="admin-detail-grid">
        <form className="admin-card admin-action-card" onSubmit={grantCommercialAccess}>
          <div>
            <span className="section-label">Dérogation commerciale</span>
            <h2>Accès temporaire à un forfait</h2>
            <p>
              Donne temporairement les fonctionnalités du forfait choisi sans modifier
              l’abonnement réel, Tara ou les factures.
            </p>
          </div>

          <div className="admin-inline-fields">
            <label>
              Forfait temporaire
              <select
                value={commercialPlanId ?? ''}
                onChange={(event) => setCommercialPlanId(Number(event.target.value))}
              >
                {plans.map((plan) => (
                  <option key={plan.id} value={plan.id}>{plan.name}</option>
                ))}
              </select>
            </label>
            <label>
              Durée (jours)
              <input
                type="number"
                min={1}
                max={365}
                value={commercialDays}
                onChange={(event) => setCommercialDays(Number(event.target.value))}
              />
            </label>
          </div>

          <label>
            Motif obligatoire
            <textarea
              value={commercialReason}
              onChange={(event) => setCommercialReason(event.target.value)}
              maxLength={500}
              placeholder="Ex. Essai commercial Pro avant décision d’achat"
            />
          </label>

          <div className="admin-action-row">
            <button
              className="primary-button"
              disabled={submitting || !commercialPlanId}
            >
              <Gift size={16} />
              {school.commercial_access ? 'Remplacer l’accès temporaire' : 'Accorder l’accès temporaire'}
            </button>
            {school.commercial_access && (
              <button
                className="admin-danger-button"
                type="button"
                disabled={submitting}
                onClick={() => void removeCommercialAccess()}
              >
                <XCircle size={16} />
                Retirer
              </button>
            )}
          </div>
        </form>

        <article className="admin-card admin-action-card support-entry-card">
          <div>
            <span className="section-label">Support</span>
            <h2>Entrer dans l’école</h2>
            <p>
              Ouvre pendant 30 minutes une vue de cette école en lecture seule.
              Aucun mot de passe client n’est utilisé.
            </p>
          </div>

          <label>
            Raison de l’accès
            <textarea
              value={supportReason}
              onChange={(event) => setSupportReason(event.target.value)}
              maxLength={500}
              placeholder="Ex. Diagnostiquer l’affichage signalé par le propriétaire"
            />
          </label>

          <button
            className="secondary-button"
            type="button"
            disabled={submitting || !school.is_active}
            onClick={() => void enterSupportMode()}
          >
            <LifeBuoy size={16} />
            {school.is_active ? 'Entrer en mode support' : 'Réactivez d’abord l’école'}
          </button>
        </article>
      </section>

      <section className="admin-card admin-audit-card">
        <div className="admin-card-heading">
          <div>
            <span className="section-label">Journal d’audit</span>
            <h2>Interventions super-admin</h2>
          </div>
        </div>

        <div className="admin-audit-list">
          {school.audit_logs.map((log) => (
            <article key={log.id}>
              <span className="admin-audit-dot" />
              <div>
                <strong>{actionLabels[log.action] || log.action}</strong>
                <p>{log.reason}</p>
                <small>
                  {log.actor_name || log.actor_email || 'Administrateur supprimé'}
                  {' · '}
                  {formatDate(log.created_at)}
                </small>
              </div>
            </article>
          ))}

          {school.audit_logs.length === 0 && (
            <div className="empty-row">Aucune intervention administrative.</div>
          )}
        </div>
      </section>
    </main>
  )
}
