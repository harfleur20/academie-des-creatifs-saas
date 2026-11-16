import { activeSchoolLocale } from '../app/schoolLocale'
import { Bell, Check, ChevronRight, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useTenant } from '../app/TenantContext'
import { useSchoolNotifications } from '../app/useSchoolNotifications'
import type { WorkspaceSpace } from '../lib/api'

const categoryNames: Record<string, string> = {
  admin: 'Administration', assignment: 'Devoir', payment: 'Paiement',
  session: 'Session', system: 'Système',
}

export function SchoolNotificationsPage({ space }: { space: WorkspaceSpace }) {
  const navigate = useNavigate()
  const { user, supportMode } = useAuth()
  const { activeOrganization } = useTenant()
  const { items, loading, error, unreadCount, markRead, dismiss } = useSchoolNotifications(
    activeOrganization?.id, user?.id, space,
  )
  const [filter, setFilter] = useState<'all' | 'unread'>('all')
  const visible = filter === 'unread' ? items.filter((item) => !item.read_at) : items

  async function openNotification(id: number, path: string | null) {
    if (!supportMode) {
      try { await markRead([id]) } catch { return }
    }
    if (path?.startsWith('/app/')) navigate(path)
  }

  return <main className="app-page school-notifications-page">
    <header className="app-page-header"><div><span className="page-kicker">Votre école</span><h1>Notifications</h1><p>Retrouvez les événements de vos formations, paiements et devoirs.</p></div><Bell size={25} /></header>
    <div className="school-notifications-toolbar">
      <div role="group" aria-label="Filtrer les notifications">
        <button type="button" className={filter === 'all' ? 'is-active' : ''} onClick={() => setFilter('all')}>Toutes ({items.length})</button>
        <button type="button" className={filter === 'unread' ? 'is-active' : ''} onClick={() => setFilter('unread')}>Non lues ({unreadCount})</button>
      </div>
      {!supportMode && items.length > 0 && <div>
        {unreadCount > 0 && <button type="button" onClick={() => void markRead(items.filter((item) => !item.read_at).map((item) => item.id))}><Check size={15} /> Tout marquer lu</button>}
        <button type="button" onClick={() => void dismiss(items.map((item) => item.id))}><Trash2 size={15} /> Vider</button>
      </div>}
    </div>
    {error && <div className="form-error" role="alert">{error}</div>}
    <section className="school-notifications-feed" aria-label="Liste des notifications">
      {loading && <div className="school-notifications-empty">Chargement…</div>}
      {!loading && visible.length === 0 && <div className="school-notifications-empty">{filter === 'unread' ? 'Aucune notification non lue.' : 'Aucune notification pour le moment.'}</div>}
      {visible.map((item) => <article key={item.id} className={`school-notifications-row ${item.read_at ? 'is-read' : ''}`}>
        <span className={`school-notif-dot is-${item.tone}`} />
        <div><div className="school-notifications-row-head"><strong>{item.title}</strong><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString(activeSchoolLocale(), { dateStyle: 'medium', timeStyle: 'short' })}</time></div><p>{item.message}</p><small>{categoryNames[item.category] || item.category}</small></div>
        <div className="school-notifications-row-actions">
          {item.action_path && <button type="button" onClick={() => void openNotification(item.id, item.action_path)}>{item.action_label || 'Voir'} <ChevronRight size={14} /></button>}
          {!item.read_at && !supportMode && <button type="button" onClick={() => void markRead([item.id])}>Marquer lu</button>}
          {!supportMode && <button type="button" aria-label={`Masquer : ${item.title}`} onClick={() => void dismiss([item.id])}><Trash2 size={15} /></button>}
        </div>
      </article>)}
    </section>
  </main>
}
