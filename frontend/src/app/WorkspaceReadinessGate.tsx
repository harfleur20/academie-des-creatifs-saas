import { useEffect, useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useTenant } from './TenantContext'
import { getOnboardingStatus } from '../lib/api'
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

export function RequireTeacherReady({ children, requireProfile = true }: { children: ReactNode; requireProfile?: boolean }) {
  const { activeOrganization, accessProfile } = useTenant()
  const location = useLocation()
  const [state, setState] = useState<'loading' | 'ready' | 'setup' | 'school-setup' | 'error'>('loading')
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (!activeOrganization) return
    let active = true
    setState('loading')
    const checkReadiness = async () => {
      try {
        if (accessProfile?.roles.includes('owner')) {
          const onboarding = await getOnboardingStatus()
          if (!active) return
          if (!onboarding.is_complete) {
            setState('school-setup')
            return
          }
        }

        if (!requireProfile) {
          if (active) setState('ready')
          return
        }

        const [profile, charter] = await Promise.all([
          getTeacherProfessionalProfile(),
          getSchoolCharter('teacher'),
        ])
        if (!active) return
        const charterReady = !charter.is_enabled || charter.accepted_current_version
        setState(profile.is_complete && charterReady ? 'ready' : 'setup')
      } catch {
        if (active) setState('error')
      }
    }
    void checkReadiness()
    return () => { active = false }
  }, [activeOrganization?.id, accessProfile?.roles, location.pathname, refreshKey, requireProfile])

  if (state === 'loading') return <div className="app-loading">Vérification des prérequis de l’espace enseignant…</div>
  if (state === 'error') return <GateError retry={() => setRefreshKey((value) => value + 1)} />
  if (state === 'school-setup') return <Navigate to="/app/manage/onboarding" replace />
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
