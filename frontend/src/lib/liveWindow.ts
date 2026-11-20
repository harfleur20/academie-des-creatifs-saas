import { activeSchoolLocale } from '../app/schoolLocale'
import type { CourseDay } from './api'

// As on the mother site: the room opens 15 minutes before the class, and takes entries
// until 15 minutes after its planned end.
export const LIVE_ROOM_OPENS_MINUTES = 15
export const LIVE_ROOM_CLOSES_MINUTES = 15

export type LiveDay = Pick<CourseDay, 'scheduled_at' | 'duration_minutes' | 'status' | 'started_at' | 'report_submitted_at'>

/** A live class by the clock: planned, room open, running, over (report awaited), closed or cancelled. */
export type LiveState = 'cancelled' | 'closed' | 'planned' | 'open' | 'live' | 'ended'

export const LIVE_STATE_LABELS: Record<LiveState, string> = {
  cancelled: 'Annulée',
  closed: 'Clôturée',
  planned: 'Planifiée',
  open: 'Salle ouverte',
  live: 'En cours',
  ended: 'Terminée',
}

export function liveState(day: LiveDay, now = Date.now()): LiveState {
  if (day.status === 'cancelled') return 'cancelled'
  if (day.report_submitted_at) return 'closed'
  const start = Date.parse(day.scheduled_at)
  if (!Number.isFinite(start)) return 'planned'
  const entriesClose = start + (day.duration_minutes + LIVE_ROOM_CLOSES_MINUTES) * 60_000
  if (now > entriesClose) return 'ended'
  if (now >= start || day.started_at) return 'live'
  if (now >= start - LIVE_ROOM_OPENS_MINUTES * 60_000) return 'open'
  return 'planned'
}

/** Whether the room takes entries now. */
export function liveClassIsOpen(day: LiveDay, now = Date.now()): boolean {
  const state = liveState(day, now)
  return state === 'open' || state === 'live'
}

/** "Dans 1 j 2 h 30 min", as on the mother site ("In 1 d 2 h 30 min" for an English school). */
export function liveCountdown(ms: number): string {
  const english = activeSchoolLocale() === 'en-US'
  const totalMinutes = Math.max(0, Math.ceil(ms / 60_000))
  if (totalMinutes === 0) return english ? 'Now' : 'Maintenant'
  const days = Math.floor(totalMinutes / 1_440)
  const hours = Math.floor((totalMinutes % 1_440) / 60)
  const minutes = totalMinutes % 60
  const parts: string[] = []
  if (days > 0) parts.push(`${days} ${english ? 'd' : 'j'}`)
  if (hours > 0) parts.push(`${hours} h`)
  if (minutes > 0 || parts.length === 0) parts.push(`${minutes} min`)
  return `${english ? 'In' : 'Dans'} ${parts.join(' ')}`
}
