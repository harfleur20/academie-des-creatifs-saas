import type { CSSProperties, ReactNode } from 'react'
import {
  Building2,
  ChevronDown,
  Eye,
  LogOut,
} from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
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
  teacher: 'Professeur',
  student: 'Étudiant',
}

export function SchoolWorkspaceLayout({
  space,
  navItems,
}: {
  space: WorkspaceSpace
  navItems: WorkspaceNavItem[]
}) {
  const navigate = useNavigate()
  const { user, signOut, supportMode } = useAuth()
  const {
    organizations,
    activeOrganization,
    accessProfile,
    selectOrganization,
  } = useTenant()

  const brandStyle = {
    '--blue': activeOrganization?.primary_color || DEFAULT_BRAND_COLORS.primary,
    '--green': activeOrganization?.secondary_color || DEFAULT_BRAND_COLORS.secondary,
    '--tenant-accent': activeOrganization?.accent_color || DEFAULT_BRAND_COLORS.accent,
  } as CSSProperties

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
                {organizations.length === 0 && <option value="">Aucune école</option>}
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
              onChange={(event) => switchWorkspace(event.target.value as WorkspaceSpace)}
            >
              {accessProfile.spaces.map((item) => (
                <option key={item} value={item}>{workspaceLabels[item]}</option>
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
            {user?.full_name
              .split(' ')
              .slice(0, 2)
              .map((part) => part[0]?.toUpperCase())
              .join('')}
          </div>
          <div>
            <strong>{user?.full_name}</strong>
            <small>
              {supportMode
                ? 'Super-admin · support'
                : `${workspaceLabels[space]} · ${user?.email || ''}`}
            </small>
          </div>
          <button
            title="Se déconnecter"
            onClick={() => {
              signOut()
              navigate('/login')
            }}
          >
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
                <strong>Mode support — {supportMode.organization_name}</strong>
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
