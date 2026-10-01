import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { TenantProvider } from './app/TenantContext'
import { AppLayout } from './app/AppLayout'
import LandingPage from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { SchoolDashboardPage } from './pages/SchoolDashboardPage'
import { TeamPage } from './pages/TeamPage'
import { SchoolSettingsPage } from './pages/SchoolSettingsPage'
import { BillingPage } from './pages/BillingPage'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()

  if (loading) {
    return <div className="app-loading">Chargement de votre espace…</div>
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return children
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <TenantProvider>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/app"
              element={
                <RequireAuth>
                  <AppLayout />
                </RequireAuth>
              }
            >
              <Route index element={<SchoolDashboardPage />} />
              <Route path="team" element={<TeamPage />} />
              <Route path="billing" element={<BillingPage />} />
              <Route path="settings" element={<SchoolSettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </TenantProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
