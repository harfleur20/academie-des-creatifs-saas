import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from 'react-router-dom'
import { lazy, Suspense } from 'react'
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
const SchoolSettingsPage = lazy(() => import('./pages/SchoolSettingsPage').then((module) => ({ default: module.SchoolSettingsPage })))
const BillingPage = lazy(() => import('./pages/BillingPage').then((module) => ({ default: module.BillingPage })))
import { AdminLayout } from './admin/AdminLayout'
import { AdminDashboardPage } from './pages/AdminDashboardPage'
import { AdminSchoolsPage } from './pages/AdminSchoolsPage'
const AdminSchoolDetailPage = lazy(() => import('./pages/AdminSchoolDetailPage').then((module) => ({ default: module.AdminSchoolDetailPage })))
const AdminPlansPage = lazy(() => import('./pages/AdminPlansPage').then((module) => ({ default: module.AdminPlansPage })))
import { OnboardingPage } from './pages/OnboardingPage'
import { FormationsManagementPage } from './pages/FormationsManagementPage'
const FormationWorkspacePage = lazy(() => import('./pages/FormationWorkspacePage').then((module) => ({ default: module.FormationWorkspacePage })))
import { TeacherDashboardPage } from './pages/TeacherDashboardPage'
import { TeacherSessionsPage } from './pages/TeacherSessionsPage'
import { StudentDashboardPage } from './pages/StudentDashboardPage'
import { TeacherSessionPlanningPage } from './pages/TeacherSessionPlanningPage'
import { StudentSessionPlanningPage } from './pages/StudentSessionPlanningPage'
const TeacherAssignmentsPage = lazy(() => import('./pages/TeacherAssignmentsPage').then((module) => ({ default: module.TeacherAssignmentsPage })))
const StudentAssignmentsPage = lazy(() => import('./pages/StudentAssignmentsPage').then((module) => ({ default: module.StudentAssignmentsPage })))
import { TeacherResourcesPage } from './pages/TeacherResourcesPage'
import { StudentResourcesPage } from './pages/StudentResourcesPage'
const TeacherQuizzesPage = lazy(() => import('./pages/TeacherQuizzesPage').then((module) => ({ default: module.TeacherQuizzesPage })))
const StudentQuizzesPage = lazy(() => import('./pages/StudentQuizzesPage').then((module) => ({ default: module.StudentQuizzesPage })))
const TeacherCoursesPage = lazy(() => import('./pages/TeacherCoursesPage').then((module) => ({ default: module.TeacherCoursesPage })))
const StudentCoursesPage = lazy(() => import('./pages/StudentCoursesPage').then((module) => ({ default: module.StudentCoursesPage })))
const StudentGuidedWorkspacePage = lazy(() => import('./pages/StudentGuidedWorkspacePage').then((module) => ({ default: module.StudentGuidedWorkspacePage })))
const StudentParcoursPage = lazy(() => import('./pages/StudentParcoursPage').then((module) => ({ default: module.StudentParcoursPage })))
import { TeacherAttendancePage } from './pages/TeacherAttendancePage'
import { TeacherPerformancePage } from './pages/TeacherPerformancePage'
import { TeacherStudentsPage } from './pages/TeacherStudentsPage'
import { StudentResultsPage } from './pages/StudentResultsPage'
import { StudentProgressPage } from './pages/StudentProgressPage'
import { StudentClassPage } from './pages/StudentClassPage'
import { StudentCertificatesPage } from './pages/StudentCertificatesPage'
import { StudentPlanningPage } from './pages/StudentPlanningPage'
import { CertificateVerifyPage } from './pages/CertificateVerifyPage'
const SchoolPublicSitePage = lazy(() => import('./pages/SchoolPublicSitePage').then((module) => ({ default: module.SchoolPublicSitePage })))
import { StudentsManagementPage } from './pages/StudentsManagementPage'
import { TeachersManagementPage } from './pages/TeachersManagementPage'
const CommerceDashboardPage = lazy(() => import('./pages/CommerceDashboardPage').then((module) => ({ default: module.CommerceDashboardPage })))
import { PromotionsPage } from './pages/PromotionsPage'
const PedagogicalMonitoringPage = lazy(() => import('./pages/PedagogicalMonitoringPage').then((module) => ({ default: module.PedagogicalMonitoringPage })))
const SchoolPerformancePage = lazy(() => import('./pages/SchoolPerformancePage').then((module) => ({ default: module.SchoolPerformancePage })))
import { ManageProfilePage, StudentProfilePage, TeacherProfilePage } from './pages/ProfilePage'
import { SupportPage } from './pages/SupportPage'
import { SchoolPublicLayout } from './public/SchoolPublicLayout'
import { HostSchoolRedirect } from './public/HostSchoolRedirect'
import { SchoolWorkspaceEntry } from './public/SchoolWorkspaceEntry'
import { SchoolHomePage } from './pages/SchoolHomePage'
import { SchoolFormationsPage } from './pages/SchoolFormationsPage'
import { SchoolFormationDetailPage } from './pages/SchoolFormationDetailPage'
import { SchoolContactPage } from './pages/SchoolContactPage'
import { SchoolLegalPage } from './pages/SchoolLegalPage'
const SchoolCheckoutPage = lazy(() => import('./pages/SchoolCheckoutPage').then((module) => ({ default: module.SchoolCheckoutPage })))
const StudentPaymentsPage = lazy(() => import('./pages/StudentPaymentsPage').then((module) => ({ default: module.StudentPaymentsPage })))
import type { WorkspaceSpace } from './lib/api'
import { SchoolNotificationsPage } from './pages/SchoolNotificationsPage'
import { SchoolFavoritesPage } from './pages/SchoolFavoritesPage'

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
          <Suspense fallback={<div className="app-loading">Chargement…</div>}>
          <Routes>
            <Route path="/" element={<HostSchoolRedirect fallback={<LandingPage />} />} />
            <Route path="/formations" element={<HostSchoolRedirect fallback={<Navigate to="/" replace />} />} />
            <Route path="/formations/:formationSlug" element={<HostSchoolRedirect fallback={<Navigate to="/" replace />} />} />
            <Route path="/contact" element={<HostSchoolRedirect fallback={<Navigate to="/" replace />} />} />
            <Route path="/panier" element={<HostSchoolRedirect fallback={<Navigate to="/" replace />} />} />
            <Route path="/checkout" element={<HostSchoolRedirect fallback={<Navigate to="/" replace />} />} />
            <Route path="/espace" element={<HostSchoolRedirect fallback={<Navigate to="/" replace />} />} />
            <Route path="/mentions-legales" element={<HostSchoolRedirect fallback={<Navigate to="/" replace />} />} />
            <Route path="/cgv" element={<HostSchoolRedirect fallback={<Navigate to="/" replace />} />} />
            <Route path="/confidentialite" element={<HostSchoolRedirect fallback={<Navigate to="/" replace />} />} />
            <Route path="/remboursement" element={<HostSchoolRedirect fallback={<Navigate to="/" replace />} />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/invite/:token" element={<InvitationAcceptPage />} />
            <Route path="/certificates/verify/:token" element={<CertificateVerifyPage />} />
            <Route path="/school/:schoolSlug" element={<SchoolPublicLayout />}>
              <Route index element={<SchoolHomePage />} />
              <Route path="formations" element={<SchoolFormationsPage />} />
              <Route path="favoris" element={<SchoolFavoritesPage />} />
              <Route path="formations/:formationSlug" element={<SchoolFormationDetailPage />} />
              <Route path="contact" element={<SchoolContactPage />} />
              <Route path="panier" element={<SchoolHomePage />} />
              <Route path="checkout" element={<SchoolCheckoutPage />} />
              <Route path="espace" element={<SchoolWorkspaceEntry />} />
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
              <Route path="notifications" element={<SchoolNotificationsPage space="manage" />} />
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
              <Route path="profile" element={<ManageProfilePage />} />
              <Route path="support" element={<SupportPage space="manage" />} />
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
              <Route path="notifications" element={<SchoolNotificationsPage space="teacher" />} />
              <Route path="sessions" element={<TeacherSessionsPage />} />
              <Route path="sessions/:sessionId" element={<TeacherSessionPlanningPage />} />
              <Route path="courses" element={<TeacherCoursesPage />} />
              <Route path="resources" element={<TeacherResourcesPage />} />
              <Route path="assignments" element={<TeacherAssignmentsPage />} />
              <Route path="quizzes" element={<TeacherQuizzesPage />} />
              <Route path="attendance" element={<TeacherAttendancePage />} />
              <Route path="students" element={<TeacherStudentsPage />} />
              <Route path="performance" element={<TeacherPerformancePage />} />
              <Route path="profile" element={<TeacherProfilePage />} />
              <Route path="support" element={<SupportPage space="teacher" />} />
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
              <Route path="notifications" element={<SchoolNotificationsPage space="student" />} />
              <Route path="formations" element={<StudentParcoursPage />} />
              <Route path="sessions/:sessionId" element={<StudentSessionPlanningPage />} />
              <Route path="planning" element={<StudentPlanningPage />} />
              <Route path="courses" element={<StudentCoursesPage />} />
              <Route path="classic/:enrollmentId" element={<StudentCoursesPage mode="classic" />} />
              <Route path="guided/:enrollmentId" element={<StudentGuidedWorkspacePage />} />
              <Route path="guided/:enrollmentId/program" element={<StudentCoursesPage mode="guided" />} />
              <Route path="resources" element={<StudentResourcesPage />} />
              <Route path="assignments" element={<StudentAssignmentsPage />} />
              <Route path="quizzes" element={<StudentQuizzesPage />} />
              <Route path="results" element={<StudentResultsPage />} />
              <Route path="progress" element={<StudentProgressPage />} />
              <Route path="class" element={<StudentClassPage />} />
              <Route path="certificates" element={<StudentCertificatesPage />} />
              <Route path="payments" element={<StudentPaymentsPage />} />
              <Route path="profile" element={<StudentProfilePage />} />
              <Route path="support" element={<SupportPage space="student" />} />
            </Route>

            <Route path="/app/onboarding" element={<Navigate to="/app/manage/onboarding" replace />} />
            <Route path="/app/formations" element={<Navigate to="/app/manage/formations" replace />} />
            <Route path="/app/formations/:formationId" element={<LegacyFormationRedirect />} />
            <Route path="/app/team" element={<Navigate to="/app/manage/team" replace />} />
            <Route path="/app/billing" element={<Navigate to="/app/manage/billing" replace />} />
            <Route path="/app/profile" element={<Navigate to="/app/manage/profile" replace />} />
            <Route path="/app/support" element={<Navigate to="/app/manage/support" replace />} />
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
          </Suspense>
        </TenantProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}

function LegacyFormationRedirect() {
  const formationId = window.location.pathname.split('/').pop()
  return <Navigate to={`/app/manage/formations/${formationId}`} replace />
}
