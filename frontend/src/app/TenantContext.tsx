import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useLocation } from 'react-router-dom'
import {
  getCurrentOrganization,
  getOrganizationAccessProfile,
  getStoredOrganizationId,
  listOrganizations,
  setStoredOrganizationId,
  type Organization,
  type OrganizationAccessProfile,
} from '../lib/api'
import { DEFAULT_BRAND_COLORS, DEFAULT_PLATFORM_LOGO_URL } from '../brand/branding'
import { recolorTealPixels } from '../brand/recolorTealPixels'
import { cacheDirectionAccent } from '../brand/directionAccentCache'
import { getCurrentSchoolBranding, type CurrentSchoolBranding } from '../brand/schoolBrandingApi'
import { useAuth } from '../auth/AuthContext'
import { setSchoolInterfaceLocale } from './schoolLocale'
import { readSchoolLoginBranding } from '../lib/schoolLoginBranding'
import { schoolKeyForPath } from '../public/schoolHost'

type TenantContextValue = {
  organizations: Organization[]
  activeOrganization: Organization | null
  schoolBranding: CurrentSchoolBranding | null
  accessProfile: OrganizationAccessProfile | null
  loading: boolean
  organizationsReady: boolean
  profileLoading: boolean
  profileError: string
  refreshOrganizations: () => Promise<void>
  refreshBranding: () => Promise<void>
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

function setDocumentIcon(url: string) {
  let link = document.querySelector<HTMLLinkElement>("link[rel~='icon']")
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }
  link.href = url
}

export function TenantProvider({ children }: { children: ReactNode }) {
  const location = useLocation()
  const { user, supportMode } = useAuth()
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [activeOrganization, setActiveOrganization] = useState<Organization | null>(null)
  const [schoolBranding, setSchoolBranding] = useState<CurrentSchoolBranding | null>(null)
  const [accessProfile, setAccessProfile] = useState<OrganizationAccessProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [resolvedUserId, setResolvedUserId] = useState<number | null>(null)
  const [organizationsReadyKey, setOrganizationsReadyKey] = useState('')
  const [profileLoading, setProfileLoading] = useState(false)
  const [profileError, setProfileError] = useState('')
  const profileRequest = useRef(0)
  const iconRequest = useRef(0)
  const organizationsRequest = useRef(0)
  const brandingRequest = useRef(0)
  const organizationsReady = useRef(false)
  const organizationContextKey = user ? `${user.id}:${supportMode?.organization_id ?? ''}` : ''
  const organizationsReadyForCurrentUser = Boolean(user && organizationsReadyKey === organizationContextKey)

  useLayoutEffect(() => {
    if (location.pathname.startsWith('/app/')) {
      setSchoolInterfaceLocale(activeOrganization?.locale)
      return
    }

    const schoolLoginKey = location.pathname === '/login'
      ? new URLSearchParams(location.search).get('school')
      : null
    const schoolKey = schoolLoginKey ?? schoolKeyForPath(location.pathname)
    setSchoolInterfaceLocale(schoolKey ? readSchoolLoginBranding(schoolKey)?.locale : null)
  }, [location.pathname, location.search, activeOrganization?.id, activeOrganization?.locale])

  const applyCurrentBranding = useCallback(async (organization: Organization) => {
    const requestId = ++brandingRequest.current
    try {
      // Pass the target organization explicitly: the visual identity must never
      // depend on a stale organization id left in browser storage.
      const branding = await getCurrentSchoolBranding(organization.id)
      if (brandingRequest.current !== requestId || branding.organization_id !== organization.id) return organization
      const branded = withBranding(organization, branding)
      setSchoolBranding(branding)
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
      setOrganizationsReadyKey('')
      setOrganizations([])
      setActiveOrganization(null)
      setSchoolBranding(null)
      setAccessProfile(null)
      setResolvedUserId(null)
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
          setOrganizationsReadyKey(organizationContextKey)
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
      setSchoolBranding(null)
      setStoredOrganizationId(selected?.id ?? null)
      organizationsReady.current = true
      setOrganizationsReadyKey(organizationContextKey)
      if (selected) await applyCurrentBranding(selected)
    } finally {
      if (organizationsRequest.current === requestId) {
        setResolvedUserId(user.id)
        if (shouldBlockWorkspace) setLoading(false)
      }
    }
  }, [user?.id, supportMode?.organization_id, applyCurrentBranding])

  const refreshBranding = useCallback(async () => {
    if (!activeOrganization) {
      setSchoolBranding(null)
      return
    }
    await applyCurrentBranding(activeOrganization)
  }, [activeOrganization, applyCurrentBranding])

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
    const primary = schoolBranding?.primary_color || activeOrganization?.primary_color
    const secondary = schoolBranding?.secondary_color || activeOrganization?.secondary_color
    const accent = schoolBranding?.accent_color || activeOrganization?.accent_color
    const variables = primary && secondary && accent ? {
      '--school-primary': primary,
      '--school-secondary': secondary,
      '--school-accent': accent,
      '--blue': primary,
      '--green': secondary,
      '--tenant-accent': accent,
      '--button-end': `color-mix(in srgb, ${primary} 80%, white)`,
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
    schoolBranding?.primary_color,
    schoolBranding?.secondary_color,
    schoolBranding?.accent_color,
  ])

  useEffect(() => {
    const requestId = ++iconRequest.current
    let active = true
    const pathname = location.pathname

    // Public school pages manage their own title/favicon because they can be
    // opened without an authenticated tenant session.
    if (schoolKeyForPath(pathname)) return () => { active = false }

    // The school-branded login page sets its own title/favicon from the public
    // identity, so the platform defaults must not overwrite them.
    if (pathname === '/login' && new URLSearchParams(location.search).has('school')) return () => { active = false }

    if (pathname.startsWith('/app') && activeOrganization) {
      const schoolName = schoolBranding?.school_name || activeOrganization.name
      const section = pathname.startsWith('/app/teacher')
        ? 'Enseignant'
        : pathname.startsWith('/app/student')
          ? 'Étudiant'
          : 'Gestion'
      document.title = `${schoolName} - ${section}`
      const schoolIcon =
        schoolBranding?.favicon_url
        || schoolBranding?.logo_url
        || activeOrganization.logo_url
      const iconUrl = schoolIcon || DEFAULT_PLATFORM_LOGO_URL
      const directionAccent = activeOrganization.direction_accent_color
        || activeOrganization.secondary_color
        || DEFAULT_BRAND_COLORS.secondary
      cacheDirectionAccent(
        activeOrganization.id,
        directionAccent,
        activeOrganization.direction_accent_color == null,
      )
      if (!schoolIcon || schoolIcon === DEFAULT_PLATFORM_LOGO_URL) {
        if (directionAccent.toUpperCase() === DEFAULT_BRAND_COLORS.secondary) {
          setDocumentIcon(DEFAULT_PLATFORM_LOGO_URL)
        } else {
          recolorTealPixels(DEFAULT_PLATFORM_LOGO_URL, directionAccent, (source) => {
            if (active && iconRequest.current === requestId) setDocumentIcon(source)
          })
        }
      } else {
        setDocumentIcon(iconUrl)
      }
      return () => { active = false }
    }

    if (pathname.startsWith('/login') || pathname.startsWith('/invite') || pathname.startsWith('/admin')) {
      document.title = 'Académie des Créatifs'
      setDocumentIcon(DEFAULT_PLATFORM_LOGO_URL)
    }
    return () => { active = false }
  }, [
    location.pathname,
    location.search,
    activeOrganization?.id,
    activeOrganization?.name,
    activeOrganization?.logo_url,
    activeOrganization?.secondary_color,
    activeOrganization?.direction_accent_color,
    schoolBranding?.school_name,
    schoolBranding?.logo_url,
    schoolBranding?.favicon_url,
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
      setSchoolBranding(null)
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

  // The user appears one render before their schools start loading: without this,
  // the route guards would read "no school" and leave the requested page.
  const tenantLoading = loading || (user !== null && resolvedUserId !== user.id)

  const value = useMemo(
    () => ({
      organizations,
      activeOrganization,
      schoolBranding,
      accessProfile,
      loading: tenantLoading,
      organizationsReady: organizationsReadyForCurrentUser,
      profileLoading,
      profileError,
      refreshOrganizations,
      refreshBranding,
      refreshAccessProfile,
      selectOrganization,
    }),
    [
      organizations,
      activeOrganization,
      schoolBranding,
      accessProfile,
      tenantLoading,
      organizationsReadyForCurrentUser,
      profileLoading,
      profileError,
      refreshOrganizations,
      refreshBranding,
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
