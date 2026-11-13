import { clearSession, setAccessToken, setStoredOrganizationId, startDemoSession, type DemoSpace } from './api'
import { clearDemoState, writeDemoState, type DemoPlace } from './demoState'

export const DEMO_PLACES: Array<{ place: DemoPlace; label: string; text: string }> = [
  { place: 'site', label: 'Site de l’école', text: 'La vitrine publique : catalogue, fiches des formations, panier.' },
  { place: 'manage', label: 'Espace direction', text: 'Formations, sessions, suivi pédagogique, ventes et statistiques.' },
  { place: 'teacher', label: 'Espace professeur', text: 'Séances, cours en live, présences, devoirs et notes.' },
  { place: 'student', label: 'Espace étudiant', text: 'Cours, planning, progression et badges, paiements.' },
]

const PATHS: Record<DemoSpace, string> = { manage: '/app/manage', teacher: '/app/teacher', student: '/app/student' }

/**
 * Open a place of the demo school. Spaces get a read-only token kept in this tab; the
 * visitor's own session, if they have one, is left as it is (docs/DEMO.md).
 */
export async function enterDemo(place: DemoPlace, school: { school_name: string; organization_slug: string }) {
  if (place === 'site') {
    clearSession()
    writeDemoState({ school_name: school.school_name, organization_slug: school.organization_slug, place })
    window.location.assign(`/school/${encodeURIComponent(school.organization_slug)}`)
    return
  }
  const session = await startDemoSession(place)
  setAccessToken(session.access_token)
  setStoredOrganizationId(session.organization_id)
  writeDemoState({ school_name: school.school_name, organization_slug: school.organization_slug, place })
  window.location.assign(PATHS[place])
}

/** Leave the demo: forget its token and come back to the landing page (or elsewhere). */
export function exitDemo(to = '/') {
  clearSession()
  clearDemoState()
  window.location.assign(to)
}
