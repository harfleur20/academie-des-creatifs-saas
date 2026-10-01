import { useEffect, useState, type FormEvent } from 'react'
import {
  ArrowLeft,
  Building2,
  CalendarPlus,
  CheckCircle2,
  ShieldAlert,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { BrandLogo } from '../brand/BrandLogo'
import {
  ApiError,
  extendAdminTrial,
  getAdminOrganization,
  reactivateAdminOrganization,
  suspendAdminOrganization,
  type AdminOrganizationDetail,
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
}

export function AdminSchoolDetailPage() {
  const params = useParams()
  const organizationId = Number(params.schoolId)
  const [school, setSchool] = useState<AdminOrganizationDetail | null>(null)
  const [reason, setReason] = useState('')
  const [trialDays, setTrialDays] = useState(7)
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
          <span className="admin-school-detail-logo">
            {school.logo_url ? (
              <BrandLogo logoUrl={school.logo_url} alt={school.name} />
            ) : (
              <Building2 size={24} />
            )}
          </span>
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
          <span className="section-label">Abonnement</span>
          <h2>{school.subscription?.plan_name || 'Aucun forfait'}</h2>
          <dl className="admin-detail-list">
            <div><dt>Statut</dt><dd>{school.subscription?.status || '—'}</dd></div>
            <div><dt>Périodicité</dt><dd>{school.subscription?.billing_interval || '—'}</dd></div>
            <div><dt>Fin d’essai</dt><dd>{formatDate(school.subscription?.trial_ends_at || null)}</dd></div>
            <div><dt>Échéance</dt><dd>{formatDate(school.subscription?.current_period_end || null)}</dd></div>
            <div><dt>Grâce jusqu’au</dt><dd>{formatDate(school.subscription?.grace_period_ends_at || null)}</dd></div>
            <div><dt>Fournisseur</dt><dd>{school.subscription?.provider || 'Interne / essai'}</dd></div>
          </dl>
        </article>
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
