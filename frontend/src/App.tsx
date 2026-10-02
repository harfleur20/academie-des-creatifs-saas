import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { TenantProvider, useTenant } from './app/TenantContext'
import { AppLayout } from './app/AppLayout'
import { TeacherLayout } from './app/TeacherLayout'
import { StudentLayout } from './app/StudentLayout'
import LandingPage from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { InvitationAcceptPage } from './pages/InvitationAcceptPage'
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
import { TeacherDashboardPage } from './pages/TeacherDashboardPage'
import { StudentDashboardPage } from './pages/StudentDashboardPage'
import { TeacherSessionPlanningPage } from './pages/TeacherSessionPlanningPage'
import { StudentSessionPlanningPage } from './pages/StudentSessionPlanningPage'
import { TeacherAssignmentsPage } from './pages/TeacherAssignmentsPage'
import { StudentAssignmentsPage } from './pages/StudentAssignmentsPage'
import { TeacherResourcesPage } from './pages/TeacherResourcesPage'
import { StudentResourcesPage } from './pages/StudentResourcesPage'
import { TeacherQuizzesPage } from './pages/TeacherQuizzesPage'
import { StudentQuizzesPage } from './pages/StudentQuizzesPage'
import { TeacherCoursesPage } from './pages/TeacherCoursesPage'
import { StudentCoursesPage } from './pages/StudentCoursesPage'
import { TeacherAttendancePage } from './pages/TeacherAttendancePage'
import { TeacherPerformancePage } from './pages/TeacherPerformancePage'
import { TeacherStudentsPage } from './pages/TeacherStudentsPage'
import { StudentResultsPage } from './pages/StudentResultsPage'
import { StudentProgressPage } from './pages/StudentProgressPage'
import { StudentClassPage } from './pages/StudentClassPage'
import { StudentCertificatesPage } from './pages/StudentCertificatesPage'
import { StudentPlanningPage } from './pages/StudentPlanningPage'
import { CertificateVerifyPage } from './pages/CertificateVerifyPage'
import { SchoolPublicSitePage } from './pages/SchoolPublicSitePage'
import { StudentsManagementPage } from './pages/StudentsManagementPage'
import { TeachersManagementPage } from './pages/TeachersManagementPage'
import { CommerceDashboardPage } from './pages/CommerceDashboardPage'
import { PromotionsPage } from './pages/PromotionsPage'
import { PedagogicalMonitoringPage } from './pages/PedagogicalMonitoringPage'
import { SchoolPerformancePage } from './pages/SchoolPerformancePage'
import { StudentProfilePage, TeacherProfilePage } from './pages/ProfilePage'
import { SchoolPublicLayout } from './public/SchoolPublicLayout'
import { SchoolHomePage } from './pages/SchoolHomePage'
import { SchoolFormationsPage } from './pages/SchoolFormationsPage'
import { SchoolFormationDetailPage } from './pages/SchoolFormationDetailPage'
import { SchoolContactPage } from './pages/SchoolContactPage'
import { SchoolLegalPage } from './pages/SchoolLegalPage'
import { SchoolCartPage } from './pages/SchoolCartPage'
import { SchoolCheckoutPage } from './pages/SchoolCheckoutPage'
import type { WorkspaceSpace } from './lib/api'

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

function WorkspaceEntry() {
  const { activeOrganization, accessProfile, loading, profileLoading } = useTenant()

  if (loading || profileLoading) {
    return <div className="app-loading">Préparation de votre espace…</div>
  }

  if (!activeOrganization) {
    return <Navigate to="/app/manage" replace />
  }

  if (!accessProfile || accessProfile.spaces.length === 0) {
    return <div className="app-loading">Aucun espace disponible pour ce compte.</div>
  }

  const stored = localStorage.getItem('academie_saas_workspace_space') as WorkspaceSpace | null
  const target = stored && accessProfile.spaces.includes(stored)
    ? stored
    : accessProfile.default_space

  return <Navigate to={`/app/${target}`} replace />
}

function RequireWorkspace({
  space,
  children,
}: {
  space: WorkspaceSpace
  children: React.ReactNode
}) {
  const { supportMode } = useAuth()
  const { activeOrganization, accessProfile, loading, profileLoading } = useTenant()

  if (loading || profileLoading) {
    return <div className="app-loading">Chargement de votre espace…</div>
  }

  if (!activeOrganization) {
    return space === 'manage'
      ? children
      : <Navigate to="/app/manage" replace />
  }

  if (supportMode && space !== 'manage') {
    return <Navigate to="/app/manage" replace />
  }

  if (!accessProfile?.spaces.includes(space)) {
    return <Navigate to="/app" replace />
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
            <Route path="/invite/:token" element={<InvitationAcceptPage />} />
            <Route path="/certificates/verify/:token" element={<CertificateVerifyPage />} />
            <Route path="/school/:schoolSlug" element={<SchoolPublicLayout />}>
              <Route index element={<SchoolHomePage />} />
              <Route path="formations" element={<SchoolFormationsPage />} />
              <Route path="formations/:formationSlug" element={<SchoolFormationDetailPage />} />
              <Route path="contact" element={<SchoolContactPage />} />
              <Route path="panier" element={<SchoolCartPage />} />
              <Route path="checkout" element={<SchoolCheckoutPage />} />
              <Route path="mentions-legales" element={<SchoolLegalPage />} />
              <Route path="cgv" element={<SchoolLegalPage />} />
              <Route path="confidentialite" element={<SchoolLegalPage />} />
              <Route path="remboursement" element={<SchoolLegalPage />} />
            </Route>

            <Route
              path="/app"
              element={
                <RequireSchoolUser>
                  <WorkspaceEntry />
                </RequireSchoolUser>
              }
            />

            <Route
              path="/app/manage"
              element={
                <RequireSchoolUser>
                  <RequireWorkspace space="manage">
                    <AppLayout />
                  </RequireWorkspace>
                </RequireSchoolUser>
              }
            >
              <Route index element={<SchoolDashboardPage />} />
              <Route path="onboarding" element={<OnboardingPage />} />
              <Route path="formations" element={<FormationsManagementPage />} />
              <Route path="formations/:formationId" element={<FormationWorkspacePage />} />
              <Route path="students" element={<StudentsManagementPage />} />
              <Route path="teachers" element={<TeachersManagementPage />} />
              <Route path="commerce" element={<CommerceDashboardPage />} />
              <Route path="promotions" element={<PromotionsPage />} />
              <Route path="pedagogy" element={<PedagogicalMonitoringPage />} />
              <Route path="performance" element={<SchoolPerformancePage />} />
              <Route path="site-public" element={<SchoolPublicSitePage />} />
              <Route path="team" element={<TeamPage />} />
              <Route path="billing" element={<BillingPage />} />
              <Route path="settings" element={<SchoolSettingsPage />} />
            </Route>

            <Route
              path="/app/teacher"
              element={
                <RequireSchoolUser>
                  <RequireWorkspace space="teacher">
                    <TeacherLayout />
                  </RequireWorkspace>
                </RequireSchoolUser>
              }
            >
              <Route index element={<TeacherDashboardPage />} />
              <Route path="sessions" element={<TeacherDashboardPage />} />
              <Route path="sessions/:sessionId" element={<TeacherSessionPlanningPage />} />
              <Route path="courses" element={<TeacherCoursesPage />} />
              <Route path="resources" element={<TeacherResourcesPage />} />
              <Route path="assignments" element={<TeacherAssignmentsPage />} />
              <Route path="quizzes" element={<TeacherQuizzesPage />} />
              <Route path="attendance" element={<TeacherAttendancePage />} />
              <Route path="students" element={<TeacherStudentsPage />} />
              <Route path="performance" element={<TeacherPerformancePage />} />
              <Route path="profile" element={<TeacherProfilePage />} />
            </Route>

            <Route
              path="/app/student"
              element={
                <RequireSchoolUser>
                  <RequireWorkspace space="student">
                    <StudentLayout />
                  </RequireWorkspace>
                </RequireSchoolUser>
              }
            >
              <Route index element={<StudentDashboardPage />} />
              <Route path="formations" element={<StudentDashboardPage />} />
              <Route path="sessions/:sessionId" element={<StudentSessionPlanningPage />} />
              <Route path="planning" element={<StudentPlanningPage />} />
              <Route path="courses" element={<StudentCoursesPage />} />
              <Route path="resources" element={<StudentResourcesPage />} />
              <Route path="assignments" element={<StudentAssignmentsPage />} />
              <Route path="quizzes" element={<StudentQuizzesPage />} />
              <Route path="results" element={<StudentResultsPage />} />
              <Route path="progress" element={<StudentProgressPage />} />
              <Route path="class" element={<StudentClassPage />} />
              <Route path="certificates" element={<StudentCertificatesPage />} />
              <Route path="profile" element={<StudentProfilePage />} />
            </Route>

            <Route path="/app/onboarding" element={<Navigate to="/app/manage/onboarding" replace />} />
            <Route path="/app/formations" element={<Navigate to="/app/manage/formations" replace />} />
            <Route path="/app/formations/:formationId" element={<LegacyFormationRedirect />} />
            <Route path="/app/team" element={<Navigate to="/app/manage/team" replace />} />
            <Route path="/app/billing" element={<Navigate to="/app/manage/billing" replace />} />
            <Route path="/app/settings" element={<Navigate to="/app/manage/settings" replace />} />

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

function LegacyFormationRedirect() {
  const formationId = window.location.pathname.split('/').pop()
  return <Navigate to={`/app/manage/formations/${formationId}`} replace />
}
