import { ChevronRight, Star, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router-dom'

export type RoleQuickAccessLink = {
  to: string
  label: string
  icon: LucideIcon
  tone: 'indigo' | 'sky' | 'emerald' | 'amber' | 'pink' | 'violet'
}

export function RoleQuickAccess({ links }: { links: readonly RoleQuickAccessLink[] }) {
  return (
    <section className="role-quick-access" aria-label="Accès rapide">
      <header className="role-quick-access__header">
        <Star size={18} aria-hidden="true" />
        <h2>Accès rapide</h2>
      </header>
      <div className="role-quick-access__grid">
        {links.map((shortcut) => (
          <Link className="role-quick-access__card" to={shortcut.to} key={shortcut.to}>
            <span className={`role-quick-access__icon role-quick-access__icon--${shortcut.tone}`}>
              <shortcut.icon size={18} aria-hidden="true" />
            </span>
            <span>{shortcut.label}</span>
            <ChevronRight className="role-quick-access__arrow" size={16} aria-hidden="true" />
          </Link>
        ))}
      </div>
    </section>
  )
}
