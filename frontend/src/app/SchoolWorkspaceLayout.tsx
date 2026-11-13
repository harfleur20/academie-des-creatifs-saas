import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from 'react'
import {
  ChevronDown,
  Eye,
  ExternalLink,
  LifeBuoy,
  LogOut,
  Menu,
  Search,
  Settings,
  UserRound,
  X,
} from 'lucide-react'
import {
  NavLink,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { BrandLogo } from '../brand/BrandLogo'
import { SchoolLogo } from '../brand/SchoolLogo'
import {
  DEFAULT_BRAND_COLORS,
  DEFAULT_PLATFORM_LOGO_URL,
} from '../brand/branding'
import {
  endAdminSupportMode,
  type WorkspaceSpace,
} from '../lib/api'
import { useTenant } from './TenantContext'
import { SchoolNotificationBell } from './SchoolNotificationBell'
import { SchoolMessageBell } from './SchoolMessageBell'
import { MenuLink, SpaceOutlet } from '../components/DemoGate'

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
    selectOrganization,
    schoolBranding,
  } = useTenant()

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [openNavGroups, setOpenNavGroups] = useState<string[]>(
    () => space === 'student' && navGroups[0] ? [navGroups[0].key] : [],
  )
  const profileRef = useRef<HTMLDivElement>(null)

  const isRoleSpace = space === 'teacher' || space === 'student'
  const organizationPrimary =
    activeOrganization?.primary_color || DEFAULT_BRAND_COLORS.primary
  const organizationSecondary =
    activeOrganization?.secondary_color || DEFAULT_BRAND_COLORS.secondary
  const organizationAccent =
    activeOrganization?.accent_color || DEFAULT_BRAND_COLORS.accent

  const brandStyle = {
    '--blue': isRoleSpace
      ? organizationPrimary
      : DEFAULT_BRAND_COLORS.primary,
    '--green': isRoleSpace
      ? organizationSecondary
      : DEFAULT_BRAND_COLORS.secondary,
    '--button-end': isRoleSpace
      ? `color-mix(in srgb, ${organizationPrimary} 80%, white)`
      : '#35409A',
    '--tenant-accent': isRoleSpace
      ? organizationAccent
      : DEFAULT_BRAND_COLORS.accent,
    '--school-primary': organizationPrimary,
    '--school-secondary': organizationSecondary,
    '--school-accent': organizationAccent,
  } as CSSProperties

  const allNavItems = useMemo(
    () => [...navItems, ...navGroups.flatMap((group) => group.items), ...trailingNavItems],
    [navItems, navGroups, trailingNavItems],
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
    signOut()
    if (schoolSlug) {
      window.location.assign(`/school/${encodeURIComponent(schoolSlug)}`)
      return
    }
    navigate('/')
  }

  function toggleNavGroup(key: string) {
    setOpenNavGroups((current) => (
      current.includes(key)
        ? current.filter((item) => item !== key)
        : [...current, key]
    ))
  }

  if (!isRoleSpace) {
    return (
      <div className="saas-app" style={brandStyle}>
        {sidebarOpen && <button className="manage-sidebar-backdrop" type="button" aria-label="Fermer le menu" onClick={() => setSidebarOpen(false)} />}
        <aside className={`app-sidebar${sidebarOpen ? ' is-open' : ''}`}>
          <div className="app-brand">
            <BrandLogo
              logoUrl={DEFAULT_PLATFORM_LOGO_URL}
              alt="Académie des Créatifs"
              className="app-brand-logo"
            />
            <span className="app-brand-text">
              <strong>Académie des Créatifs</strong>
              <small>Premium Virtual School</small>
            </span>
          </div>

          <div className="school-switcher">
            <SchoolLogo
              logoUrl={activeOrganization?.logo_url}
              alt={activeOrganization?.name || 'École'}
              className="school-switcher-logo"
            />
            <label>
              <small>{supportMode ? 'École consultée' : 'École active'}</small>
              <span className="select-shell">
                <select
                  value={activeOrganization?.id ?? ''}
                  onChange={(event) => {
                    selectOrganization(Number(event.target.value))
                    navigate('/app')
                  }}
                  disabled={organizations.length === 0 || Boolean(supportMode)}
                >
                  {organizations.length === 0 && (
                    <option value="">Aucune école</option>
                  )}
                  {organizations.map((organization) => (
                    <option key={organization.id} value={organization.id}>
                      {organization.name}
                    </option>
                  ))}
                </select>
                {!supportMode && <ChevronDown size={14} />}
              </span>
            </label>
          </div>

          {accessProfile && accessProfile.spaces.length > 1 && (
            <div className="workspace-switcher">
              <small>Espace actif</small>
              <select
                value={space}
                onChange={(event) => (
                  switchWorkspace(event.target.value as WorkspaceSpace)
                )}
              >
                {accessProfile.spaces.map((item) => (
                  <option key={item} value={item}>
                    {workspaceLabels[item]}
                  </option>
                ))}
              </select>
            </div>
          )}

          <nav className="app-nav">
            {navItems.map((item) => (
              <MenuLink key={item.to} to={item.to} end={item.end}>
                {item.icon} {item.label}
              </MenuLink>
            ))}
            {navGroups.map((group) => {
              const isOpen = openNavGroups.includes(group.key)
              const isActive = group.items.some((item) => navItemMatches(location.pathname, item))
              return (
                <div key={group.key} className={`app-nav-group${isOpen ? ' is-open' : ''}${isActive ? ' is-active' : ''}`}>
                  <button
                    type="button"
                    className="app-nav-group-trigger"
                    onClick={() => toggleNavGroup(group.key)}
                    aria-expanded={isOpen}
                  >
                    {group.icon}
                    <span>{group.label}</span>
                    <ChevronDown className="app-nav-group-chevron" size={14} />
                  </button>
                  {isOpen && (
                    <div className="app-nav-subnav">
                      {group.items.map((item) => (
                        <MenuLink key={item.to} to={item.to} end={item.end}>
                          {item.icon} {item.label}
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
            <button title="Se déconnecter" onClick={handleSignOut}>
              <LogOut size={17} />
            </button>
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
              {activeOrganization && <NavLink className="manage-topbar-site" to={`/school/${activeOrganization.slug}`} target="_blank" rel="noopener noreferrer" title="Voir le site public"><ExternalLink size={17} /><span>Voir le site</span></NavLink>}
              <SchoolNotificationBell space="manage" />
              <button type="button" className="manage-topbar-profile" onClick={() => setProfileOpen((value) => !value)} aria-expanded={profileOpen} aria-label="Ouvrir le menu du compte">
                <span className="manage-topbar-avatar">{user?.avatar_url ? <img src={user.avatar_url} alt="" /> : initialsFor(user?.full_name)}</span>
                <span className="manage-topbar-profile-label"><strong>{user?.full_name || 'Administrateur'}</strong><small>{activeOrganization?.name || 'Gestion de l’école'}</small></span>
                <ChevronDown size={15} />
              </button>
              {profileOpen && <div className="manage-topbar-profile-menu">
                <div><strong>{user?.full_name}</strong><small>{user?.email}</small></div>
                <button type="button" onClick={() => { setProfileOpen(false); navigate('/app/manage/profile') }}><UserRound size={16} /> Profil</button>
                <button type="button" onClick={() => { setProfileOpen(false); navigate('/app/manage/settings') }}><Settings size={16} /> Paramètres de l’école</button>
                <button type="button" onClick={() => { setProfileOpen(false); navigate('/app/manage/support') }}><LifeBuoy size={16} /> Support</button>
                <span className="account-menu-divider" aria-hidden="true" />
                <button type="button" className="is-danger" onClick={() => { setProfileOpen(false); handleSignOut() }}><LogOut size={16} /> Se déconnecter</button>
              </div>}
            </div>
          </header>
          {supportMode && (
            <div className="support-mode-banner">
              <div>
                <span className="support-mode-icon"><Eye size={17} /></span>
                <span>
                  <strong>
                    Mode support — {supportMode.organization_name}
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
          <SpaceOutlet key={activeOrganization?.id ?? 'no-school'} />
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

        {organizations.length > 1 && !supportMode && (
          <label className="tenant-role-school-select">
            <small>École</small>
            <select
              value={activeOrganization?.id ?? ''}
              onChange={(event) => {
                selectOrganization(Number(event.target.value))
                navigate(roleHome)
              }}
            >
              {organizations.map((organization) => (
                <option key={organization.id} value={organization.id}>
                  {organization.name}
                </option>
              ))}
            </select>
          </label>
        )}

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
                  <LogOut size={19} />
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
                  Mode support — {supportMode.organization_name}
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
