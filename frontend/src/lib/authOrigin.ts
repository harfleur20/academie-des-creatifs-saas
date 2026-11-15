const AUTH_ORIGIN_KEY = 'academie_saas_auth_origin_v1'
const SCHOOL_SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/i

type AuthOrigin =
  | { kind: 'platform' }
  | { kind: 'school'; slug: string }

function validSchoolSlug(value: unknown): value is string {
  return typeof value === 'string' && SCHOOL_SLUG_PATTERN.test(value.trim())
}

function saveAuthOrigin(origin: AuthOrigin) {
  try {
    sessionStorage.setItem(AUTH_ORIGIN_KEY, JSON.stringify(origin))
  } catch {
    // The logout redirect still has a safe fallback if session storage is unavailable.
  }
}

export function rememberPlatformAuthOrigin() {
  saveAuthOrigin({ kind: 'platform' })
}

export function rememberSchoolAuthOrigin(slug: string) {
  const normalizedSlug = slug.trim()
  if (!validSchoolSlug(normalizedSlug)) return
  saveAuthOrigin({ kind: 'school', slug: normalizedSlug })
}

function schoolHomePath(slug: string) {
  return `/school/${encodeURIComponent(slug)}`
}

/** Resolve and consume the login origin when the user signs out. */
export function takePostLogoutDestination(fallbackSchoolSlug?: string | null) {
  try {
    const raw = sessionStorage.getItem(AUTH_ORIGIN_KEY)
    sessionStorage.removeItem(AUTH_ORIGIN_KEY)
    if (raw) {
      const origin = JSON.parse(raw) as AuthOrigin
      if (origin.kind === 'platform') return '/login?mode=register'
      if (origin.kind === 'school' && validSchoolSlug(origin.slug)) return schoolHomePath(origin.slug)
    }
  } catch {
    // Fall through to the active school or platform destination.
  }

  return validSchoolSlug(fallbackSchoolSlug) ? schoolHomePath(fallbackSchoolSlug) : '/login?mode=register'
}

export function clearAuthOrigin() {
  try {
    sessionStorage.removeItem(AUTH_ORIGIN_KEY)
  } catch {
    // Storage may be unavailable in restricted browser contexts.
  }
}
