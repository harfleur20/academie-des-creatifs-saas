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
  UserRound,
  Users,
} from 'lucide-react'
import { SchoolWorkspaceLayout } from './SchoolWorkspaceLayout'

export function StudentLayout() {
  return (
    <SchoolWorkspaceLayout
      space="student"
      navItems={[
        {
          to: '/app/student',
          label: "Vue d'ensemble",
          icon: <LayoutDashboard size={18} />,
          end: true,
        },
        {
          to: '/app/student/formations',
          label: 'Mes parcours',
          icon: <GraduationCap size={18} />,
        },
        {
          to: '/app/student/planning',
          label: 'Planning',
          icon: <CalendarDays size={18} />,
        },
        {
          to: '/app/student/courses',
          label: 'Mes cours',
          icon: <BookOpen size={18} />,
        },
        {
          to: '/app/student/class',
          label: 'Ma classe',
          icon: <Users size={18} />,
        },
        {
          to: '/app/student/quizzes',
          label: 'Quiz & Examens',
          icon: <CheckCircle2 size={18} />,
        },
        {
          to: '/app/student/resources',
          label: 'Ressources',
          icon: <FileText size={18} />,
        },
        {
          to: '/app/student/assignments',
          label: 'Devoirs',
          icon: <ClipboardCheck size={18} />,
        },
        {
          to: '/app/student/results',
          label: 'Mes résultats',
          icon: <BarChart3 size={18} />,
        },
        {
          to: '/app/student/progress',
          label: 'Progression',
          icon: <Award size={18} />,
        },
        {
          to: '/app/student/certificates',
          label: 'Certificats',
          icon: <Award size={18} />,
        },
        {
          to: '/app/student/profile',
          label: 'Mon profil',
          icon: <UserRound size={18} />,
        },
      ]}
    />
  )
}
