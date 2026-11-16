import { activeSchoolLocale } from './schoolLocale'
import { Bell, Check, ChevronRight, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useTenant } from './TenantContext'
import { useSchoolNotifications } from './useSchoolNotifications'
import type { WorkspaceSpace } from '../lib/api'

export function SchoolNotificationBell({
  space,
  variant = 'icon',
  onNavigate,
}: {
  space: WorkspaceSpace
  variant?: 'icon' | 'menu'
  onNavigate?: () => void
}) {
  const navigate = useNavigate()
  const { user, supportMode } = useAuth()
  const { activeOrganization } = useTenant()
  const [open, setOpen] = useState(false)
  const container = useRef<HTMLDivElement>(null)
  const { items, loading, error, unreadCount, refresh, markRead, dismiss } = useSchoolNotifications(
    activeOrganization?.id, user?.id, space,
  )
  const allPath = `/app/${space}/notifications`

  useEffect(() => setOpen(false), [activeOrganization?.id, space])
  useEffect(() => {
    if (!open) return
    const onOutside = (event: MouseEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false)
    }
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onOutside)
    document.addEventListener('keydown', onEscape)
    return () => {
      document.removeEventListener('mousedown', onOutside)
      document.removeEventListener('keydown', onEscape)
    }
  }, [open])

  async function openTarget(id: number, path: string | null) {
    if (!supportMode) {
      try { await markRead([id]) } catch { return }
    }
    setOpen(false)
    if (path?.startsWith('/app/')) navigate(path)
  }

  if (variant === 'menu') {
    return (
      <Link
        className="public-school-account-indicator"
        to={allPath}
        onClick={onNavigate}
        aria-label={`Notifications${unreadCount ? ` : ${unreadCount} non lues` : ''}`}
      >
        <Bell size={17} />
        <span className="public-school-account-indicator-label">Notifications</span>
        {unreadCount > 0 && <span className="public-school-account-indicator-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>}
      </Link>
    )
  }

  return <div className="school-notif-wrap" ref={container}>
    <button type="button" className="school-notif-bell" aria-label={`Notifications${unreadCount ? ` : ${unreadCount} non lues` : ''}`} aria-expanded={open} aria-haspopup="dialog" onClick={() => { setOpen((value) => !value); void refresh() }}>
      <Bell size={19} />
      {unreadCount > 0 && <span className="school-notif-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>}
    </button>
    {open && <section className="school-notif-dropdown" role="dialog" aria-label="Notifications">
      <header><strong>Notifications</strong><span>{unreadCount} non lue{unreadCount > 1 ? 's' : ''}</span></header>
      <div className="school-notif-actions">
        {unreadCount > 0 && !supportMode && <button type="button" onClick={() => void markRead(items.filter((item) => !item.read_at).map((item) => item.id))}><Check size={14} /> Tout marquer lu</button>}
        {items.length > 0 && !supportMode && <button type="button" onClick={() => void dismiss(items.map((item) => item.id))} title="Vider les notifications"><Trash2 size={14} /> Vider</button>}
      </div>
      <div className="school-notif-list">
        {loading && <p className="school-notif-empty">Chargement…</p>}
        {!loading && error && <p className="school-notif-empty">{error}</p>}
        {!loading && !error && items.length === 0 && <p className="school-notif-empty">Aucune notification.</p>}
        {items.slice(0, 6).map((item) => <button key={item.id} type="button" className={`school-notif-item ${item.read_at ? 'is-read' : ''}`} onClick={() => void openTarget(item.id, item.action_path)}>
          <span className={`school-notif-dot is-${item.tone}`} />
          <span><strong>{item.title}</strong><small>{item.message}</small><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleDateString(activeSchoolLocale(), { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</time></span>
          {item.action_path && <ChevronRight size={15} />}
        </button>)}
      </div>
      <button type="button" className="school-notif-all" onClick={() => { setOpen(false); navigate(allPath) }}>Voir toutes les notifications <ChevronRight size={15} /></button>
    </section>}
  </div>
}
