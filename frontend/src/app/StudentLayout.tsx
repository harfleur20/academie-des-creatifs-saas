import {
  Award,
  BarChart3,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  GraduationCap,
  LayoutDashboard,
  CreditCard,
  UserRound,
  Users,
} from 'lucide-react'
import {
  SchoolWorkspaceLayout,
  type WorkspaceNavGroup,
  type WorkspaceNavItem,
} from './SchoolWorkspaceLayout'

const navItems: WorkspaceNavItem[] = [
  {
    to: '/app/student',
    label: "Vue d'ensemble",
    icon: <LayoutDashboard size={18} />,
    end: true,
  },
]

const trailingNavItems: WorkspaceNavItem[] = [
  { to: '/app/student/certificates', label: 'Certificats', icon: <Award size={18} /> },
  { to: '/app/student/payments', label: 'Mes paiements', icon: <CreditCard size={18} /> },
  { to: '/app/student/profile', label: 'Mon profil', icon: <UserRound size={18} /> },
]

const navGroups: WorkspaceNavGroup[] = [
  {
    key: 'formation',
    label: 'Ma formation',
    icon: <BookOpen size={18} />,
    items: [
      { to: '/app/student/formations', label: 'Mes parcours', icon: <GraduationCap size={18} /> },
      { to: '/app/student/courses', label: 'Mes cours', icon: <BookOpen size={18} /> },
      { to: '/app/student/planning', label: 'Planning', icon: <CalendarDays size={18} /> },
      { to: '/app/student/class', label: 'Ma classe', icon: <Users size={18} /> },
      { to: '/app/student/resources', label: 'Ressources', icon: <FileText size={18} /> },
    ],
  },
  {
    key: 'evaluations',
    label: 'Évaluations',
    icon: <ClipboardCheck size={18} />,
    items: [
      { to: '/app/student/assignments', label: 'Devoirs', icon: <ClipboardCheck size={18} /> },
      { to: '/app/student/quizzes', label: 'Quiz & Examens', icon: <CheckCircle2 size={18} /> },
      { to: '/app/student/results', label: 'Mes résultats', icon: <BarChart3 size={18} /> },
      { to: '/app/student/progress', label: 'Progression', icon: <Award size={18} /> },
    ],
  },
]

export function StudentLayout() {
  return (
    <SchoolWorkspaceLayout
      space="student"
      navItems={navItems}
      navGroups={navGroups}
      trailingNavItems={trailingNavItems}
    />
  )
}
