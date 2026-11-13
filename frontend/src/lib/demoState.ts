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
