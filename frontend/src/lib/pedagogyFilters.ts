import { useCallback, useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

/**
 * The filters shared by the school's pedagogy pages (suivi, comptes rendus, statistiques).
 * They live in the address, and are remembered for the tab so they follow from one page to the next.
 */
export type PedagogyFilters = {
  formation: number | null
  session: number | null
  teacher: number | null
  from: string
  to: string
}

/** A session as the filters know it: which formation it belongs to, and who teaches it. */
export type FilterSession = {
  id: number
  label: string
  formationId: number | null
  formationTitle: string
  teacherIds: number[]
}

export type FilterTeacher = { id: number; name: string }

/** What a row exposes to be filtered. */
export type FilterableRow = {
  formationId?: number | null
  sessionId?: number | null
  teacherIds?: number[]
  date?: string | null
}

const KEYS = ['formation', 'session', 'teacher', 'from', 'to'] as const
const STORAGE_PREFIX = 'academie_pedagogy_filters:'

function toId(value: string | null): number | null {
  const id = Number(value)
  return value && Number.isInteger(id) && id > 0 ? id : null
}

function toDate(value: string | null): string {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : ''
}

export function usePedagogyFilters(organizationId: number | null | undefined) {
  const [params, setParams] = useSearchParams()
  const storageKey = organizationId ? `${STORAGE_PREFIX}${organizationId}` : null

  // Arriving from another pedagogy page without filters in the address: take back the remembered ones.
  useEffect(() => {
    if (!storageKey || KEYS.some((key) => params.get(key))) return
    try {
      const saved = sessionStorage.getItem(storageKey)
      if (!saved) return
      const restored = new URLSearchParams(saved)
      if (![...restored.keys()].length) return
      const next = new URLSearchParams(params)
      restored.forEach((value, key) => { if ((KEYS as readonly string[]).includes(key)) next.set(key, value) })
      setParams(next, { replace: true })
    } catch {
      // Storage can be unavailable in privacy-restricted browser contexts.
    }
    // Only when the page opens for this school.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey])

  const filters = useMemo<PedagogyFilters>(() => ({
    formation: toId(params.get('formation')),
    session: toId(params.get('session')),
    teacher: toId(params.get('teacher')),
    from: toDate(params.get('from')),
    to: toDate(params.get('to')),
  }), [params])

  const update = useCallback((changes: Partial<PedagogyFilters>) => {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === '' || value === undefined) next.delete(key)
      else next.set(key, String(value))
    }
    // A session belongs to one formation: changing the formation clears the session.
    if ('formation' in changes && !('session' in changes)) next.delete('session')
    setParams(next, { replace: true })
    if (storageKey) {
      try {
        const kept = new URLSearchParams()
        KEYS.forEach((key) => { const value = next.get(key); if (value) kept.set(key, value) })
        sessionStorage.setItem(storageKey, kept.toString())
      } catch {
        // Nothing to remember.
      }
    }
  }, [params, setParams, storageKey])

  const clear = useCallback(() => update({ formation: null, session: null, teacher: null, from: '', to: '' }), [update])

  const active = Boolean(filters.formation || filters.session || filters.teacher || filters.from || filters.to)

  const matches = useCallback((row: FilterableRow) => {
    if (filters.formation && row.formationId !== filters.formation) return false
    if (filters.session && row.sessionId !== filters.session) return false
    if (filters.teacher && !(row.teacherIds ?? []).includes(filters.teacher)) return false
    if (row.date) {
      const day = row.date.slice(0, 10)
      if (filters.from && day < filters.from) return false
      if (filters.to && day > filters.to) return false
    }
    return true
  }, [filters])

  return { filters, update, clear, active, matches }
}

/** Formations of the sessions, sorted by title. */
export function filterFormations(sessions: FilterSession[]): Array<{ id: number; title: string }> {
  const seen = new Map<number, string>()
  sessions.forEach((session) => { if (session.formationId) seen.set(session.formationId, session.formationTitle) })
  return [...seen.entries()].map(([id, title]) => ({ id, title })).sort((a, b) => a.title.localeCompare(b.title, 'fr'))
}
