import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useTenant } from '../app/TenantContext'
import type { WorkspaceSpace } from '../lib/api'
import { usePublicSchool } from './SchoolPublicLayout'

const labels: Record<WorkspaceSpace, string> = {
  manage: 'Gestion de l’école',
  teacher: 'Espace professeur',
  student: 'Espace étudiant',
}

export function SchoolWorkspaceEntry() {
  const { school } = usePublicSchool()
  const { user, loading: authLoading } = useAuth()
  const {
    organizations,
    activeOrganization,
    accessProfile,
    loading,
    profileLoading,
    profileError,
    refreshOrganizations,
    refreshAccessProfile,
    selectOrganization,
  } = useTenant()
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')
  const membership = organizations.find((item) => item.id === school.organization_id)

  useEffect(() => {
    if (!user) return
    let active = true
    setReady(false)
    setError('')
    refreshOrganizations()
      .then(() => { if (active) setReady(true) })
      .catch(() => { if (active) setError('Impossible de charger vos écoles.') })
    return () => { active = false }
  }, [user?.id, refreshOrganizations])

  useEffect(() => {
    if (ready && membership && activeOrganization?.id !== school.organization_id) {
      selectOrganization(school.organization_id)
    }
  }, [ready, membership?.id, activeOrganization?.id, school.organization_id, selectOrganization])

  if (authLoading) return <main className="school-section"><div className="school-empty">Chargement de votre compte…</div></main>
  if (!user) {
    const destination = '/school/' + school.slug + '/espace'
    return <Navigate replace to={'/login?school=' + encodeURIComponent(school.slug) + '&return=' + encodeURIComponent(destination)} />
  }
  if (user.platform_role === 'super_admin') return <Navigate replace to="/admin" />
  if (error) {
    return <main className="school-section"><div className="school-empty">{error} <button type="button" onClick={() => { setError(''); void refreshOrganizations().then(() => setReady(true)).catch(() => setError('Impossible de charger vos écoles.')) }}>Réessayer</button></div></main>
  }
  if (!ready || loading) return <main className="school-section"><div className="school-empty">Recherche de votre espace…</div></main>
  if (!membership) return <Navigate replace to={'/school/' + school.slug} />
  if (activeOrganization?.id !== school.organization_id || profileLoading) {
    return <main className="school-section"><div className="school-empty">Ouverture de votre espace…</div></main>
  }
  if (!accessProfile || accessProfile.organization_id !== school.organization_id) {
    return <main className="school-section"><div className="school-empty">{profileError || 'Chargement de vos accès…'} <button type="button" onClick={() => void refreshAccessProfile()}>Réessayer</button></div></main>
  }
  if (accessProfile.spaces.length === 1) {
    return <Navigate replace to={'/app/' + accessProfile.spaces[0]} />
  }
  if (accessProfile.spaces.length === 0) {
    return <main className="school-section"><div className="school-empty">Aucun espace actif pour cette école. <Link to={'/school/' + school.slug}>Retour au site</Link></div></main>
  }

  return <main className="school-section school-workspace-entry">
    <header className="school-page-heading"><span className="school-kicker">{school.site_name}</span><h1>Choisissez votre espace</h1></header>
    <div className="school-workspace-choices">
      {accessProfile.spaces.map((space) => <Link key={space} to={'/app/' + space}>{labels[space]}</Link>)}
    </div>
  </main>
}
