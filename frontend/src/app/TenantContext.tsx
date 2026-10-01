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
  getStoredOrganizationId,
  listOrganizations,
  setStoredOrganizationId,
  type Organization,
} from '../lib/api'
import { useAuth } from '../auth/AuthContext'

type TenantContextValue = {
  organizations: Organization[]
  activeOrganization: Organization | null
  loading: boolean
  refreshOrganizations: () => Promise<void>
  selectOrganization: (id: number) => void
}

const TenantContext = createContext<TenantContextValue | null>(null)

export function TenantProvider({ children }: { children: ReactNode }) {
  const { user, supportMode } = useAuth()
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [activeOrganization, setActiveOrganization] = useState<Organization | null>(null)
  const [loading, setLoading] = useState(false)

  const refreshOrganizations = useCallback(async () => {
    if (!user) {
      setOrganizations([])
      setActiveOrganization(null)
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

  useEffect(() => {
    void refreshOrganizations()
  }, [refreshOrganizations])

  const selectOrganization = useCallback(
    (id: number) => {
      if (supportMode) return
      const selected = organizations.find((item) => item.id === id)
      if (!selected) return
      setActiveOrganization(selected)
      setStoredOrganizationId(selected.id)
    },
    [organizations, supportMode],
  )

  const value = useMemo(
    () => ({
      organizations,
      activeOrganization,
      loading,
      refreshOrganizations,
      selectOrganization,
    }),
    [
      organizations,
      activeOrganization,
      loading,
      refreshOrganizations,
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
