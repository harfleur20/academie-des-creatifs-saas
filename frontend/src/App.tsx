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
import { AdminLayout } from './admin/AdminLayout'
import { AdminDashboardPage } from './pages/AdminDashboardPage'
import { AdminSchoolsPage } from './pages/AdminSchoolsPage'
import { AdminSchoolDetailPage } from './pages/AdminSchoolDetailPage'
import { AdminPlansPage } from './pages/AdminPlansPage'
import { OnboardingPage } from './pages/OnboardingPage'
import { FormationsManagementPage } from './pages/FormationsManagementPage'
import { FormationWorkspacePage } from './pages/FormationWorkspacePage'

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

function RequireSchoolUser({ children }: { children: React.ReactNode }) {
  const { user, supportMode, loading } = useAuth()

  if (loading) {
    return <div className="app-loading">Chargement de votre espace…</div>
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (user.platform_role === 'super_admin' && !supportMode) {
    return <Navigate to="/admin" replace />
  }

  return children
}

function RequireSuperAdmin({ children }: { children: React.ReactNode }) {
  const { user, supportMode, loading } = useAuth()

  if (loading) {
    return <div className="app-loading">Chargement de l’administration…</div>
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (supportMode) {
    return <Navigate to="/app" replace />
  }

  if (user.platform_role !== 'super_admin') {
    return <Navigate to="/app" replace />
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
                <RequireSchoolUser>
                  <AppLayout />
                </RequireSchoolUser>
              }
            >
              <Route index element={<SchoolDashboardPage />} />
              <Route path="onboarding" element={<OnboardingPage />} />
              <Route path="formations" element={<FormationsManagementPage />} />
              <Route path="formations/:formationId" element={<FormationWorkspacePage />} />
              <Route path="team" element={<TeamPage />} />
              <Route path="billing" element={<BillingPage />} />
              <Route path="settings" element={<SchoolSettingsPage />} />
            </Route>
            <Route
              path="/admin"
              element={
                <RequireSuperAdmin>
                  <AdminLayout />
                </RequireSuperAdmin>
              }
            >
              <Route index element={<AdminDashboardPage />} />
              <Route path="schools" element={<AdminSchoolsPage />} />
              <Route path="schools/:schoolId" element={<AdminSchoolDetailPage />} />
              <Route path="plans" element={<AdminPlansPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </TenantProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
