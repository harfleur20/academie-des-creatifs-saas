/** The read-only demo the visitor is in, kept in this tab only (docs/DEMO.md). */
export type DemoPlace = 'site' | 'manage' | 'teacher' | 'student'
export type DemoState = { place: DemoPlace; school_name: string; organization_slug: string }

const KEY = 'academie_saas_demo'
export const DEMO_READ_ONLY_MESSAGE = 'Mode démo : rien n’est enregistré. Créez votre école pour essayer pour de vrai.'

export function readDemoState(): DemoState | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(KEY) || 'null') as DemoState | null
    return value && typeof value.organization_slug === 'string' ? value : null
  } catch {
    return null
  }
}

export function writeDemoState(state: DemoState) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(state))
  } catch {
    // Without storage the demo still works, without its bar.
  }
}

export function clearDemoState() {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // Nothing to clear.
  }
}

/*
 * The screens of the demo tour, per space (paths after /app/<space>/). The server reads
 * nothing else for a demo token (backend app/services/demo.py: DEMO_ALLOWED_READS); the
 * other screens stay visible in the menus, greyed, "available once you create your school".
 */
const DEMO_OPEN_SCREENS: Record<'manage' | 'teacher' | 'student', RegExp[]> = {
  manage: [/^$/, /^formations$/, /^formations\/\d+$/, /^pedagogy$/, /^performance$/, /^commerce$/],
  teacher: [/^$/, /^sessions$/, /^sessions\/\d+$/, /^students$/, /^grades$/],
  student: [/^$/, /^formations$/, /^sessions\/\d+$/, /^courses$/, /^classic\/\d+$/, /^guided\/\d+$/, /^guided\/\d+\/program$/, /^planning$/, /^results$/],
}

export const DEMO_LOCKED_MESSAGE = 'Disponible quand vous créez votre école'

/** In the demo, whether this screen of a space is closed (outside the spaces, nothing is). */
export function demoScreenLocked(pathname: string): boolean {
  if (!readDemoState()) return false
  const match = pathname.match(/^\/app\/(manage|teacher|student)(?:\/(.*?))?\/?$/)
  if (!match) return false
  const space = match[1] as keyof typeof DEMO_OPEN_SCREENS
  const rest = match[2] ?? ''
  return !DEMO_OPEN_SCREENS[space].some((pattern) => pattern.test(rest))
}
