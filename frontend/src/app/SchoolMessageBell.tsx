import { LayoutDashboard, MessageCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { listMessageThreads, subscribeSchoolMessages, type WorkspaceSpace } from '../lib/api'
import { useTenant } from './TenantContext'

export function SchoolMessageBell({
  space,
  variant = 'icon',
  onNavigate,
}: {
  space: WorkspaceSpace
  variant?: 'icon' | 'menu'
  onNavigate?: () => void
}) {
  const { activeOrganization } = useTenant()
  const { schoolSlug = '' } = useParams()
  const [unread, setUnread] = useState(0)

  useEffect(() => {
    if (!activeOrganization) { setUnread(0); return }
    let active = true
    const refresh = () => listMessageThreads()
      .then((threads) => {
        if (!active) return
        setUnread(threads.reduce((total, thread) => total + thread.unread_count, 0))
      })
      .catch(() => { if (active) setUnread(0) })

    void refresh()
    const unsubscribe = subscribeSchoolMessages((event) => {
      if (active) setUnread(event.unread_count)
    })
    const timer = window.setInterval(() => {
      if (!document.hidden) void refresh()
    }, 15000)
    const onVisible = () => { if (!document.hidden) void refresh() }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      active = false
      unsubscribe()
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [activeOrganization?.id])

  const target = '/app/' + space + '/messages'
  const workspaceTarget = schoolSlug ? '/school/' + schoolSlug + '/espace' : '/app/' + space
  const displayUnread = unread > 99 ? '99+' : unread

  if (variant === 'menu') {
    return (
      <>
        <Link
          className="public-school-account-indicator"
          to={target}
          onClick={onNavigate}
          aria-label={unread ? `${unread} message(s) non lu(s)` : 'Messages'}
        >
          <MessageCircle size={17} />
          <span className="public-school-account-indicator-label">Messages</span>
          {unread > 0 && <span className="public-school-account-indicator-badge">{displayUnread}</span>}
        </Link>
        <span className="public-school-account-menu-divider is-soft" aria-hidden="true" />
        <Link
          className="public-school-account-indicator"
          to={workspaceTarget}
          onClick={onNavigate}
          aria-label="Ouvrir mon espace"
        >
          <LayoutDashboard size={17} />
          <span className="public-school-account-indicator-label">Mon espace</span>
        </Link>
      </>
    )
  }

  return (
    <Link
      className="tenant-role-icon-button school-message-bell"
      to={target}
      aria-label={unread ? `${unread} message(s) non lu(s)` : 'Messagerie'}
      title="Messagerie"
    >
      <MessageCircle size={19}/>
      {unread > 0 && <span>{displayUnread}</span>}
    </Link>
  )
}
