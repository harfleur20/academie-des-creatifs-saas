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

export function TenantProvider({ children }: { children: ReactNode }) {
  const { user, supportMode } = useAuth()
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [activeOrganization, setActiveOrganization] = useState<Organization | null>(null)
  const [accessProfile, setAccessProfile] = useState<OrganizationAccessProfile | null>(null)
  const [loading, setLoading] = useState(false)
  const [profileLoading, setProfileLoading] = useState(false)
  const [profileError, setProfileError] = useState('')
  const profileRequest = useRef(0)
  const organizationsRequest = useRef(0)

  const refreshOrganizations = useCallback(async () => {
    const requestId = ++organizationsRequest.current
    if (!user) {
      setOrganizations([])
      setActiveOrganization(null)
      setAccessProfile(null)
      setLoading(false)
      return
    }

    setLoading(true)
    try {
      if (supportMode) {
        setStoredOrganizationId(supportMode.organization_id)
        const organization = await getCurrentOrganization()
        if (organizationsRequest.current === requestId) {
          setOrganizations([organization])
          setActiveOrganization(organization)
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
    } finally {
      if (organizationsRequest.current === requestId) setLoading(false)
    }
  }, [user, supportMode?.organization_id])

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
  }, [user, activeOrganization?.id])

  useEffect(() => {
    void refreshOrganizations()
  }, [refreshOrganizations])

  useEffect(() => {
    void refreshAccessProfile()
  }, [refreshAccessProfile])

  const selectOrganization = useCallback(
    (id: number) => {
      if (supportMode) return
      const selected = organizations.find((item) => item.id === id)
      if (!selected) return
      if (activeOrganization?.id === id) {
        if (!accessProfile && !profileLoading) void refreshAccessProfile()
        return
      }
      profileRequest.current += 1
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
