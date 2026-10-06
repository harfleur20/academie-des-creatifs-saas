import {
  BadgePercent,
  BarChart3,
  Bell,
  BookOpen,
  BookOpenCheck,
  ClipboardList,
  CreditCard,
  GraduationCap,
  HeartPulse,
  LayoutDashboard,
  Settings,
  ShoppingCart,
  Store,
  UserRoundCog,
  Users,
} from 'lucide-react'
import { MessageNavIcon } from './MessageNavIcon'
import { SchoolWorkspaceLayout } from './SchoolWorkspaceLayout'

export function AppLayout() {
  return (
    <SchoolWorkspaceLayout
      space="manage"
      navItems={[
        { to: '/app/manage', label: 'Tableau de bord', icon: <LayoutDashboard size={18} />, end: true },
        { to: '/app/manage/notifications', label: 'Notifications', icon: <Bell size={18} /> },
        { to: '/app/manage/messages', label: 'Messages', icon: <MessageNavIcon /> },
        { to: '/app/manage/formations', label: 'Formations', icon: <BookOpen size={18} /> },
        { to: '/app/manage/students', label: 'Étudiants', icon: <GraduationCap size={18} /> },
        { to: '/app/manage/teachers', label: 'Enseignants', icon: <UserRoundCog size={18} /> },
        { to: '/app/manage/pedagogy', label: 'Suivi pédagogique', icon: <HeartPulse size={18} /> },
        { to: '/app/manage/course-reports', label: 'Comptes rendus', icon: <ClipboardList size={18} /> },
        { to: '/app/manage/performance', label: 'Statistiques', icon: <BarChart3 size={18} /> },
        { to: '/app/manage/team', label: 'Équipe & accès', icon: <Users size={18} /> },
        { to: '/app/manage/charters', label: 'Chartes & règles', icon: <BookOpenCheck size={18} /> },
        { to: '/app/manage/commerce', label: 'Commerce', icon: <ShoppingCart size={18} /> },
        { to: '/app/manage/promotions', label: 'Promotions', icon: <BadgePercent size={18} /> },
        { to: '/app/manage/site-public', label: 'Site public', icon: <Store size={18} /> },
        { to: '/app/manage/billing', label: 'Abonnement', icon: <CreditCard size={18} /> },
        { to: '/app/manage/settings', label: 'Paramètres', icon: <Settings size={18} /> },
      ]}
    />
  )
}
