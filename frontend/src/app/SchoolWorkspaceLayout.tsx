import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
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
  Power,
  Search,
  Settings,
  UserRound,
  X,
} from 'lucide-react'
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
  DEFAULT_PLATFORM_LOGO_URL,
} from '../brand/branding'
import {
  endAdminSupportMode,
  updateCurrentOrganization,
  type Organization,
  type OrganizationAccessProfile,
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
  onSelectOrganization,
  onSwitchWorkspace,
  onOpenChange,
}: {
  variant: 'direction' | 'role'
  currentSpace: WorkspaceSpace
  collapsed?: boolean
  organizations: Organization[]
  activeOrganization: Organization | null
  accessProfile: OrganizationAccessProfile | null
  profileLoading: boolean
  supportMode?: boolean
  onSelectOrganization: (id: number) => void
  onSwitchWorkspace: (space: WorkspaceSpace) => void
  onOpenChange?: (open: boolean) => void
}) {
  const [open, setOpen] = useState(false)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const canSwitchSchool = !supportMode && organizations.length > 1
  const availableSpaces = supportMode ? [] : accessProfile?.spaces ?? []
  const canSwitchSpace = availableSpaces.length > 1
  const canOpen = !supportMode && Boolean(activeOrganization)
  const schoolName = activeOrganization?.name || 'Aucune école'
  const triggerLabel = supportMode
    ? 'École consultée'
    : variant === 'direction'
      ? 'École active'
      : 'Espace actif'
  const triggerValue = variant === 'direction' ? schoolName : workspaceMenuLabels[currentSpace]

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
          <span className="school-switcher-initial" aria-hidden="true">
            {schoolName.trim().charAt(0).toUpperCase() || '?'}
          </span>
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
                      <span><strong>{organization.name}</strong>{selected && <small>École active</small>}</span>
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
                      <span><strong>{workspaceMenuLabels[item]}</strong>{selected && <small>Espace actuel</small>}</span>
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
        </div>
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
  const [savingSidebarPreference, setSavingSidebarPreference] = useState(false)
  const [supportsCompactSidebar, setSupportsCompactSidebar] = useState(() => window.matchMedia('(min-width: 1024px)').matches)
  const [profileOpen, setProfileOpen] = useState(false)
  const [workspaceSwitcherOpen, setWorkspaceSwitcherOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [openNavGroups, setOpenNavGroups] = useState<string[]>(
    () => space === 'student' && navGroups[0] ? [navGroups[0].key] : [],
  )
  const profileRef = useRef<HTMLDivElement>(null)

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
  const directionSidebarCollapsed = !isRoleSpace
    && activeOrganization?.direction_sidebar_collapsed === true
    && supportsCompactSidebar

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
    const query = search.trim().toLocaleLowerCase('fr-FR')
    if (!query) return []
    return allNavItems
      .filter((item) => item.label.toLocaleLowerCase('fr-FR').includes(query))
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

  async function toggleDirectionSidebar() {
    if (!activeOrganization || savingSidebarPreference) return
    setSavingSidebarPreference(true)
    try {
      await updateCurrentOrganization({
        direction_sidebar_collapsed: !activeOrganization.direction_sidebar_collapsed,
      })
      await refreshOrganizations()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Impossible de modifier la barre latérale.')
    } finally {
      setSavingSidebarPreference(false)
    }
  }

  if (!isRoleSpace) {
    return (
      <div className={`saas-app${directionSidebarCollapsed ? ' is-manage-sidebar-collapsed' : ''}`} style={brandStyle}>
        {sidebarOpen && <button className="manage-sidebar-backdrop" type="button" aria-label="Fermer le menu" onClick={() => setSidebarOpen(false)} />}
        <aside className={`app-sidebar${sidebarOpen ? ' is-open' : ''}${directionSidebarCollapsed ? ' is-collapsed' : ''}${workspaceSwitcherOpen ? ' has-workspace-menu-open' : ''}`}>
          <div className="app-brand">
            <DirectionWordmark accentColor={directionAccent} />
          </div>
          {activeOrganization
            && !supportMode
            && ['owner', 'admin', 'super_admin'].includes(accessProfile?.primary_role || '')
            && supportsCompactSidebar && <button
              type="button"
              className="sidebar-collapse-toggle"
              onClick={() => void toggleDirectionSidebar()}
              disabled={savingSidebarPreference}
              aria-label={directionSidebarCollapsed ? 'Développer la barre latérale' : 'Rétracter la barre latérale'}
              title={directionSidebarCollapsed ? 'Développer la barre latérale' : 'Rétracter la barre latérale'}
            >
              {directionSidebarCollapsed ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}
            </button>}

          <SchoolWorkspaceSwitcher
            variant="direction"
            currentSpace={space}
            collapsed={directionSidebarCollapsed}
            organizations={organizations}
            activeOrganization={activeOrganization}
            accessProfile={accessProfile}
            profileLoading={profileLoading}
            supportMode={Boolean(supportMode)}
            onSelectOrganization={(id) => {
              selectOrganization(id)
              navigate('/app')
            }}
            onSwitchWorkspace={switchWorkspace}
            onOpenChange={setWorkspaceSwitcherOpen}
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
                    {new Intl.DateTimeFormat('fr-FR', {
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

      <aside className={`tenant-role-sidebar${sidebarOpen ? ' is-open' : ''}${workspaceSwitcherOpen ? ' has-workspace-menu-open' : ''}`}>
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

        <SchoolWorkspaceSwitcher
          variant="role"
          currentSpace={space}
          organizations={organizations}
          activeOrganization={activeOrganization}
          accessProfile={accessProfile}
          profileLoading={profileLoading}
          supportMode={Boolean(supportMode)}
          onSelectOrganization={(id) => {
            selectOrganization(id)
            navigate('/app')
          }}
          onSwitchWorkspace={switchWorkspace}
          onOpenChange={setWorkspaceSwitcherOpen}
        />

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
