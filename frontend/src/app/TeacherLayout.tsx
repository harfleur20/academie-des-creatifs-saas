import {
  CalendarDays,
  LayoutDashboard,
} from 'lucide-react'
import { SchoolWorkspaceLayout } from './SchoolWorkspaceLayout'

export function TeacherLayout() {
  return (
    <SchoolWorkspaceLayout
      space="teacher"
      navItems={[
        {
          to: '/app/teacher',
          label: 'Tableau de bord',
          icon: <LayoutDashboard size={18} />,
          end: true,
        },
        {
          to: '/app/teacher/sessions',
          label: 'Mes sessions',
          icon: <CalendarDays size={18} />,
        },
      ]}
    />
  )
}
