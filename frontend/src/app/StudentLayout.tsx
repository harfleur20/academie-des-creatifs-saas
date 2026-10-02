import {
  ClipboardCheck,
  GraduationCap,
  LayoutDashboard,
} from 'lucide-react'
import { SchoolWorkspaceLayout } from './SchoolWorkspaceLayout'

export function StudentLayout() {
  return (
    <SchoolWorkspaceLayout
      space="student"
      navItems={[
        {
          to: '/app/student',
          label: 'Tableau de bord',
          icon: <LayoutDashboard size={18} />,
          end: true,
        },
        {
          to: '/app/student/formations',
          label: 'Mes formations',
          icon: <GraduationCap size={18} />,
        },
        {
          to: '/app/student/assignments',
          label: 'Devoirs',
          icon: <ClipboardCheck size={18} />,
        },
      ]}
    />
  )
}
