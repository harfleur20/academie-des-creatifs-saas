import {
  Building2,
  Gauge,
  LogOut,
  Plug,
  Settings2,
  Wallet,
} from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { BrandLogo } from '../brand/BrandLogo'

export function AdminLayout() {
  const navigate = useNavigate()
  const { user, signOut } = useAuth()

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <div className="admin-brand">
          <BrandLogo className="app-brand-logo" />
          <div>
            <strong>Académie des Créatifs</strong>
            <small>Administration plateforme</small>
          </div>
        </div>

        <nav className="admin-nav">
          <NavLink to="/admin" end>
            <Gauge size={18} />
            Vue d’ensemble
          </NavLink>
          <NavLink to="/admin/schools">
            <Building2 size={18} />
            Écoles
          </NavLink>
          <NavLink to="/admin/plans">
            <Settings2 size={18} />
            Plans & quotas
          </NavLink>
          <NavLink to="/admin/integrations">
            <Plug size={18} />
            Intégrations
          </NavLink>
          <NavLink to="/admin/payouts">
            <Wallet size={18} />
            Reversements
          </NavLink>
        </nav>

        <div className="admin-user">
          <div className="user-avatar">
            {user?.full_name
              .split(' ')
              .slice(0, 2)
              .map((part) => part[0]?.toUpperCase())
              .join('')}
          </div>
          <div>
            <strong>{user?.full_name}</strong>
            <small>Super-admin</small>
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

      <div className="admin-content">
        <Outlet />
      </div>
    </div>
  )
}
