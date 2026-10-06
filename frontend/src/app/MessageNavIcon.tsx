import { MessageCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { listMessageThreads } from '../lib/api'
import { useTenant } from './TenantContext'
import './MessageNavIcon.css'

export function MessageNavIcon({ size = 18 }: { size?: number }) {
  const { activeOrganization } = useTenant()
  const [unread, setUnread] = useState(0)

  useEffect(() => {
    let active = true
    const refresh = () => listMessageThreads()
      .then((threads) => {
        if (!active) return
        setUnread(threads.reduce((total, thread) => total + thread.unread_count, 0))
      })
      .catch(() => { if (active) setUnread(0) })

    void refresh()
    const timer = window.setInterval(() => {
      if (!document.hidden) void refresh()
    }, 15000)
    const onVisible = () => { if (!document.hidden) void refresh() }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      active = false
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [activeOrganization?.id])

  return (
    <span className="workspace-message-nav-icon" aria-hidden="true">
      <MessageCircle size={size} />
      {unread > 0 && <span className="workspace-message-nav-badge">{unread > 99 ? '99+' : unread}</span>}
    </span>
  )
}
