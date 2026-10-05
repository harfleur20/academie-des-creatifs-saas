import {
  Activity,
  BookOpen,
  CalendarCheck2,
  CalendarDays,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  Bell,
  UserRound,
  Users,
} from 'lucide-react'
import { SchoolWorkspaceLayout } from './SchoolWorkspaceLayout'

export function TeacherLayout() {
  return (
    <SchoolWorkspaceLayout
      space="teacher"
      navItems={[
        {
          to: '/app/teacher',
          label: "Vue d'ensemble",
          icon: <LayoutDashboard size={18} />,
          end: true,
        },
        { to: '/app/teacher/notifications', label: 'Notifications', icon: <Bell size={18} /> },
        {
          to: '/app/teacher/performance',
          label: 'Performance',
          icon: <Activity size={18} />,
        },
        {
          to: '/app/teacher/sessions',
          label: 'Mes sessions',
          icon: <CalendarDays size={18} />,
        },
        {
          to: '/app/teacher/courses',
          label: 'Cours',
          icon: <BookOpen size={18} />,
        },
        {
          to: '/app/teacher/quizzes',
          label: 'Quiz & Examens',
          icon: <CheckCircle2 size={18} />,
        },
        {
          to: '/app/teacher/resources',
          label: 'Ressources',
          icon: <FileText size={18} />,
        },
        {
          to: '/app/teacher/assignments',
          label: 'Devoirs',
          icon: <ClipboardCheck size={18} />,
        },
        {
          to: '/app/teacher/attendance',
          label: 'Présences',
          icon: <CalendarCheck2 size={18} />,
        },
        {
          to: '/app/teacher/students',
          label: 'Étudiants',
          icon: <Users size={18} />,
        },
        {
          to: '/app/teacher/profile',
          label: 'Mon profil',
          icon: <UserRound size={18} />,
        },
      ]}
    />
  )
}
