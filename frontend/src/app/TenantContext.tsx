import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
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

  const refreshOrganizations = useCallback(async () => {
    if (!user) {
      setOrganizations([])
      setActiveOrganization(null)
      setAccessProfile(null)
      return
    }

    setLoading(true)
    try {
      if (supportMode) {
        setStoredOrganizationId(supportMode.organization_id)
        const organization = await getCurrentOrganization()
        setOrganizations([organization])
        setActiveOrganization(organization)
        return
      }

      const items = await listOrganizations()
      setOrganizations(items)

      const storedId = getStoredOrganizationId()
      const selected =
        items.find((item) => item.id === storedId) ??
        items[0] ??
        null

      setActiveOrganization(selected)
      setStoredOrganizationId(selected?.id ?? null)
    } finally {
      setLoading(false)
    }
  }, [user, supportMode?.organization_id])

  const refreshAccessProfile = useCallback(async () => {
    if (!user || !activeOrganization) {
      setAccessProfile(null)
      return
    }
    setProfileLoading(true)
    try {
      setAccessProfile(await getOrganizationAccessProfile())
    } catch {
      setAccessProfile(null)
    } finally {
      setProfileLoading(false)
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
      setAccessProfile(null)
      setActiveOrganization(selected)
      setStoredOrganizationId(selected.id)
    },
    [organizations, supportMode],
  )

  const value = useMemo(
    () => ({
      organizations,
      activeOrganization,
      accessProfile,
      loading,
      profileLoading,
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
