import type { CourseDay } from './api'

export function liveClassIsOpen(day: CourseDay): boolean {
  if (day.status === 'cancelled' || day.report_submitted_at) return false
  const start = new Date(day.scheduled_at).getTime()
  if (!Number.isFinite(start)) return false
  const now = Date.now()
  return now >= start - 15 * 60_000 && now <= start + (day.duration_minutes + 15) * 60_000
}
