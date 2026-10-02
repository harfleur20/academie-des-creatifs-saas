import {
  BookOpen,
  CreditCard,
  Globe2,
  GraduationCap,
  LayoutDashboard,
  Megaphone,
  Settings,
  ShoppingCart,
  Tags,
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
        { to: '/app/manage/formations', label: 'Formations', icon: <BookOpen size={18} /> },
        { to: '/app/manage/catalogue', label: 'Catalogue public', icon: <ShoppingCart size={18} /> },
        { to: '/app/manage/site-public', label: 'Identité & site public', icon: <Globe2 size={18} /> },
        { to: '/app/manage/students', label: 'Étudiants', icon: <GraduationCap size={18} /> },
        { to: '/app/manage/teachers', label: 'Enseignants', icon: <UserRoundCog size={18} /> },
        { to: '/app/manage/team', label: 'Équipe & accès', icon: <Users size={18} /> },
        { to: '/app/manage/ventes', label: 'Ventes & paiements', icon: <CreditCard size={18} /> },
        { to: '/app/manage/promotions', label: 'Promotions', icon: <Tags size={18} /> },
        { to: '/app/manage/billing', label: 'Abonnement SaaS', icon: <Megaphone size={18} /> },
        { to: '/app/manage/settings', label: 'Paramètres', icon: <Settings size={18} /> },
      ]}
    />
  )
}
