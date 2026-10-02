import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from 'react'
import {
  Bell,
  Building2,
  ChevronDown,
  Eye,
  LogOut,
  Menu,
  MessageCircle,
  Search,
  Settings,
  UserRound,
  X,
} from 'lucide-react'
import {
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { BrandLogo } from '../brand/BrandLogo'
import {
  DEFAULT_BRAND_COLORS,
  DEFAULT_PLATFORM_LOGO_URL,
} from '../brand/branding'
import {
  endAdminSupportMode,
  type WorkspaceSpace,
} from '../lib/api'
import { useTenant } from './TenantContext'

export type WorkspaceNavItem = {
  to: string
  label: string
  icon: ReactNode
  end?: boolean
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

export function SchoolWorkspaceLayout({
  space,
  navItems,
}: {
  space: WorkspaceSpace
  navItems: WorkspaceNavItem[]
}) {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, signOut, supportMode } = useAuth()
  const {
    organizations,
    activeOrganization,
    accessProfile,
    selectOrganization,
  } = useTenant()

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [search, setSearch] = useState('')
  const profileRef = useRef<HTMLDivElement>(null)

  const isRoleSpace = space === 'teacher' || space === 'student'
  const organizationPrimary =
    activeOrganization?.primary_color || DEFAULT_BRAND_COLORS.primary
  const organizationSecondary =
    activeOrganization?.secondary_color || DEFAULT_BRAND_COLORS.secondary
  const organizationAccent =
    activeOrganization?.accent_color || DEFAULT_BRAND_COLORS.accent

  // Important: school identity only skins student/teacher spaces.
  // The owner/admin management workspace keeps the platform identity.
  const brandStyle = {
    '--blue': isRoleSpace
      ? organizationPrimary
      : DEFAULT_BRAND_COLORS.primary,
    '--green': isRoleSpace
      ? organizationSecondary
      : DEFAULT_BRAND_COLORS.secondary,
    '--tenant-accent': isRoleSpace
      ? organizationAccent
      : DEFAULT_BRAND_COLORS.accent,
    '--school-primary': organizationPrimary,
    '--school-secondary': organizationSecondary,
    '--school-accent': organizationAccent,
  } as CSSProperties

  const currentLabel =
    navItems.find((item) => (
      location.pathname === item.to
      || (!item.end && location.pathname.startsWith(item.to))
    ))?.label
    || workspaceLabels[space]

  const searchResults = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('fr-FR')
    if (!query) return []
    return navItems
      .filter((item) => item.label.toLocaleLowerCase('fr-FR').includes(query))
      .slice(0, 6)
  }, [navItems, search])

  useEffect(() => {
    setSidebarOpen(false)
    setProfileOpen(false)
    setSearch('')
  }, [location.pathname])

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
    signOut()
    navigate('/login')
  }

  if (!isRoleSpace) {
    return (
      <div className="saas-app" style={brandStyle}>
        <aside className="app-sidebar">
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
            <span className="school-switcher-icon">
              {activeOrganization?.logo_url ? (
                <BrandLogo
                  logoUrl={activeOrganization.logo_url}
                  alt={activeOrganization.name}
                  className="school-switcher-logo"
                />
              ) : (
                <Building2 size={18} />
              )}
            </span>
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
              <NavLink key={item.to} to={item.to} end={item.end}>
                {item.icon} {item.label}
              </NavLink>
            ))}
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
          <Outlet />
        </div>
      </div>
    )
  }

  const roleHome = space === 'teacher' ? '/app/teacher' : '/app/student'
  const profilePath =
    space === 'teacher' ? '/app/teacher/profile' : '/app/student/profile'
  const roleLabel = workspaceLabels[space]
  const schoolName = activeOrganization?.name || 'Académie des Créatifs'
  const schoolLogo = activeOrganization?.logo_url || '/logo_academie_hd.png'

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
          <BrandLogo
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
            <NavLink key={item.to} to={item.to} end={item.end}>
              <span>{item.icon}</span>
              {item.label}
            </NavLink>
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

          <div className="tenant-role-powered">
            <small>Powered by</small>
            <span>
              <BrandLogo
                logoUrl={DEFAULT_PLATFORM_LOGO_URL}
                alt="Académie des Créatifs"
                className="tenant-role-powered__logo"
              />
              <strong>Académie des Créatifs</strong>
            </span>
          </div>
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
            <button
              type="button"
              className="tenant-role-icon-button"
              aria-label="Messages"
              title="Messages"
            >
              <MessageCircle size={19} />
            </button>
            <button
              type="button"
              className="tenant-role-icon-button"
              aria-label="Notifications"
              title="Notifications"
            >
              <Bell size={19} />
            </button>

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
                  onClick={() => navigate(profilePath)}
                >
                  <UserRound size={15} />
                  Mon profil
                </button>
                <button
                  type="button"
                  onClick={() => navigate(profilePath)}
                >
                  <Settings size={15} />
                  Paramètres du compte
                </button>
                <button
                  type="button"
                  className="is-danger"
                  onClick={handleSignOut}
                >
                  <LogOut size={15} />
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
          <Outlet />
        </main>
      </div>
    </div>
  )
}
