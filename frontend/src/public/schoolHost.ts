// Kept free of React: the bootstrap loads it before the app.
// A school's site answers at "/", "/formations"… on the school's own address (its
// subdomain, or a verified domain), and at "/school/<slug>/…" everywhere else.

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const CACHE_KEY = 'academie_saas_school_host_v1:'

// The pages of a school's site, as they read on the school's own address.
const SCHOOL_SITE_PAGE = /^\/(?:formations(?:\/[^/]+)?|favoris|contact|panier|checkout|espace|mentions-legales|cgv|confidentialite|remboursement)?\/?$/

export type SchoolHost =
  | { status: 'pending' }
  | { status: 'resolved'; slug: string | null }

let current: SchoolHost = readCache()
let request: Promise<void> | null = null
const listeners = new Set<() => void>()

function readCache(): SchoolHost {
  try {
    const cached = sessionStorage.getItem(CACHE_KEY + window.location.hostname)
    if (cached !== null) return { status: 'resolved', slug: cached || null }
  } catch {
    // Without storage, the address is resolved once per page load.
  }
  return { status: 'pending' }
}

function settle(slug: string | null, remember: boolean) {
  current = { status: 'resolved', slug }
  if (remember) {
    try {
      sessionStorage.setItem(CACHE_KEY + window.location.hostname, slug ?? '')
    } catch {
      // The answer still holds for this page load.
    }
  }
  listeners.forEach((listener) => listener())
}

/** Learn whether this address is a school's own: once per tab, before the app renders. */
export function resolveSchoolHost(): Promise<void> {
  if (current.status === 'resolved') return Promise.resolve()
  request ??= fetch(
    `${API_BASE}/organizations/resolve-host?hostname=${encodeURIComponent(window.location.hostname)}`,
    { cache: 'no-store' },
  )
    .then(async (response) => {
      if (response.ok) settle(((await response.json()) as { slug: string }).slug, true)
      else settle(null, response.status === 404)
    })
    // Unreachable API: the platform's pages, as before; the next load asks again.
    .catch(() => settle(null, false))
  return request
}

/** The school this address belongs to, or null on the platform's own address. */
export function schoolHostSlug(): string | null {
  return current.status === 'resolved' ? current.slug : null
}

export function readSchoolHost(): SchoolHost {
  return current
}

export function subscribeSchoolHost(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

function isHostSchool(slug: string) {
  const host = schoolHostSlug()
  return Boolean(slug && host && host.toLowerCase() === slug.toLowerCase())
}

/** A page of a school's site: "/formations" on its own address, "/school/<slug>/formations" elsewhere. */
export function schoolPath(slug: string, page = ''): string {
  const tail = page.replace(/^\/+/, '')
  if (isHostSchool(slug)) return '/' + tail
  return '/school/' + encodeURIComponent(slug) + (tail ? '/' + tail : '')
}

export function isSchoolSitePage(pathname: string) {
  return SCHOOL_SITE_PAGE.test(pathname)
}

/** The school whose public site this path shows, if any. */
export function schoolKeyForPath(pathname: string): string | null {
  const fromPath = pathname.match(/^\/school\/([^/]+)/)?.[1]
  if (fromPath) return decodeURIComponent(fromPath)
  return isSchoolSitePage(pathname) ? schoolHostSlug() : null
}

/** "/school/<host school>/formations" on the school's own address reads "/formations". */
export function hostSchoolPath(pathname: string): string | null {
  const match = pathname.match(/^\/school\/([^/]+)(\/.*)?$/)
  if (!match || !isHostSchool(decodeURIComponent(match[1]))) return null
  return match[2] && match[2] !== '/' ? match[2] : '/'
}
