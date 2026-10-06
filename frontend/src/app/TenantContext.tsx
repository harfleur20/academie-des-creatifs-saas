import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  getCurrentOrganization,
  getOrganizationAccessProfile,
  getStoredOrganizationId,
  listOrganizations,
  setStoredOrganizationId,
  type Organization,
  type OrganizationAccessProfile,
} from '../lib/api'
import { getCurrentSchoolBranding, type CurrentSchoolBranding } from '../brand/schoolBrandingApi'
import { useAuth } from '../auth/AuthContext'

type TenantContextValue = {
  organizations: Organization[]
  activeOrganization: Organization | null
  accessProfile: OrganizationAccessProfile | null
  loading: boolean
  profileLoading: boolean
  profileError: string
  refreshOrganizations: () => Promise<void>
  refreshAccessProfile: () => Promise<void>
  selectOrganization: (id: number) => void
}

const TenantContext = createContext<TenantContextValue | null>(null)

function withBranding(organization: Organization, branding: CurrentSchoolBranding): Organization {
  return {
    ...organization,
    name: branding.school_name || organization.name,
    logo_url: branding.logo_url,
    primary_color: branding.primary_color || organization.primary_color,
    secondary_color: branding.secondary_color || organization.secondary_color,
    accent_color: branding.accent_color || organization.accent_color,
  }
}

export function TenantProvider({ children }: { children: ReactNode }) {
  const { user, supportMode } = useAuth()
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [activeOrganization, setActiveOrganization] = useState<Organization | null>(null)
  const [accessProfile, setAccessProfile] = useState<OrganizationAccessProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [profileLoading, setProfileLoading] = useState(false)
  const [profileError, setProfileError] = useState('')
  const profileRequest = useRef(0)
  const organizationsRequest = useRef(0)
  const brandingRequest = useRef(0)
  const organizationsReady = useRef(false)

  const applyCurrentBranding = useCallback(async (organization: Organization) => {
    const requestId = ++brandingRequest.current
    try {
      const branding = await getCurrentSchoolBranding()
      if (brandingRequest.current !== requestId || branding.organization_id !== organization.id) return organization
      const branded = withBranding(organization, branding)
      setOrganizations((current) => current.map((item) => item.id === branded.id ? { ...item, ...branded } : item))
      setActiveOrganization((current) => current?.id === branded.id ? { ...current, ...branded } : current)
      return branded
    } catch {
      return organization
    }
  }, [])

  const refreshOrganizations = useCallback(async () => {
    const requestId = ++organizationsRequest.current
    if (!user) {
      organizationsReady.current = false
      setOrganizations([])
      setActiveOrganization(null)
      setAccessProfile(null)
      setLoading(false)
      return
    }

    const shouldBlockWorkspace = !organizationsReady.current
    if (shouldBlockWorkspace) setLoading(true)
    try {
      if (supportMode) {
        setStoredOrganizationId(supportMode.organization_id)
        const organization = await getCurrentOrganization()
        if (organizationsRequest.current === requestId) {
          setOrganizations([organization])
          setActiveOrganization(organization)
          organizationsReady.current = true
          await applyCurrentBranding(organization)
        }
        return
      }

      const items = await listOrganizations()
      if (organizationsRequest.current !== requestId) return
      setOrganizations(items)

      const storedId = getStoredOrganizationId()
      const selected =
        items.find((item) => item.id === storedId) ??
        items[0] ??
        null

      setActiveOrganization(selected)
      setStoredOrganizationId(selected?.id ?? null)
      organizationsReady.current = true
      if (selected) await applyCurrentBranding(selected)
    } finally {
      if (organizationsRequest.current === requestId && shouldBlockWorkspace) setLoading(false)
    }
  }, [user?.id, supportMode?.organization_id, applyCurrentBranding])

  const refreshAccessProfile = useCallback(async () => {
    const requestId = ++profileRequest.current
    if (!user || !activeOrganization) {
      setAccessProfile(null)
      setProfileLoading(false)
      setProfileError('')
      return
    }
    setProfileLoading(true)
    setProfileError('')
    try {
      const profile = await getOrganizationAccessProfile()
      if (profileRequest.current === requestId && profile.organization_id === activeOrganization.id) {
        setAccessProfile(profile)
      }
    } catch (error) {
      if (profileRequest.current === requestId) {
        setAccessProfile(null)
        setProfileError(error instanceof Error ? error.message : 'Impossible de charger vos accès.')
      }
    } finally {
      if (profileRequest.current === requestId) setProfileLoading(false)
    }
  }, [user?.id, activeOrganization?.id])

  useEffect(() => {
    organizationsReady.current = false
  }, [user?.id, supportMode?.organization_id])

  useEffect(() => {
    void refreshOrganizations()
  }, [refreshOrganizations])

  useEffect(() => {
    void refreshAccessProfile()
  }, [refreshAccessProfile])

  useEffect(() => {
    if (!user || !activeOrganization) return
    void applyCurrentBranding(activeOrganization)
  }, [user?.id, activeOrganization?.id, applyCurrentBranding])

  useEffect(() => {
    const root = document.documentElement
    const variables = activeOrganization ? {
      '--school-primary': activeOrganization.primary_color,
      '--school-secondary': activeOrganization.secondary_color,
      '--school-accent': activeOrganization.accent_color,
      '--blue': activeOrganization.primary_color,
      '--green': activeOrganization.secondary_color,
      '--tenant-accent': activeOrganization.accent_color,
      '--button-end': `color-mix(in srgb, ${activeOrganization.primary_color} 80%, white)`,
    } : null

    const names = [
      '--school-primary',
      '--school-secondary',
      '--school-accent',
      '--blue',
      '--green',
      '--tenant-accent',
      '--button-end',
    ]

    if (!variables) {
      names.forEach((name) => root.style.removeProperty(name))
      return
    }

    Object.entries(variables).forEach(([name, value]) => root.style.setProperty(name, value))
  }, [
    activeOrganization?.id,
    activeOrganization?.primary_color,
    activeOrganization?.secondary_color,
    activeOrganization?.accent_color,
  ])

  const selectOrganization = useCallback(
    (id: number) => {
      if (supportMode) return
      const selected = organizations.find((item) => item.id === id)
      if (!selected) return
      if (activeOrganization?.id === id) {
        if (!accessProfile && !profileLoading) void refreshAccessProfile()
        void applyCurrentBranding(selected)
        return
      }
      profileRequest.current += 1
      brandingRequest.current += 1
      setAccessProfile(null)
      setProfileError('')
      setActiveOrganization(selected)
      setStoredOrganizationId(selected.id)
    },
    [
      organizations,
      supportMode,
      activeOrganization?.id,
      accessProfile,
      profileLoading,
      refreshAccessProfile,
      applyCurrentBranding,
    ],
  )

  const value = useMemo(
    () => ({
      organizations,
      activeOrganization,
      accessProfile,
      loading,
      profileLoading,
      profileError,
      refreshOrganizations,
      refreshAccessProfile,
      selectOrganization,
    }),
    [
      organizations,
      activeOrganization,
      accessProfile,
      loading,
      profileLoading,
      profileError,
      refreshOrganizations,
      refreshAccessProfile,
      selectOrganization,
    ],
  )

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>
}

export function useTenant() {
  const value = useContext(TenantContext)
  if (!value) throw new Error('useTenant must be used inside TenantProvider')
  return value
}
