import { activeSchoolLocale } from './schoolLocale'
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
  type ReactNode,
} from 'react'
import {
  BookOpen,
  Building2,
  Check,
  ChevronDown,
  Eye,
  ExternalLink,
  GraduationCap,
  LifeBuoy,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Power,
  Search,
  Settings,
  UserRound,
  X,
} from 'lucide-react'
import { createPortal } from 'react-dom'
import {
  Navigate,
  NavLink,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { BrandLogo } from '../brand/BrandLogo'
import { DirectionWordmark } from '../brand/DirectionWordmark'
import { SchoolLogo } from '../brand/SchoolLogo'
import { takePostLogoutDestination } from '../lib/authOrigin'
import {
  DEFAULT_BRAND_COLORS,
  DEFAULT_SCHOOL_LOGO_URL,
  DEFAULT_PLATFORM_LOGO_URL,
} from '../brand/branding'
import {
  endAdminSupportMode,
  createOrganization,
  getOrganizationCreationCapacity,
  setStoredOrganizationId,
  updateCurrentOrganization,
  type Organization,
  type OrganizationAccessProfile,
  type OrganizationCreationCapacity,
  type WorkspaceSpace,
} from '../lib/api'
import { useTenant } from './TenantContext'
import { SchoolNotificationBell } from './SchoolNotificationBell'
import { SchoolMessageBell } from './SchoolMessageBell'
import { MenuLink, SpaceOutlet } from '../components/DemoGate'
import { toast } from '../ui/toast'

export type WorkspaceNavItem = {
  to: string
  label: string
  icon: ReactNode
  end?: boolean
}

export type WorkspaceNavGroup = {
  key: string
  label: string
  icon: ReactNode
  items: WorkspaceNavItem[]
}

const workspaceLabels: Record<WorkspaceSpace, string> = {
  manage: 'Gestion',
  teacher: 'Enseignant',
  student: 'Étudiant',
}

const workspaceMenuLabels: Record<WorkspaceSpace, string> = {
  manage: 'Espace direction',
  teacher: 'Espace professeur',
  student: 'Espace étudiant',
}

function slugifyOrganizationName(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 120)
    .replace(/-$/g, '')
}

function WorkspaceSpaceIcon({ space }: { space: WorkspaceSpace }) {
  if (space === 'manage') return <Building2 size={17} aria-hidden="true" />
  if (space === 'teacher') return <GraduationCap size={17} aria-hidden="true" />
  return <BookOpen size={17} aria-hidden="true" />
}

function SchoolWorkspaceSwitcher({
  variant,
  currentSpace,
  collapsed = false,
  organizations,
  activeOrganization,
  accessProfile,
  profileLoading,
  supportMode = false,
  creationCapacity,
  creationCapacityLoading = false,
  canManageSchools = false,
  schoolPrimaryColor,
  schoolSecondaryColor,
  onCreateOrganization,
  onUpgradePlan,
  onSelectOrganization,
  onSwitchWorkspace,
  onOpenChange,
}: {
  variant: 'direction'
  currentSpace: WorkspaceSpace
  collapsed?: boolean
  organizations: Organization[]
  activeOrganization: Organization | null
  accessProfile: OrganizationAccessProfile | null
  profileLoading: boolean
  supportMode?: boolean
  creationCapacity: OrganizationCreationCapacity | null
  creationCapacityLoading?: boolean
  canManageSchools?: boolean
  schoolPrimaryColor: string
  schoolSecondaryColor: string
  onCreateOrganization: (name: string) => Promise<void>
  onUpgradePlan: () => void
  onSelectOrganization: (id: number) => void
  onSwitchWorkspace: (space: WorkspaceSpace) => void
  onOpenChange?: (open: boolean) => void
}) {
  const [open, setOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [newSchoolName, setNewSchoolName] = useState('')
  const [creatingSchool, setCreatingSchool] = useState(false)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const canSwitchSchool = !supportMode && organizations.length > 1
  const availableSpaces = supportMode ? [] : accessProfile?.spaces ?? []
  const canSwitchSpace = availableSpaces.length > 1
  const canOpen = !supportMode && Boolean(activeOrganization)
  const schoolName = activeOrganization?.name || 'Aucune école'
  const triggerLabel = supportMode ? 'École consultée' : 'École active'
  const triggerValue = schoolName
  const configuredSchoolLogo = activeOrganization?.logo_url?.trim()
  const hasCustomSchoolLogo = Boolean(configuredSchoolLogo && configuredSchoolLogo !== DEFAULT_SCHOOL_LOGO_URL)
  const creationQuotaDescription = creationCapacity
    ? creationCapacity.maximum_organizations === null
      ? `${creationCapacity.owned_organizations} ${creationCapacity.owned_organizations > 1 ? 'écoles' : 'école'} · sans limite`
      : `${creationCapacity.owned_organizations}/${creationCapacity.maximum_organizations} ${creationCapacity.maximum_organizations > 1 ? 'écoles' : 'école'} · ${creationCapacity.plan_name || 'forfait actuel'}`
    : 'Quota indisponible'

  async function submitNewSchool(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = newSchoolName.trim()
    if (!name || creatingSchool) return
    setCreatingSchool(true)
    try {
      await onCreateOrganization(name)
      setCreateOpen(false)
      setNewSchoolName('')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Impossible de créer cette école.')
    } finally {
      setCreatingSchool(false)
    }
  }

  function beginSchoolCreation() {
    setMenuOpen(false)
    if (creationCapacityLoading || !creationCapacity) {
      toast.info('Vérification du quota de votre forfait. Réessayez dans un instant.')
      return
    }
    if (!creationCapacity.can_create) {
      toast.info('La limite d’écoles de votre forfait est atteinte. Choisissez un forfait supérieur pour continuer.')
      onUpgradePlan()
      return
    }
    setNewSchoolName('')
    setCreateOpen(true)
  }

  const setMenuOpen = useCallback((nextOpen: boolean) => {
    setOpen(nextOpen)
    onOpenChange?.(nextOpen)
  }, [onOpenChange])

  useEffect(() => {
    if (!open) return
    function closeOnOutsideClick(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setMenuOpen(false)
      }
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('mousedown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open, setMenuOpen])

  return (
    <div ref={wrapperRef} className={`school-switcher school-switcher--${variant}${collapsed ? ' is-collapsed' : ''}${open ? ' is-open' : ''}`}>
      <button
        type="button"
        className={`school-switcher-trigger${collapsed ? ' is-collapsed' : ''}`}
        onClick={() => setMenuOpen(!open)}
        disabled={!canOpen}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls="school-workspace-switcher-menu"
        aria-label={`${triggerLabel} : ${triggerValue}${canOpen ? ', ouvrir le menu' : ''}`}
        title={collapsed ? schoolName : undefined}
      >
        {collapsed ? (
          hasCustomSchoolLogo ? (
            <SchoolLogo logoUrl={configuredSchoolLogo} alt="" className="school-switcher-collapsed-logo" />
          ) : (
            <span className="school-switcher-initial" aria-hidden="true">
              {schoolName.trim().charAt(0).toUpperCase() || '?'}
            </span>
          )
        ) : (
          <>
            <SchoolLogo
              logoUrl={activeOrganization?.logo_url}
              alt={schoolName}
              className="school-switcher-logo"
            />
            <span className="school-switcher-trigger-copy">
              <small>{triggerLabel}</small>
              <strong>{triggerValue}</strong>
            </span>
            {canOpen && <ChevronDown className="school-switcher-trigger-chevron" size={16} aria-hidden="true" />}
          </>
        )}
      </button>

      {open && (
        <div id="school-workspace-switcher-menu" className="school-switcher-menu" role="dialog" aria-label="Écoles et espaces disponibles">
          {canSwitchSchool && (
            <section className="school-switcher-menu-section" aria-labelledby="school-switcher-schools-label">
              <small id="school-switcher-schools-label">Changer d’école</small>
              <div className="school-switcher-menu-options">
                {organizations.map((organization) => {
                  const selected = organization.id === activeOrganization?.id
                  return (
                    <button
                      key={organization.id}
                      type="button"
                      className={`school-switcher-menu-option${selected ? ' is-active' : ''}`}
                      aria-current={selected ? 'true' : undefined}
                      onClick={() => {
                        setMenuOpen(false)
                        onSelectOrganization(organization.id)
                      }}
                    >
                      <SchoolLogo logoUrl={organization.logo_url} alt="" className="school-switcher-menu-logo" />
                      <span><strong>{organization.name}</strong></span>
                      {selected && <Check size={16} aria-hidden="true" />}
                    </button>
                  )
                })}
              </div>
            </section>
          )}

          {!canSwitchSchool && activeOrganization && (
            <section className="school-switcher-menu-section" aria-labelledby="school-switcher-active-school-label">
              <small id="school-switcher-active-school-label">École active</small>
              <div className="school-switcher-menu-summary">
                <SchoolLogo logoUrl={activeOrganization.logo_url} alt="" className="school-switcher-menu-logo" />
                <span><strong>{schoolName}</strong><small>Vous êtes dans cette école</small></span>
              </div>
            </section>
          )}

          {canSwitchSpace && (
            <section className="school-switcher-menu-section" aria-labelledby="school-switcher-spaces-label">
              <small id="school-switcher-spaces-label">Changer d’espace</small>
              <div className="school-switcher-menu-options">
                {availableSpaces.map((item) => {
                  const selected = item === currentSpace
                  return (
                    <button
                      key={item}
                      type="button"
                      className={`school-switcher-menu-option${selected ? ' is-active' : ''}`}
                      aria-current={selected ? 'page' : undefined}
                      onClick={() => {
                        setMenuOpen(false)
                        onSwitchWorkspace(item)
                      }}
                    >
                      <span className="school-switcher-menu-space-icon"><WorkspaceSpaceIcon space={item} /></span>
                      <span><strong>{workspaceMenuLabels[item]}</strong></span>
                      {selected && <Check size={16} aria-hidden="true" />}
                    </button>
                  )
                })}
              </div>
            </section>
          )}

          {accessProfile && availableSpaces.length === 1 && (
            <section className="school-switcher-menu-section" aria-labelledby="school-switcher-current-space-label">
              <small id="school-switcher-current-space-label">Espace disponible</small>
              <div className="school-switcher-menu-summary">
                <span className="school-switcher-menu-space-icon"><WorkspaceSpaceIcon space={availableSpaces[0]} /></span>
                <span><strong>{workspaceMenuLabels[availableSpaces[0]]}</strong><small>Aucun autre espace n’est associé à votre compte</small></span>
              </div>
            </section>
          )}

          {!accessProfile && (
            <p className="school-switcher-menu-message">
              {profileLoading ? 'Chargement des espaces disponibles…' : 'Les espaces disponibles n’ont pas pu être chargés.'}
            </p>
          )}

          {accessProfile && availableSpaces.length === 0 && (
            <p className="school-switcher-menu-message">Aucun espace n’est associé à votre compte dans cette école.</p>
          )}

          {canManageSchools && (
            <section className="school-switcher-menu-section school-switcher-menu-create-section">
              <button
                type="button"
                className="school-switcher-create"
                onClick={beginSchoolCreation}
                disabled={creationCapacityLoading}
              >
                <Plus size={17} aria-hidden="true" />
                <span><strong>Ajouter une école</strong><small>
                  {creationCapacityLoading
                    ? 'Vérification du forfait…'
                    : creationQuotaDescription}
                </small></span>
              </button>
            </section>
          )}
        </div>
      )}

      {createOpen && typeof document !== 'undefined' && createPortal(
        <div className="school-create-overlay" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !creatingSchool) setCreateOpen(false)
        }}>
          <section
            className="school-create-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="school-create-title"
            style={{
              '--school-create-primary': schoolPrimaryColor,
              '--school-create-secondary': schoolSecondaryColor,
            } as CSSProperties}
          >
            <button type="button" className="school-create-close" onClick={() => setCreateOpen(false)} aria-label="Fermer" disabled={creatingSchool}><X size={19} /></button>
            <span className="school-create-kicker">+ NOUVEL ESPACE</span>
            <h2 id="school-create-title">Ajouter une école</h2>
            <p>Cette école aura son propre site, ses membres et ses réglages.</p>
            <form onSubmit={(event) => void submitNewSchool(event)}>
              <label htmlFor="new-school-name">Nom de l’école</label>
              <input
                id="new-school-name"
                autoFocus
                maxLength={180}
                minLength={2}
                placeholder="Ex. Studio Créatif Academy"
                value={newSchoolName}
                onChange={(event) => setNewSchoolName(event.target.value)}
                required
              />
              <div className="school-create-dialog-actions">
                <button type="button" className="school-create-cancel" onClick={() => setCreateOpen(false)} disabled={creatingSchool}>Annuler</button>
                <button type="submit" className="school-create-submit" disabled={creatingSchool || newSchoolName.trim().length < 2}>
                  {creatingSchool ? 'Création…' : 'Créer mon école'}
                </button>
              </div>
            </form>
          </section>
        </div>,
        document.body,
      )}
    </div>
  )
}

function initialsFor(name?: string | null) {
  return (name || '?')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}

function navItemMatches(pathname: string, item: WorkspaceNavItem) {
  return pathname === item.to || (!item.end && pathname.startsWith(item.to))
}

export function SchoolWorkspaceLayout({
  space,
  navItems,
  navGroups = [],
  trailingNavItems = [],
}: {
  space: WorkspaceSpace
  navItems: WorkspaceNavItem[]
  navGroups?: WorkspaceNavGroup[]
  trailingNavItems?: WorkspaceNavItem[]
}) {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, signOut, supportMode } = useAuth()
  const {
    organizations,
    activeOrganization,
    accessProfile,
    profileLoading,
    selectOrganization,
    refreshOrganizations,
    schoolBranding,
    loading: tenantLoading,
  } = useTenant()

  const [sidebarOpen, setSidebarOpen] = useState(false)
  // The direction sidebar follows a click at once; the choice reaches the school a moment later.
  const [sidebarCollapsedChoice, setSidebarCollapsedChoice] = useState<boolean | null>(null)
  const sidebarSaveTimer = useRef<number | null>(null)
  const [supportsCompactSidebar, setSupportsCompactSidebar] = useState(() => window.matchMedia('(min-width: 1024px)').matches)
  const [profileOpen, setProfileOpen] = useState(false)
  const [workspaceSwitcherOpen, setWorkspaceSwitcherOpen] = useState(false)
  const [organizationCapacity, setOrganizationCapacity] = useState<OrganizationCreationCapacity | null>(null)
  const [organizationCapacityLoading, setOrganizationCapacityLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [openNavGroups, setOpenNavGroups] = useState<string[]>(
    () => space === 'student' && navGroups[0] ? [navGroups[0].key] : [],
  )
  const profileRef = useRef<HTMLDivElement>(null)

  const loadOrganizationCapacity = useCallback(async () => {
    if (!user || supportMode || space === 'teacher' || space === 'student') {
      setOrganizationCapacity(null)
      return
    }
    setOrganizationCapacityLoading(true)
    try {
      setOrganizationCapacity(await getOrganizationCreationCapacity())
    } catch {
      setOrganizationCapacity(null)
    } finally {
      setOrganizationCapacityLoading(false)
    }
  }, [user, supportMode, space])

  useEffect(() => {
    void loadOrganizationCapacity()
  }, [loadOrganizationCapacity])

  async function createSchoolFromSwitcher(name: string) {
    const organization = await createOrganization({
      name,
      slug: slugifyOrganizationName(name),
    })
    setStoredOrganizationId(organization.id)
    await refreshOrganizations()
    await loadOrganizationCapacity()
    navigate('/app/manage/onboarding?essai=1')
    toast.success(`${organization.name} a été créée.`)
  }

  function handleSwitcherOpenChange(open: boolean) {
    setWorkspaceSwitcherOpen(open)
    if (open) void loadOrganizationCapacity()
  }

  const canManageSchools = !supportMode && (
    accessProfile?.roles.includes('owner') === true
    || user?.platform_role === 'super_admin'
  )

  useEffect(() => {
    const media = window.matchMedia('(min-width: 1024px)')
    const updateViewport = () => setSupportsCompactSidebar(media.matches)
    media.addEventListener('change', updateViewport)
    return () => media.removeEventListener('change', updateViewport)
  }, [])

  const isRoleSpace = space === 'teacher' || space === 'student'
  // A new account without a school yet: every management screen but the dashboard (which
  // creates the first school) and the account's own profile needs a school.
  const spaceHome = `/app/${space}`
  const awaitingFirstSchool = !isRoleSpace && !tenantLoading && !activeOrganization && !supportMode
  const openWithoutSchool = [spaceHome, `${spaceHome}/profile`]
  const visibleNavItems = awaitingFirstSchool
    ? navItems.filter((item) => item.to === spaceHome)
    : navItems
  const visibleNavGroups = awaitingFirstSchool ? [] : navGroups
  const visibleTrailingNavItems = awaitingFirstSchool ? [] : trailingNavItems
  const organizationPrimary =
    activeOrganization?.primary_color || DEFAULT_BRAND_COLORS.primary
  const organizationSecondary =
    activeOrganization?.secondary_color || DEFAULT_BRAND_COLORS.secondary
  const organizationAccent =
    activeOrganization?.accent_color || DEFAULT_BRAND_COLORS.accent
  const directionAccent = activeOrganization?.direction_accent_color || organizationSecondary || '#18A7A3'
  const directionSidebarCollapseEnabled = !isRoleSpace
    && activeOrganization?.direction_sidebar_collapse_enabled === true
    && supportsCompactSidebar
  const directionSidebarCollapsed = !isRoleSpace
    && directionSidebarCollapseEnabled
    && (sidebarCollapsedChoice ?? activeOrganization?.direction_sidebar_collapsed === true)

  // A choice not yet saved belongs to the school it was made in.
  useEffect(() => () => {
    if (sidebarSaveTimer.current !== null) window.clearTimeout(sidebarSaveTimer.current)
    sidebarSaveTimer.current = null
    setSidebarCollapsedChoice(null)
  }, [activeOrganization?.id])

  const brandStyle = {
    '--blue': isRoleSpace
      ? organizationPrimary
      : DEFAULT_BRAND_COLORS.primary,
    '--green': isRoleSpace ? organizationSecondary : directionAccent,
    '--green-soft': isRoleSpace
      ? undefined
      : `color-mix(in srgb, ${directionAccent} 12%, white)`,
    '--green-ink': isRoleSpace
      ? undefined
      : `color-mix(in srgb, ${directionAccent} 78%, #10233f)`,
    '--direction-accent': directionAccent,
    '--button-end': isRoleSpace
      ? `color-mix(in srgb, ${organizationPrimary} 80%, white)`
      : directionAccent,
    '--tenant-accent': isRoleSpace
      ? organizationAccent
      : DEFAULT_BRAND_COLORS.accent,
    '--school-primary': organizationPrimary,
    '--school-secondary': organizationSecondary,
    '--school-accent': organizationAccent,
  } as CSSProperties

  const allNavItems = useMemo(
    () => [...visibleNavItems, ...visibleNavGroups.flatMap((group) => group.items), ...visibleTrailingNavItems],
    [visibleNavItems, visibleNavGroups, visibleTrailingNavItems],
  )
  const activeNavGroup = navGroups.find((group) =>
    group.items.some((item) => navItemMatches(location.pathname, item)),
  )?.key

  const currentLabel =
    allNavItems.find((item) => navItemMatches(location.pathname, item))?.label
    || (location.pathname === `/app/${space}/messages` ? 'Messages' : '')
    || (location.pathname === `/app/${space}/notifications` ? 'Notifications' : '')
    || workspaceLabels[space]

  const searchResults = useMemo(() => {
    const query = search.trim().toLocaleLowerCase(activeSchoolLocale())
    if (!query) return []
    return allNavItems
      .filter((item) => item.label.toLocaleLowerCase(activeSchoolLocale()).includes(query))
      .slice(0, 6)
  }, [allNavItems, search])

  useEffect(() => {
    setSidebarOpen(false)
    setProfileOpen(false)
    setSearch('')
    if (!isRoleSpace) {
      setOpenNavGroups(activeNavGroup ? [activeNavGroup] : [])
    } else if (activeNavGroup) {
      setOpenNavGroups((current) => current.includes(activeNavGroup)
        ? current
        : [...current, activeNavGroup])
    }
  }, [location.pathname, activeNavGroup, isRoleSpace])

  useEffect(() => {
    function handleOutsideClick(event: MouseEvent) {
      if (
        profileRef.current
        && !profileRef.current.contains(event.target as Node)
      ) {
        setProfileOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [])

  async function leaveSupportMode() {
    if (!supportMode) return
    const organizationId = supportMode.organization_id
    try {
      await endAdminSupportMode()
    } finally {
      window.location.assign(`/admin/schools/${organizationId}`)
    }
  }

  function switchWorkspace(nextSpace: WorkspaceSpace) {
    localStorage.setItem('academie_saas_workspace_space', nextSpace)
    navigate(`/app/${nextSpace}`)
  }

  function handleSignOut() {
    const schoolSlug = activeOrganization?.slug
    const destination = takePostLogoutDestination(schoolSlug)
    navigate(destination, { replace: true, flushSync: true })
    signOut()
  }

  function toggleNavGroup(key: string) {
    setOpenNavGroups((current) => (
      current.includes(key)
        ? current.filter((item) => item !== key)
        : [...current, key]
    ))
  }

  // The rail moves on the click; the school's preference is saved once the clicks stop.
  function toggleDirectionSidebar() {
    if (!activeOrganization || !directionSidebarCollapseEnabled) return
    const collapsed = !directionSidebarCollapsed
    setSidebarCollapsedChoice(collapsed)
    if (sidebarSaveTimer.current !== null) window.clearTimeout(sidebarSaveTimer.current)
    sidebarSaveTimer.current = window.setTimeout(() => {
      sidebarSaveTimer.current = null
      void saveDirectionSidebar(collapsed)
    }, 400)
  }

  async function saveDirectionSidebar(collapsed: boolean) {
    try {
      await updateCurrentOrganization({ direction_sidebar_collapsed: collapsed })
      await refreshOrganizations()
      // A later click keeps its own choice until it is saved in turn.
      setSidebarCollapsedChoice((current) => (current === collapsed ? null : current))
    } catch (error) {
      setSidebarCollapsedChoice(null)
      toast.error(error instanceof Error ? error.message : 'Impossible de modifier la barre latérale.')
    }
  }

  if (!isRoleSpace) {
    return (
      <div className={`saas-app${directionSidebarCollapsed ? ' is-manage-sidebar-collapsed' : ''}`} style={brandStyle}>
        {sidebarOpen && <button className="manage-sidebar-backdrop" type="button" aria-label="Fermer le menu" onClick={() => setSidebarOpen(false)} />}
        <aside className={`app-sidebar${sidebarOpen ? ' is-open' : ''}${directionSidebarCollapsed ? ' is-collapsed' : ''}${workspaceSwitcherOpen ? ' has-workspace-menu-open' : ''}`}>
          <div className="app-brand">
            <a className="direction-brand-home" href="/" aria-label="Retour à l’accueil de l’Académie des Créatifs">
              <DirectionWordmark accentColor={directionAccent} />
            </a>
          </div>
          {activeOrganization
            && !supportMode
            && ['owner', 'admin', 'super_admin'].includes(accessProfile?.primary_role || '')
            && directionSidebarCollapseEnabled && <button
              type="button"
              className="sidebar-collapse-toggle"
              onClick={toggleDirectionSidebar}
              aria-label={directionSidebarCollapsed ? 'Développer la barre latérale' : 'Rétracter la barre latérale'}
              title={directionSidebarCollapsed ? 'Développer la barre latérale' : 'Rétracter la barre latérale'}
            >
              {directionSidebarCollapsed ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}
            </button>}

          <SchoolWorkspaceSwitcher
            variant="direction"
            currentSpace={space}
            collapsed={directionSidebarCollapsed && !sidebarOpen}
            organizations={organizations}
            activeOrganization={activeOrganization}
            accessProfile={accessProfile}
            profileLoading={profileLoading}
            supportMode={Boolean(supportMode)}
            creationCapacity={organizationCapacity}
            creationCapacityLoading={organizationCapacityLoading}
            canManageSchools={canManageSchools}
            schoolPrimaryColor={organizationPrimary}
            schoolSecondaryColor={directionAccent}
            onCreateOrganization={createSchoolFromSwitcher}
            onUpgradePlan={() => navigate('/app/manage/billing')}
            onSelectOrganization={(id) => {
              selectOrganization(id)
              navigate('/app')
            }}
            onSwitchWorkspace={switchWorkspace}
            onOpenChange={handleSwitcherOpenChange}
          />

          <nav className="app-nav">
            {visibleNavItems.map((item) => (
              <MenuLink key={item.to} to={item.to} end={item.end} title={item.label}>
                {item.icon}<span className="app-nav-label">{item.label}</span>
              </MenuLink>
            ))}
            {visibleNavGroups.map((group) => {
              const isOpen = openNavGroups.includes(group.key)
              const isActive = group.items.some((item) => navItemMatches(location.pathname, item))
              return (
                <div key={group.key} className={`app-nav-group${isOpen ? ' is-open' : ''}${isActive ? ' is-active' : ''}`}>
                  <button
                    type="button"
                    className="app-nav-group-trigger"
                    onClick={() => toggleNavGroup(group.key)}
                    aria-expanded={isOpen}
                    title={directionSidebarCollapsed ? group.label : undefined}
                  >
                    {group.icon}
                    <span>{group.label}</span>
                    <ChevronDown className="app-nav-group-chevron" size={14} />
                  </button>
                  {isOpen && (
                    <div className="app-nav-subnav">
                      {group.items.map((item) => (
                        <MenuLink key={item.to} to={item.to} end={item.end} title={item.label}>
                          {item.icon}<span className="app-nav-label">{item.label}</span>
                        </MenuLink>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </nav>

          <div className="sidebar-user">
            <div className="user-avatar">
              {user?.avatar_url ? (
                <img src={user.avatar_url} alt={user.full_name} />
              ) : (
                initialsFor(user?.full_name)
              )}
            </div>
            <div>
              <strong>{user?.full_name}</strong>
              <small>
                {supportMode
                  ? 'Super-admin · support'
                  : `${workspaceLabels[space]} · ${user?.email || ''}`}
              </small>
            </div>
          </div>
        </aside>

        <div className="app-content">
          <header className="manage-topbar">
            <button type="button" className="manage-topbar-menu" aria-label={sidebarOpen ? 'Fermer le menu' : 'Ouvrir le menu'} aria-expanded={sidebarOpen} onClick={() => setSidebarOpen((value) => !value)}>
              {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
            <div className="manage-topbar-search">
              <Search size={17} />
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Rechercher dans le dashboard..." aria-label="Rechercher une rubrique de gestion" />
              {searchResults.length > 0 && <div className="manage-topbar-results">
                {searchResults.map((item) => <button type="button" key={item.to} onClick={() => { navigate(item.to); setSearch('') }}>{item.icon}<span>{item.label}</span></button>)}
              </div>}
            </div>
            <div className="manage-topbar-actions" ref={profileRef}>
              {activeOrganization && <NavLink className="manage-topbar-site" to={`/school/${activeOrganization.slug}`} target="_blank" rel="noopener noreferrer" title="Voir le site public"><Eye size={17} /><span>Voir le site</span></NavLink>}
              <SchoolNotificationBell space="manage" />
              <button type="button" className="manage-topbar-profile" onClick={() => setProfileOpen((value) => !value)} aria-expanded={profileOpen} aria-label="Ouvrir le menu du compte">
                <span className="manage-topbar-avatar">{user?.avatar_url ? <img src={user.avatar_url} alt="" /> : initialsFor(user?.full_name)}</span>
                <span className="manage-topbar-profile-label"><strong>{user?.full_name || 'Administrateur'}</strong><small>{activeOrganization?.name || 'Gestion de l’école'}</small></span>
                <ChevronDown size={15} />
              </button>
              {profileOpen && <div className="manage-topbar-profile-menu">
                <div><strong>{user?.full_name}</strong><small>{user?.email}</small></div>
                <button type="button" onClick={() => { setProfileOpen(false); navigate('/app/manage/profile') }}><UserRound size={16} /> Profil</button>
                {!awaitingFirstSchool && <>
                  <button type="button" onClick={() => { setProfileOpen(false); navigate('/app/manage/identity?tab=school') }}><Settings size={16} /> Identité de l’école</button>
                  <button type="button" onClick={() => { setProfileOpen(false); navigate('/app/manage/support') }}><LifeBuoy size={16} /> Support</button>
                </>}
                <span className="account-menu-divider" aria-hidden="true" />
                <button type="button" className="is-danger" onClick={() => { setProfileOpen(false); handleSignOut() }}><Power size={16} /> Se déconnecter</button>
              </div>}
            </div>
          </header>
          {supportMode && (
            <div className="support-mode-banner">
              <div>
                <span className="support-mode-icon"><Eye size={17} /></span>
                <span>
                  <strong>
                    Mode support - {supportMode.organization_name}
                  </strong>
                  <small>
                    Lecture seule · session temporaire jusqu’à{' '}
                    {new Intl.DateTimeFormat(activeSchoolLocale(), {
                      hour: '2-digit',
                      minute: '2-digit',
                    }).format(new Date(supportMode.expires_at))}
                  </small>
                </span>
              </div>
              <button type="button" onClick={() => void leaveSupportMode()}>
                Quitter le mode support
              </button>
            </div>
          )}
          {awaitingFirstSchool && !openWithoutSchool.includes(location.pathname.replace(/\/+$/, ''))
            ? <Navigate to={spaceHome} replace />
            : <SpaceOutlet key={activeOrganization?.id ?? 'no-school'} />}
        </div>
      </div>
    )
  }

  const roleHome = space === 'teacher' ? '/app/teacher' : '/app/student'
  const profilePath =
    space === 'teacher' ? '/app/teacher/profile' : '/app/student/profile'
  const supportPath =
    space === 'teacher' ? '/app/teacher/support' : '/app/student/support'
  const roleLabel = workspaceLabels[space]
  const schoolName = activeOrganization?.name || 'Académie des Créatifs'
  const schoolLogo = activeOrganization?.logo_url

  function returnToSchoolSite() {
    setProfileOpen(false)
    if (activeOrganization?.slug) {
      navigate(`/school/${activeOrganization.slug}`)
      return
    }
    navigate('/')
  }

  return (
    <div
      className={`tenant-role-shell tenant-role-shell--${space}`}
      style={brandStyle}
    >
      {sidebarOpen && (
        <button
          type="button"
          className="tenant-role-backdrop"
          aria-label="Fermer le menu"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside className={`tenant-role-sidebar${sidebarOpen ? ' is-open' : ''}`}>
        <NavLink className="tenant-role-brand" to={roleHome}>
          <SchoolLogo
            logoUrl={schoolLogo}
            alt={schoolName}
            className="tenant-role-brand__logo"
          />
          <span>
            <strong>{schoolName}</strong>
            <small>{roleLabel}</small>
          </span>
        </NavLink>

        <div className="tenant-role-badge">
          ESPACE {space === 'teacher' ? 'ENSEIGNANT' : 'ÉTUDIANT'}
        </div>

        <nav className="tenant-role-nav">
          {navItems.map((item) => (
            <MenuLink key={item.to} to={item.to} end={item.end}>
              <span>{item.icon}</span>
              {item.label}
            </MenuLink>
          ))}
          {navGroups.map((group) => {
            const isOpen = openNavGroups.includes(group.key)
            const isActive = group.items.some((item) => navItemMatches(location.pathname, item))
            return (
              <div
                key={group.key}
                className={`tenant-role-nav-group${isOpen ? ' is-open' : ''}${isActive ? ' is-active' : ''}`}
              >
                <button
                  type="button"
                  className="tenant-role-nav-group__trigger"
                  onClick={() => toggleNavGroup(group.key)}
                  aria-expanded={isOpen}
                  aria-controls={`role-nav-${group.key}`}
                >
                  <span className="tenant-role-nav-group__icon">{group.icon}</span>
                  <span className="tenant-role-nav-group__label">{group.label}</span>
                  <ChevronDown className="tenant-role-nav-group__chevron" size={15} />
                </button>
                <div
                  id={`role-nav-${group.key}`}
                  className="tenant-role-nav-subnav"
                  hidden={!isOpen}
                >
                  {group.items.map((item) => (
                    <MenuLink key={item.to} to={item.to} end={item.end}>
                      <span>{item.icon}</span>
                      {item.label}
                    </MenuLink>
                  ))}
                </div>
              </div>
            )
          })}
          {trailingNavItems.map((item) => (
            <MenuLink key={item.to} to={item.to} end={item.end}>
              <span>{item.icon}</span>
              {item.label}
            </MenuLink>
          ))}
        </nav>

        <div className="tenant-role-sidebar__bottom">
          <div className="tenant-role-user-pill">
            <div className="tenant-role-avatar">
              {user?.avatar_url ? (
                <img src={user.avatar_url} alt={user.full_name} />
              ) : (
                initialsFor(user?.full_name)
              )}
            </div>
            <div>
              <strong>{user?.full_name}</strong>
              <small>{roleLabel}</small>
            </div>
          </div>

          {!schoolBranding?.white_label && <div className="tenant-role-powered">
            <small>Powered by</small>
            <span>
              <BrandLogo
                logoUrl={DEFAULT_PLATFORM_LOGO_URL}
                alt="Académie des Créatifs"
                className="tenant-role-powered__logo"
              />
              <strong>Académie des Créatifs</strong>
            </span>
          </div>}
        </div>
      </aside>

      <div className="tenant-role-main">
        <header className="tenant-role-topbar">
          <button
            type="button"
            className="tenant-role-menu"
            onClick={() => setSidebarOpen((value) => !value)}
            aria-label={sidebarOpen ? 'Fermer le menu' : 'Ouvrir le menu'}
          >
            {sidebarOpen ? <X size={19} /> : <Menu size={19} />}
          </button>

          <strong className="tenant-role-topbar__title">{currentLabel}</strong>

          <div className="tenant-role-search">
            <Search size={16} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Rechercher..."
              aria-label="Rechercher dans cet espace"
            />
            {searchResults.length > 0 && (
              <div className="tenant-role-search__results">
                {searchResults.map((item) => (
                  <button
                    type="button"
                    key={item.to}
                    onClick={() => {
                      navigate(item.to)
                      setSearch('')
                    }}
                  >
                    {item.icon}
                    <span>{item.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="tenant-role-topbar__actions" ref={profileRef}>
            <SchoolMessageBell space={space} />
            <SchoolNotificationBell space={space} />

            <button
              type="button"
              className="tenant-role-profile-button"
              onClick={() => setProfileOpen((value) => !value)}
              aria-expanded={profileOpen}
            >
              <span className="tenant-role-avatar tenant-role-avatar--header">
                {user?.avatar_url ? (
                  <img src={user.avatar_url} alt={user.full_name} />
                ) : (
                  initialsFor(user?.full_name)
                )}
              </span>
              <span>
                <strong>{user?.full_name}</strong>
                <small>{roleLabel}</small>
              </span>
              <ChevronDown size={14} />
            </button>

            {profileOpen && (
              <div className="tenant-role-profile-menu">
                <div className="tenant-role-profile-menu__head">
                  <span className="tenant-role-avatar">
                    {user?.avatar_url ? (
                      <img src={user.avatar_url} alt={user.full_name} />
                    ) : (
                      initialsFor(user?.full_name)
                    )}
                  </span>
                  <div>
                    <strong>{user?.full_name}</strong>
                    <small>{user?.email}</small>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => { setProfileOpen(false); navigate(profilePath) }}
                >
                  <UserRound size={19} />
                  Mon profil
                </button>
                <button
                  type="button"
                  onClick={() => { setProfileOpen(false); navigate(`${profilePath}?section=security`) }}
                >
                  <Settings size={19} />
                  Paramètres du compte
                </button>
                <button
                  type="button"
                  onClick={returnToSchoolSite}
                >
                  <ExternalLink size={19} />
                  Retour au site
                </button>
                <button
                  type="button"
                  onClick={() => { setProfileOpen(false); navigate(supportPath) }}
                >
                  <LifeBuoy size={19} />
                  Support
                </button>
                <span className="account-menu-divider" aria-hidden="true" />
                <button
                  type="button"
                  className="is-danger"
                  onClick={handleSignOut}
                >
                  <Power size={19} />
                  Se déconnecter
                </button>
              </div>
            )}
          </div>
        </header>

        {supportMode && (
          <div className="support-mode-banner">
            <div>
              <span className="support-mode-icon"><Eye size={17} /></span>
              <span>
                <strong>
                  Mode support - {supportMode.organization_name}
                </strong>
                <small>Lecture seule</small>
              </span>
            </div>
            <button type="button" onClick={() => void leaveSupportMode()}>
              Quitter le mode support
            </button>
          </div>
        )}

        <main className="tenant-role-content">
          <SpaceOutlet key={activeOrganization?.id ?? 'no-school'} />
        </main>
      </div>
    </div>
  )
}
