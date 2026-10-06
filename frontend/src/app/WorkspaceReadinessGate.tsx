import { useEffect, useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useTenant } from './TenantContext'
import {
  getSchoolCharter,
  getTeacherProfessionalProfile,
} from '../onboarding/workspaceOnboardingApi'

function GateError({ retry }: { retry: () => void }) {
  return (
    <div className="app-loading workspace-readiness-error">
      <div>
        <strong>Impossible de vérifier les informations requises.</strong>
        <button type="button" className="secondary-button" onClick={retry}>Réessayer</button>
      </div>
    </div>
  )
}

export function RequireTeacherReady({ children }: { children: ReactNode }) {
  const { activeOrganization } = useTenant()
  const location = useLocation()
  const [state, setState] = useState<'loading' | 'ready' | 'setup' | 'error'>('loading')
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (!activeOrganization) return
    let active = true
    setState('loading')
    Promise.all([
      getTeacherProfessionalProfile(),
      getSchoolCharter('teacher'),
    ])
      .then(([profile, charter]) => {
        if (!active) return
        const charterReady = !charter.is_enabled || charter.accepted_current_version
        setState(profile.is_complete && charterReady ? 'ready' : 'setup')
      })
      .catch(() => {
        if (active) setState('error')
      })
    return () => { active = false }
  }, [activeOrganization?.id, location.pathname, refreshKey])

  if (state === 'loading') return <div className="app-loading">Vérification de votre profil enseignant…</div>
  if (state === 'error') return <GateError retry={() => setRefreshKey((value) => value + 1)} />
  if (state === 'setup') return <Navigate to="/app/teacher/setup" replace />
  return children
}

export function RequireStudentReady({ children }: { children: ReactNode }) {
  const { activeOrganization } = useTenant()
  const location = useLocation()
  const [state, setState] = useState<'loading' | 'ready' | 'charter' | 'error'>('loading')
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (!activeOrganization) return
    let active = true
    setState('loading')
    getSchoolCharter('student')
      .then((charter) => {
        if (!active) return
        setState(!charter.is_enabled || charter.accepted_current_version ? 'ready' : 'charter')
      })
      .catch(() => {
        if (active) setState('error')
      })
    return () => { active = false }
  }, [activeOrganization?.id, location.pathname, refreshKey])

  if (state === 'loading') return <div className="app-loading">Vérification de votre accès étudiant…</div>
  if (state === 'error') return <GateError retry={() => setRefreshKey((value) => value + 1)} />
  if (state === 'charter') return <Navigate to="/app/student/charter" replace />
  return children
}
