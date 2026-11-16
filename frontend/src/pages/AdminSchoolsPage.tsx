import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useMemo, useState } from 'react'
import { ChevronRight, Search } from 'lucide-react'
import { Link } from 'react-router-dom'
import { SchoolLogo } from '../brand/SchoolLogo'
import {
  ApiError,
  listAdminOrganizations,
  type AdminOrganization,
} from '../lib/api'

function formatDate(value: string | null) {
  if (!value) return '-'
  return new Intl.DateTimeFormat(activeSchoolLocale(), {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value))
}

const subscriptionLabels: Record<string, string> = {
  trialing: 'Essai',
  active: 'Actif',
  past_due: 'En retard',
  suspended: 'Suspendu',
  cancelled: 'Résilié',
}

export function AdminSchoolsPage() {
  const [schools, setSchools] = useState<AdminOrganization[]>([])
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    listAdminOrganizations()
      .then(setSchools)
      .catch((err) => {
        setError(
          err instanceof ApiError
            ? err.message
            : 'Impossible de charger les écoles.',
        )
      })
  }, [])

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return schools

    return schools.filter((school) =>
      [
        school.name,
        school.slug,
        school.owner_name,
        school.owner_email,
        school.subscription?.plan_name,
      ]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(normalized)),
    )
  }, [schools, query])

  return (
    <main className="admin-page">
      <header className="admin-page-header admin-page-header-row">
        <div>
          <span className="page-kicker">Clients</span>
          <h1>Écoles</h1>
          <p>{schools.length} école{schools.length > 1 ? 's' : ''} enregistrée{schools.length > 1 ? 's' : ''}.</p>
        </div>

        <label className="admin-search">
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Rechercher une école…"
          />
        </label>
      </header>

      {error && <div className="form-error">{error}</div>}

      <section className="admin-card admin-school-table">
        <div className="admin-school-row admin-school-header">
          <span>École</span>
          <span>Propriétaire</span>
          <span>Forfait</span>
          <span>Utilisation</span>
          <span>Création</span>
          <span>Statut</span>
          <span></span>
        </div>

        {filtered.map((school) => (
          <div className="admin-school-row" key={school.id}>
            <div className="admin-school-name">
              <SchoolLogo logoUrl={school.logo_url} alt={school.name} className="admin-school-logo" />
              <span>
                <strong>{school.name}</strong>
                <small>
                  {school.subdomain || school.slug}
                  {school.verified_domain_count > 0
                    ? ` · ${school.verified_domain_count} domaine vérifié`
                    : ''}
                </small>
              </span>
            </div>

            <span className="admin-owner">
              <strong>{school.owner_name || '-'}</strong>
              <small>{school.owner_email || school.contact_email || '-'}</small>
            </span>

            <span>
              <strong>{school.subscription?.plan_name || 'Aucun'}</strong>
              <small>
                {school.subscription?.billing_interval === 'annual'
                  ? 'Annuel'
                  : school.subscription
                    ? 'Mensuel'
                    : '-'}
              </small>
            </span>

            <span className="admin-school-usage">
              <strong>{school.student_count} étu.</strong>
              <small>{school.teacher_count} prof. · {school.formation_count} form.</small>
            </span>
            <span>{formatDate(school.created_at)}</span>

            <span
              className={`admin-subscription-status ${
                school.subscription?.status || (school.is_active ? 'active' : 'suspended')
              }`}
            >
              {school.subscription
                ? subscriptionLabels[school.subscription.status]
                : school.is_active
                  ? 'École active'
                  : 'École suspendue'}
            </span>

            <Link
              className="admin-school-open"
              to={`/admin/schools/${school.id}`}
              aria-label={`Ouvrir ${school.name}`}
            >
              <ChevronRight size={16} />
            </Link>
          </div>
        ))}

        {filtered.length === 0 && (
          <div className="empty-row">Aucune école ne correspond à cette recherche.</div>
        )}
      </section>
    </main>
  )
}
