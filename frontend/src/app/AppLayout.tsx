import type { CSSProperties } from 'react'
import {
  BookOpen,
  Building2,
  ChevronDown,
  CreditCard,
  LayoutDashboard,
  LogOut,
  Settings,
  Users,
} from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { BrandLogo } from '../brand/BrandLogo'
import { DEFAULT_BRAND_COLORS, resolveBrandLogo } from '../brand/branding'
import { useTenant } from './TenantContext'

export function AppLayout() {
  const navigate = useNavigate()
  const { user, signOut } = useAuth()
  const {
    organizations,
    activeOrganization,
    selectOrganization,
  } = useTenant()

  const brandStyle = {
    '--blue': activeOrganization?.primary_color || DEFAULT_BRAND_COLORS.primary,
    '--green': activeOrganization?.secondary_color || DEFAULT_BRAND_COLORS.secondary,
    '--tenant-accent': activeOrganization?.accent_color || DEFAULT_BRAND_COLORS.accent,
  } as CSSProperties

  const activeLogo = resolveBrandLogo(activeOrganization?.logo_url)

  return (
    <div className="saas-app" style={brandStyle}>
      <aside className="app-sidebar">
        <div className="app-brand">
          <BrandLogo
            logoUrl={activeLogo}
            alt={activeOrganization?.name || 'Académie des Créatifs'}
            className="app-brand-logo"
          />
          <span>{activeOrganization?.name || 'Académie'} <strong>SaaS</strong></span>
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
            <small>École active</small>
            <span className="select-shell">
              <select
                value={activeOrganization?.id ?? ''}
                onChange={(event) => selectOrganization(Number(event.target.value))}
                disabled={organizations.length === 0}
              >
                {organizations.length === 0 && <option value="">Aucune école</option>}
                {organizations.map((organization) => (
                  <option key={organization.id} value={organization.id}>
                    {organization.name}
                  </option>
                ))}
              </select>
              <ChevronDown size={14} />
            </span>
          </label>
        </div>

        <nav className="app-nav">
          <NavLink to="/app" end>
            <LayoutDashboard size={18} /> Tableau de bord
          </NavLink>
          <span className="nav-disabled"><BookOpen size={18} /> Formations <small>Bientôt</small></span>
          <NavLink to="/app/team">
            <Users size={18} /> Équipe & accès
          </NavLink>
          <NavLink to="/app/billing">
            <CreditCard size={18} /> Abonnement
          </NavLink>
          <NavLink to="/app/settings">
            <Settings size={18} /> Paramètres
          </NavLink>
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
            <small>{user?.email}</small>
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
        <Outlet />
      </div>
    </div>
  )
}
