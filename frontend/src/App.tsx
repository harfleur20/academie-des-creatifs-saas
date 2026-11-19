import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import { lazy, Suspense, type ReactElement } from 'react'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { TenantProvider, useTenant } from './app/TenantContext'
import { billingPathFor, readPlanChoice } from './lib/planChoice'
import { AppLayout } from './app/AppLayout'
import { TeacherLayout } from './app/TeacherLayout'
import { StudentLayout } from './app/StudentLayout'
import { RequireStudentReady, RequireTeacherReady } from './app/WorkspaceReadinessGate'
import LandingPage from './pages/LandingPage'
import { PlatformLegalPage } from './pages/PlatformLegalPage'
import { LoginPage } from './pages/LoginPage'
import { InvitationAcceptPage } from './pages/InvitationAcceptPage'
import { SchoolDashboardPage } from './pages/SchoolDashboardPage'
import { TeamPage } from './pages/TeamPage'
import { SchoolIdentityPage } from './pages/SchoolIdentityPage'
import { BillingPage } from './pages/BillingPage'
import { SchoolRevenuePage } from './pages/SchoolRevenuePage'
import { AdminPayoutsPage } from './pages/AdminPayoutsPage'
import { SchoolReportsPage } from './pages/SchoolReportsPage'
import { SchoolConnectPage } from './pages/SchoolConnectPage'
import { AdminLayout } from './admin/AdminLayout'
import { AdminDashboardPage } from './pages/AdminDashboardPage'
import { AdminSchoolsPage } from './pages/AdminSchoolsPage'
const AdminSchoolDetailPage = lazy(() => import('./pages/AdminSchoolDetailPage').then((module) => ({ default: module.AdminSchoolDetailPage })))
const AdminPlansPage = lazy(() => import('./pages/AdminPlansPage').then((module) => ({ default: module.AdminPlansPage })))
const AdminIntegrationPreferencesPage = lazy(() => import('./pages/AdminIntegrationPreferencesPage').then((module) => ({ default: module.AdminIntegrationPreferencesPage })))
import { OnboardingPage } from './pages/OnboardingPage'
import { FormationsManagementPage } from './pages/FormationsManagementPage'
import { NewFormationPage } from './pages/NewFormationPage'
import { FormationWorkspacePage } from './pages/FormationWorkspacePage'
import { TeacherDashboardPage } from './pages/TeacherDashboardPage'
import { TeacherSessionsPage } from './pages/TeacherSessionsPage'
import { TeacherPlanningPage } from './pages/TeacherPlanningPage'
import { StudentDashboardPage } from './pages/StudentDashboardPage'
import { TeacherSessionPlanningPage } from './pages/TeacherSessionPlanningPage'
import { StudentSessionPlanningPage } from './pages/StudentSessionPlanningPage'
import { LiveClassPage } from './pages/LiveClassPage'
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
import { TeacherGradesPage } from './pages/TeacherGradesPage'
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
import { SchoolCourseReportsPage } from './pages/SchoolCourseReportsPage'
import { ManageProfilePage, StudentProfilePage, TeacherProfilePage } from './pages/ProfilePage'
import { SupportPage } from './pages/SupportPage'
import { SchoolPublicLayout, SchoolSiteAtPath } from './public/SchoolPublicLayout'
import { useSchoolHost } from './public/useSchoolHost'
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
import { SchoolMessagesPage } from './pages/SchoolMessagesPage'
import { TeacherSetupPage } from './pages/TeacherSetupPage'
import { StudentCharterPage } from './pages/StudentCharterPage'
import { CharterSettingsPage } from './pages/CharterSettingsPage'
import { OrganizationSelectionDialog } from './app/OrganizationSelectionDialog'

function RequireSchoolUser({ children }: { children: React.ReactNode }) {
  const { user, supportMode, loading } = useAuth()
  const tenant = useTenant()
  const location = useLocation()

  if (loading) {
    return <div className="app-loading">Chargement de votre espace…</div>
  }

  if (!user) {
    const target = `${location.pathname}${location.search}${location.hash}`
    return <Navigate to={target === '/app' ? '/login' : `/login?return=${encodeURIComponent(target)}`} replace />
  }

  if (user.platform_role === 'super_admin' && !supportMode) {
    return <Navigate to="/admin" replace />
  }

  if (!supportMode && tenant.organizationSelectionRequired) {
    return <OrganizationSelectionDialog
      organizations={tenant.organizations}
      onSelect={tenant.selectOrganization}
    />
  }

  return children
}

function WorkspaceEntry() {
  const { activeOrganization, accessProfile, loading, profileLoading, profileError } = useTenant()

  if (loading || (profileLoading && !accessProfile)) {
    return <div className="app-loading">Préparation de votre espace…</div>
  }

  if (!activeOrganization) {
    return <Navigate to="/app/manage" replace />
  }

  if (!accessProfile) {
    return <div className="app-loading">{profileError || 'Préparation de vos accès…'}</div>
  }

  if (accessProfile.spaces.length === 0) {
    return <div className="app-loading">Aucun espace disponible pour ce compte.</div>
  }

  // A plan clicked on the landing page: the billing page shows it (and forgets it).
  const choice = readPlanChoice()
  if (choice && accessProfile.spaces.includes('manage')) {
    return <Navigate to={billingPathFor(choice)} replace />
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
  const { activeOrganization, accessProfile, loading, profileLoading, profileError } = useTenant()

  if (loading || (profileLoading && !accessProfile)) {
    return <div className="app-loading">Chargement de votre espace…</div>
  }

  if (!activeOrganization) {
    return space === 'manage'
      ? children
      : <Navigate to="/app/manage" replace />
  }

  if (!accessProfile) {
    return <div className="app-loading">{profileError || 'Préparation de vos accès…'}</div>
  }

  if (supportMode && space !== 'manage') {
    return <Navigate to="/app/manage" replace />
  }

  if (!accessProfile.spaces.includes(space)) {
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

// The pages of a school's site, under "/school/<slug>" or at the root of its own address.
const schoolSitePages = (
  <>
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
  </>
)

export default function App() {
  const host = useSchoolHost()
  const hostSchool = host.status === 'resolved' ? host.slug : null
  // The app waits for the address before rendering; should that take too long, the root
  // pages wait too, rather than show the platform on a school's address.
  const platformPage = (page: ReactElement) => (
    host.status === 'pending' ? <div className="public-school-state">Chargement…</div> : page
  )
  return (
    <BrowserRouter>
      <AuthProvider>
        <TenantProvider>
          <Suspense fallback={<div className="app-loading">Chargement…</div>}>
          <Routes>
            {hostSchool ? (
              // The school's own address: its site at the root, "/formations"…
              <Route path="/" element={<SchoolPublicLayout />}>{schoolSitePages}</Route>
            ) : (
              <>
                <Route path="/" element={platformPage(<LandingPage />)} />
                <Route path="/formations" element={platformPage(<Navigate to="/" replace />)} />
                <Route path="/formations/:formationSlug" element={platformPage(<Navigate to="/" replace />)} />
                <Route path="/contact" element={platformPage(<Navigate to="/" replace />)} />
                <Route path="/panier" element={platformPage(<Navigate to="/" replace />)} />
                <Route path="/checkout" element={platformPage(<Navigate to="/" replace />)} />
                <Route path="/espace" element={platformPage(<Navigate to="/" replace />)} />
                <Route path="/mentions-legales" element={platformPage(<PlatformLegalPage page="mentions" />)} />
                <Route path="/cgv" element={platformPage(<PlatformLegalPage page="cgv" />)} />
                <Route path="/confidentialite" element={platformPage(<PlatformLegalPage page="confidentialite" />)} />
                <Route path="/remboursement" element={platformPage(<Navigate to="/" replace />)} />
              </>
            )}
            <Route path="/cgu" element={<PlatformLegalPage page="cgu" />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/invite/:token" element={<InvitationAcceptPage />} />
            <Route path="/certificates/verify/:token" element={<CertificateVerifyPage />} />
            <Route path="/school/:schoolSlug" element={<SchoolSiteAtPath />}>{schoolSitePages}</Route>

            <Route path="/app" element={<RequireSchoolUser><WorkspaceEntry /></RequireSchoolUser>} />

            <Route
              path="/app/manage"
              element={<RequireSchoolUser><RequireWorkspace space="manage"><AppLayout /></RequireWorkspace></RequireSchoolUser>}
            >
              <Route index element={<SchoolDashboardPage />} />
              <Route path="reports" element={<SchoolReportsPage />} />
              <Route path="connect" element={<SchoolConnectPage />} />
              <Route path="notifications" element={<SchoolNotificationsPage space="manage" />} />
              <Route path="messages" element={<SchoolMessagesPage />} />
              <Route path="onboarding" element={<OnboardingPage />} />
              <Route path="formations" element={<FormationsManagementPage />} />
              <Route path="formations/new" element={<NewFormationPage />} />
              <Route path="formations/:formationId" element={<FormationWorkspacePage />} />
              <Route path="students" element={<StudentsManagementPage />} />
              <Route path="teachers" element={<TeachersManagementPage />} />
              <Route path="commerce" element={<CommerceDashboardPage />} />
              <Route path="promotions" element={<PromotionsPage />} />
              <Route path="pedagogy" element={<PedagogicalMonitoringPage />} />
              <Route path="course-reports" element={<SchoolCourseReportsPage />} />
              <Route path="performance" element={<SchoolPerformancePage />} />
              <Route path="identity" element={<SchoolIdentityPage />} />
              <Route path="site-public" element={<SchoolPublicSitePage />} />
              <Route path="team" element={<TeamPage />} />
              <Route path="charters" element={<CharterSettingsPage />} />
              <Route path="billing" element={<BillingPage />} />
              <Route path="revenue" element={<SchoolRevenuePage />} />
              <Route path="profile" element={<ManageProfilePage />} />
              <Route path="support" element={<SupportPage space="manage" />} />
              <Route path="settings" element={<Navigate to="/app/manage/identity?tab=school" replace />} />
            </Route>

            {/* The live class is full screen, outside the space's layout, as on the mother site. */}
            <Route
              path="/app/teacher/live/:courseDayId"
              element={<RequireSchoolUser><RequireWorkspace space="teacher"><RequireTeacherReady><LiveClassPage space="teacher" /></RequireTeacherReady></RequireWorkspace></RequireSchoolUser>}
            />
            <Route
              path="/app/student/live/:courseDayId"
              element={<RequireSchoolUser><RequireWorkspace space="student"><RequireStudentReady><LiveClassPage space="student" /></RequireStudentReady></RequireWorkspace></RequireSchoolUser>}
            />
            <Route
              path="/app/teacher/setup"
              element={<RequireSchoolUser><RequireWorkspace space="teacher"><RequireTeacherReady requireProfile={false}><TeacherSetupPage /></RequireTeacherReady></RequireWorkspace></RequireSchoolUser>}
            />
            <Route
              path="/app/teacher"
              element={<RequireSchoolUser><RequireWorkspace space="teacher"><RequireTeacherReady><TeacherLayout /></RequireTeacherReady></RequireWorkspace></RequireSchoolUser>}
            >
              <Route index element={<TeacherDashboardPage />} />
              <Route path="notifications" element={<SchoolNotificationsPage space="teacher" />} />
              <Route path="messages" element={<SchoolMessagesPage />} />
              <Route path="sessions" element={<TeacherSessionsPage />} />
              <Route path="planning" element={<TeacherPlanningPage />} />
              <Route path="sessions/:sessionId" element={<TeacherSessionPlanningPage />} />
              <Route path="courses" element={<TeacherCoursesPage />} />
              <Route path="resources" element={<TeacherResourcesPage />} />
              <Route path="assignments" element={<TeacherAssignmentsPage />} />
              <Route path="quizzes" element={<TeacherQuizzesPage />} />
              <Route path="attendance" element={<TeacherAttendancePage />} />
              <Route path="grades" element={<TeacherGradesPage />} />
              <Route path="students" element={<TeacherStudentsPage />} />
              <Route path="performance" element={<TeacherPerformancePage />} />
              <Route path="profile" element={<TeacherProfilePage />} />
              <Route path="support" element={<SupportPage space="teacher" />} />
            </Route>

            <Route
              path="/app/student/charter"
              element={<RequireSchoolUser><RequireWorkspace space="student"><StudentCharterPage /></RequireWorkspace></RequireSchoolUser>}
            />
            <Route
              path="/app/student"
              element={<RequireSchoolUser><RequireWorkspace space="student"><RequireStudentReady><StudentLayout /></RequireStudentReady></RequireWorkspace></RequireSchoolUser>}
            >
              <Route index element={<StudentDashboardPage />} />
              <Route path="notifications" element={<SchoolNotificationsPage space="student" />} />
              <Route path="messages" element={<SchoolMessagesPage />} />
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
            <Route path="/app/settings" element={<Navigate to="/app/manage/identity?tab=school" replace />} />

            <Route path="/admin" element={<RequireSuperAdmin><AdminLayout /></RequireSuperAdmin>}>
              <Route index element={<AdminDashboardPage />} />
              <Route path="schools" element={<AdminSchoolsPage />} />
              <Route path="schools/:schoolId" element={<AdminSchoolDetailPage />} />
              <Route path="plans" element={<AdminPlansPage />} />
              <Route path="integrations" element={<AdminIntegrationPreferencesPage />} />
              <Route path="payouts" element={<AdminPayoutsPage />} />
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
