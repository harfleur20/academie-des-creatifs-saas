import {
  BadgePercent,
  BookOpen,
  ClipboardList,
  CreditCard,
  GraduationCap,
  Activity,
  HeartPulse,
  LayoutDashboard,
  Bell,
  MessageCircle,
  Settings,
  ShoppingCart,
  Store,
  UserRoundCog,
  Users,
} from 'lucide-react'
import { SchoolWorkspaceLayout } from './SchoolWorkspaceLayout'

export function AppLayout() {
  return (
    <SchoolWorkspaceLayout
      space="manage"
      navItems={[
        { to: '/app/manage', label: 'Tableau de bord', icon: <LayoutDashboard size={18} />, end: true },
        { to: '/app/manage/notifications', label: 'Notifications', icon: <Bell size={18} /> },
        { to: '/app/manage/messages', label: 'Messages', icon: <MessageCircle size={18} /> },
        { to: '/app/manage/formations', label: 'Formations', icon: <BookOpen size={18} /> },
        { to: '/app/manage/students', label: 'Étudiants', icon: <GraduationCap size={18} /> },
        { to: '/app/manage/teachers', label: 'Enseignants', icon: <UserRoundCog size={18} /> },
        { to: '/app/manage/pedagogy', label: 'Suivi pédagogique', icon: <HeartPulse size={18} /> },
        { to: '/app/manage/course-reports', label: 'Comptes rendus', icon: <ClipboardList size={18} /> },
        { to: '/app/manage/performance', label: 'Performance', icon: <Activity size={18} /> },
        { to: '/app/manage/team', label: 'Équipe & accès', icon: <Users size={18} /> },
        { to: '/app/manage/commerce', label: 'Commerce', icon: <ShoppingCart size={18} /> },
        { to: '/app/manage/promotions', label: 'Promotions', icon: <BadgePercent size={18} /> },
        { to: '/app/manage/site-public', label: 'Site public', icon: <Store size={18} /> },
        { to: '/app/manage/billing', label: 'Abonnement', icon: <CreditCard size={18} /> },
        { to: '/app/manage/settings', label: 'Paramètres', icon: <Settings size={18} /> },
      ]}
    />
  )
}
