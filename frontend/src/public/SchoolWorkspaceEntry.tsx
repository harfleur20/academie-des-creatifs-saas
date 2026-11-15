import { useEffect, useState } from 'react'
import { DoorOpen } from 'lucide-react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
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
  const navigate = useNavigate()
  const { user, loading: authLoading, signOut } = useAuth()
  const {
    organizations,
    activeOrganization,
    accessProfile,
    organizationsReady,
    profileLoading,
    profileError,
    refreshOrganizations,
    refreshAccessProfile,
    selectOrganization,
  } = useTenant()
  const [error, setError] = useState('')
  const membership = organizations.find((item) => item.id === school.organization_id)
  const profileReady = Boolean(
    accessProfile?.organization_id === school.organization_id && !profileLoading,
  )

  useEffect(() => {
    if (organizationsReady && membership && activeOrganization?.id !== school.organization_id) {
      selectOrganization(school.organization_id)
    }
  }, [organizationsReady, membership?.id, activeOrganization?.id, school.organization_id, selectOrganization])

  useEffect(() => {
    if (!user || organizationsReady || error) return
    const timer = window.setTimeout(() => {
      setError('La vérification de votre inscription prend trop de temps. Réessayez.')
    }, 10000)
    return () => window.clearTimeout(timer)
  }, [user?.id, organizationsReady, error])

  useEffect(() => {
    if (!user || !organizationsReady || !membership || profileReady || error) return
    const timer = window.setTimeout(() => {
      setError('L’ouverture de votre espace prend trop de temps. Réessayez.')
    }, 10000)
    return () => window.clearTimeout(timer)
  }, [user?.id, organizationsReady, membership?.id, profileReady, error])

  function retryWorkspace() {
    setError('')
    void refreshOrganizations()
      .then(() => refreshAccessProfile())
      .catch(() => setError('Impossible de charger votre espace. Réessayez.'))
  }

  function changeAccount() {
    signOut()
    const destination = '/school/' + school.slug + '/espace'
    navigate(
      '/login?school=' + encodeURIComponent(school.slug) + '&return=' + encodeURIComponent(destination),
      { replace: true },
    )
  }

  if (authLoading) return <main className="school-section"><div className="school-empty">Chargement de votre compte…</div></main>
  if (!user) {
    const destination = '/school/' + school.slug + '/espace'
    return <Navigate replace to={'/login?school=' + encodeURIComponent(school.slug) + '&return=' + encodeURIComponent(destination)} />
  }
  if (user.platform_role === 'super_admin') return <Navigate replace to="/admin" />
  if (!organizationsReady) return <main className="school-section"><div className="school-empty">Vérification de votre accès…</div></main>
  if (error) {
    return <main className="school-section"><div className="school-empty">{error} <button type="button" onClick={retryWorkspace}>Réessayer</button></div></main>
  }
  if (!membership && school.is_demo) return <Navigate replace to={'/school/' + school.slug} />
  if (!membership) return <main className="school-section school-workspace-entry">
    <div className="school-empty">
      <h1>Vous n’êtes pas encore inscrit à cette école</h1>
      <p>Le compte <strong>{user.email}</strong> n’a pas encore accès à {school.site_name || school.name}. Inscrivez-vous à une formation ou acceptez une invitation pour ouvrir votre espace.</p>
      <div className="school-workspace-entry-actions">
        <Link className="school-primary-link" to={'/school/' + school.slug + '/formations'}>Découvrir les formations</Link>
        <button className="school-account-switch-button" type="button" onClick={changeAccount}><span className="school-account-switch-icon"><DoorOpen size={18}/></span>Se déconnecter et changer de compte</button>
      </div>
    </div>
  </main>
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
