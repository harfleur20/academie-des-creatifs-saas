import { MessageCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listMessageThreads, type WorkspaceSpace } from '../lib/api'
import { useTenant } from './TenantContext'

export function SchoolMessageBell({ space }: { space: WorkspaceSpace }) {
  const { activeOrganization } = useTenant()
  const [unread, setUnread] = useState(0)
  useEffect(() => {
    let active = true
    const refresh = () => listMessageThreads()
      .then((threads) => { if (active) setUnread(threads.reduce((total, thread) => total + thread.unread_count, 0)) })
      .catch(() => { if (active) setUnread(0) })
    void refresh()
    const timer = window.setInterval(() => void refresh(), 15000)
    return () => { active = false; window.clearInterval(timer) }
  }, [activeOrganization?.id])
  return <Link className="tenant-role-icon-button school-message-bell" to={'/app/' + space + '/messages'} aria-label={unread ? `${unread} message(s) non lu(s)` : 'Messagerie'} title="Messagerie"><MessageCircle size={19}/>{unread > 0 && <span>{unread > 99 ? '99+' : unread}</span>}</Link>
}
