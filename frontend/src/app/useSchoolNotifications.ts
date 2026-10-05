import { useCallback, useEffect, useRef, useState } from 'react'
import {
  dismissSchoolNotifications,
  listSchoolNotifications,
  markSchoolNotificationsRead,
  type SchoolNotification,
  type WorkspaceSpace,
} from '../lib/api'

const CHANGE_EVENT = 'school-notifications-changed'

export function useSchoolNotifications(organizationId: number | undefined, userId: number | undefined, space: WorkspaceSpace) {
  const [items, setItems] = useState<SchoolNotification[]>([])
  const [dataScope, setDataScope] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const scope = `${organizationId ?? ''}:${userId ?? ''}:${space}`
  const activeScope = useRef(scope)
  activeScope.current = scope

  const refresh = useCallback(async () => {
    const requestedScope = `${organizationId ?? ''}:${userId ?? ''}:${space}`
    if (!organizationId || !userId) {
      setItems([])
      setDataScope('')
      setError('')
      setLoading(false)
      return
    }
    try {
      const rows = await listSchoolNotifications(space)
      if (activeScope.current !== requestedScope) return
      setItems(rows)
      setDataScope(requestedScope)
      setError('')
    } catch (cause) {
      if (activeScope.current !== requestedScope) return
      setError(cause instanceof Error ? cause.message : 'Notifications indisponibles.')
    } finally {
      if (activeScope.current === requestedScope) setLoading(false)
    }
  }, [organizationId, userId, space])

  useEffect(() => {
    setItems([])
    setDataScope('')
    setLoading(true)
    void refresh()
    const timer = window.setInterval(() => { if (!document.hidden) void refresh() }, 30000)
    const onVisible = () => { if (!document.hidden) void refresh() }
    const onChanged = () => { void refresh() }
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener(CHANGE_EVENT, onChanged)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener(CHANGE_EVENT, onChanged)
    }
  }, [refresh])

  const update = useCallback(async (ids: number[], dismiss: boolean) => {
    if (ids.length === 0) return
    try {
      if (dismiss) await dismissSchoolNotifications(ids)
      else await markSchoolNotificationsRead(ids)
      window.dispatchEvent(new Event(CHANGE_EVENT))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Action impossible.')
      throw cause
    }
  }, [])

  const scopedItems = dataScope === scope ? items : []
  return {
    items: scopedItems, loading, error, refresh,
    unreadCount: scopedItems.filter((item) => !item.read_at).length,
    markRead: (ids: number[]) => update(ids, false),
    dismiss: (ids: number[]) => update(ids, true),
  }
}
