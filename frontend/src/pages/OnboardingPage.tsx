import { useEffect, useState, type FormEvent } from 'react'
import {
  ArrowRight,
  Check,
  Circle,
  GraduationCap,
  Settings2,
  Users,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import {
  ApiError,
  createFormation,
  getOnboardingStatus,
  type OnboardingStatus,
} from '../lib/api'

function slugify(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export function OnboardingPage() {
  const { activeOrganization } = useTenant()
  const [status, setStatus] = useState<OnboardingStatus | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function refresh() {
    if (!activeOrganization) return
    try {
      setStatus(await getOnboardingStatus())
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Impossible de charger votre progression.',
      )
    }
  }

  useEffect(() => {
    void refresh()
  }, [activeOrganization?.id])

  async function createFirstFormation(event: FormEvent) {
    event.preventDefault()
    const slug = slugify(title)
    if (!slug) return

    setSubmitting(true)
    setError('')
    try {
      await createFormation({
        slug,
        title: title.trim(),
        description: description.trim(),
      })
      setTitle('')
      setDescription('')
      await refresh()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Impossible de créer cette formation.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  if (!activeOrganization) {
    return <div className="page-state">Créez d’abord une école.</div>
  }

  if (!status && !error) {
    return <div className="page-state">Préparation de votre école…</div>
  }

  return (
    <main className="app-page onboarding-workspace">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Mise en route</span>
          <h1>Préparez {activeOrganization.name}</h1>
          <p>
            Suivez les étapes essentielles pour rendre votre école prête à accueillir
            votre équipe et vos premières formations.
          </p>
        </div>
        {status && (
          <span className="status-chip">
            {status.completed_steps}/{status.total_steps} étapes
          </span>
        )}
      </header>

      {error && <div className="form-error">{error}</div>}

      {status && (
        <>
          <section className="onboarding-progress-card">
            <div className="onboarding-progress-heading">
              <div>
                <span>Progression</span>
                <strong>{status.progress_percent}%</strong>
              </div>
              <small>
                {status.is_complete
                  ? 'Votre école est prête.'
                  : 'Vous pouvez quitter et revenir : la progression est recalculée automatiquement.'}
              </small>
            </div>
            <div className="onboarding-progress-track">
              <span style={{ width: `${status.progress_percent}%` }} />
            </div>
          </section>

          <section className="onboarding-step-list">
            {status.steps.map((step, index) => (
              <article
                className={`onboarding-step ${step.completed ? 'complete' : !step.available ? 'locked' : ''}`}
                key={step.key}
              >
                <span className="onboarding-step-number">
                  {step.completed ? <Check size={17} /> : index + 1}
                </span>
                <div>
                  <strong>{step.label}</strong>
                  <p>{step.description}</p>
                </div>
                {step.completed ? (
                  <span className="onboarding-done">Terminé</span>
                ) : !step.available ? (
                  <span className="onboarding-done">Après l’étape précédente</span>
                ) : step.key !== 'formation' ? (
                  <Link className="secondary-button compact-action" to={step.path}>
                    Continuer <ArrowRight size={14} />
                  </Link>
                ) : (
                  <span className="onboarding-current"><Circle size={10} /> À faire ici</span>
                )}
              </article>
            ))}
          </section>

          {!status.is_complete &&
            status.next_step?.key === 'formation' && (
              <form className="app-card onboarding-formation-form" onSubmit={createFirstFormation}>
                <div className="settings-section-heading">
                  <div>
                    <span className="section-label">Première formation</span>
                    <h2>Créez votre premier espace pédagogique</h2>
                    <p>
                      Le module complet de gestion des formations arrivera ensuite,
                      mais vous pouvez déjà créer la première formation de votre école.
                    </p>
                  </div>
                  <GraduationCap size={22} />
                </div>

                <label>
                  Nom de la formation
                  <input
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    minLength={2}
                    maxLength={255}
                    required
                    placeholder="Ex. Motion Design — Cohorte Octobre"
                  />
                </label>

                <label>
                  Description
                  <textarea
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    maxLength={5000}
                    placeholder="Une courte description de cette formation…"
                  />
                </label>

                <button className="primary-button" disabled={submitting}>
                  <GraduationCap size={16} />
                  {submitting ? 'Création…' : 'Créer la formation'}
                </button>
              </form>
            )}

          {status.is_complete && (
            <section className="onboarding-ready-card">
              <div>
                <span className="onboarding-ready-icon"><Check size={22} /></span>
                <div>
                  <span className="section-label">École prête</span>
                  <h2>La configuration essentielle est terminée.</h2>
                  <p>
                    Vous pouvez maintenant continuer à enrichir votre équipe,
                    votre identité et vos contenus.
                  </p>
                </div>
              </div>
              <Link className="primary-button" to="/app/manage">
                Ouvrir le tableau de bord <ArrowRight size={16} />
              </Link>
            </section>
          )}

          {!status.is_complete && status.next_step && status.next_step.key !== 'formation' && (
            <section className="onboarding-next-card">
              <span>
                {status.next_step.key === 'team' ? <Users size={19} /> : <Settings2 size={19} />}
              </span>
              <div>
                <small>Prochaine étape</small>
                <strong>{status.next_step.label}</strong>
              </div>
              <Link className="primary-button" to={status.next_step.path}>
                Continuer <ArrowRight size={16} />
              </Link>
            </section>
          )}
        </>
      )}
    </main>
  )
}
