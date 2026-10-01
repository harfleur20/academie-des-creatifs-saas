import { useState, type FormEvent } from 'react'
import { ArrowRight, Building2, GraduationCap, ShieldCheck, Users } from 'lucide-react'
import { createOrganization, setStoredOrganizationId } from '../lib/api'
import { useTenant } from '../app/TenantContext'

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
  const { activeOrganization, refreshOrganizations, loading } = useTenant()
  const [schoolName, setSchoolName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible de créer cette école.')
    } finally {
      setSubmitting(false)
    }
  }

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
          <p>Votre espace d’administration est prêt.</p>
        </div>
        <span className="status-chip">École active</span>
      </header>

      <div className="app-stat-grid">
        <article>
          <span className="stat-icon"><Users size={20} /></span>
          <small>Équipe & étudiants</small>
          <strong>Gérer les accès</strong>
          <p>Invitez vos collaborateurs et contrôlez leurs rôles.</p>
        </article>
        <article>
          <span className="stat-icon"><GraduationCap size={20} /></span>
          <small>Formations</small>
          <strong>Socle prêt</strong>
          <p>Le portage des sessions et contenus arrive dans le bloc suivant.</p>
        </article>
        <article>
          <span className="stat-icon"><ShieldCheck size={20} /></span>
          <small>Isolation</small>
          <strong>Multi-tenant actif</strong>
          <p>Les données de votre école sont filtrées côté serveur.</p>
        </article>
      </div>

      <section className="dashboard-callout">
        <div>
          <span>Prochaine étape</span>
          <h2>Construisez votre équipe pédagogique.</h2>
          <p>
            Ajoutez vos administrateurs, managers, professeurs et étudiants depuis
            l’espace Équipe & accès.
          </p>
        </div>
        <a className="primary-button" href="/app/team">
          Gérer mon équipe <ArrowRight size={17} />
        </a>
      </section>
    </main>
  )
}
