import { getAccessToken, getStoredOrganizationId, type PublicSchool } from './lib/api'
import {
  applySchoolLoginBranding,
  cacheSchoolLoginBranding,
  readSchoolLoginBranding,
  toSchoolLoginBranding,
} from './lib/schoolLoginBranding'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const BRAND_CACHE_PREFIX = 'academie_saas_school_branding:'

type CachedBranding = {
  organization_id: number
  school_name: string
  slug?: string
  logo_url: string | null
  favicon_url: string | null
  primary_color?: string
  secondary_color?: string
  accent_color?: string
}

function setFavicon(url?: string | null) {
  if (!url) return
  let link = document.querySelector<HTMLLinkElement>("link[rel~='icon']")
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }
  link.href = url
}

function applyWorkspaceBranding(branding: CachedBranding) {
  const pathname = window.location.pathname
  const section = pathname.startsWith('/app/teacher')
    ? 'Enseignant'
    : pathname.startsWith('/app/student')
      ? 'Étudiant'
      : 'Gestion'
  document.title = `${branding.school_name} - ${section}`
  setFavicon(branding.favicon_url || branding.logo_url)
}

function cacheBranding(branding: CachedBranding) {
  try {
    sessionStorage.setItem(
      BRAND_CACHE_PREFIX + branding.organization_id,
      JSON.stringify(branding),
    )
  } catch {
    // The live API response remains the source of truth when storage is blocked.
  }
}

function cachedBranding(organizationId: number): CachedBranding | null {
  try {
    const raw = sessionStorage.getItem(BRAND_CACHE_PREFIX + organizationId)
    return raw ? JSON.parse(raw) as CachedBranding : null
  } catch {
    return null
  }
}

async function prehydrateWorkspaceBranding() {
  const organizationId = getStoredOrganizationId()
  if (organizationId === null) return

  const cached = cachedBranding(organizationId)
  if (cached?.organization_id === organizationId) applyWorkspaceBranding(cached)

  const headers = new Headers()
  const token = getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  headers.set('X-Organization-Id', String(organizationId))

  try {
    const response = await Promise.race([
      fetch(`${API_BASE}/branding/current`, {
        headers,
        credentials: 'include',
        cache: 'no-store',
      }),
      new Promise<never>((_, reject) => {
        window.setTimeout(() => reject(new Error('branding timeout')), 1800)
      }),
    ])
    if (!response.ok) return
    const branding = await response.json() as CachedBranding
    if (branding.organization_id !== organizationId) return
    cacheBranding(branding)
    applyWorkspaceBranding(branding)
  } catch {
    // Cached branding, when available, has already prevented a platform flash.
  }
}

async function prehydratePublicSchool() {
  const match = window.location.pathname.match(/^\/school\/([^/]+)/)
  if (!match) return

  const encodedKey = match[1]
  const schoolKey = decodeURIComponent(encodedKey)
  const cached = readSchoolLoginBranding(schoolKey)
  if (cached) {
    // Apply the last known school identity before the network request so a
    // refresh never briefly exposes the platform's title or favicon.
    applySchoolLoginBranding(cached)
  } else {
    document.title = 'Chargement du site de l’école…'
    document.querySelector<HTMLLinkElement>("link[rel~='icon']")?.remove()
  }

  try {
    const response = await fetch(
      `${API_BASE}/public/schools/${encodeURIComponent(schoolKey)}/identity`,
      { cache: 'no-store' },
    )
    if (!response.ok) return
    const school = await response.json() as PublicSchool
    const branding = toSchoolLoginBranding(school)
    cacheSchoolLoginBranding(schoolKey, branding)
    if (school.slug !== schoolKey) cacheSchoolLoginBranding(school.slug, branding)
    applySchoolLoginBranding(branding)

    if (school.slug && school.slug !== schoolKey) {
      const prefix = `/school/${encodedKey}`
      const suffix = window.location.pathname.slice(prefix.length)
      window.history.replaceState(
        window.history.state,
        '',
        `/school/${encodeURIComponent(school.slug)}${suffix}${window.location.search}${window.location.hash}`,
      )
    }
  } catch {
    // React will show the regular public error state if the school is unavailable.
  }
}

async function prehydrateSchoolLogin() {
  const schoolKey = new URLSearchParams(window.location.search).get('school')?.trim()
  if (!schoolKey) return

  const cached = readSchoolLoginBranding(schoolKey)
  if (cached) {
    applySchoolLoginBranding(cached)
    return
  }

  document.title = 'Inscription à l’école'
  document.querySelector<HTMLLinkElement>("link[rel~='icon']")?.remove()

  try {
    const response = await Promise.race([
      fetch(`${API_BASE}/public/schools/${encodeURIComponent(schoolKey)}/identity`, {
        cache: 'no-store',
      }),
      new Promise<never>((_, reject) => {
        window.setTimeout(() => reject(new Error('school branding timeout')), 1800)
      }),
    ])
    if (!response.ok) return
    const school = await response.json() as PublicSchool
    const branding = toSchoolLoginBranding(school)
    cacheSchoolLoginBranding(schoolKey, branding)
    if (school.slug !== schoolKey) cacheSchoolLoginBranding(school.slug, branding)
    applySchoolLoginBranding(branding)
  } catch {
    // React shows a neutral loading/error state instead of platform branding.
  }
}

async function bootstrap() {
  if (window.location.pathname.startsWith('/app')) {
    await prehydrateWorkspaceBranding()
  } else if (window.location.pathname.startsWith('/school/')) {
    await prehydratePublicSchool()
  } else if (window.location.pathname === '/login') {
    await prehydrateSchoolLogin()
  }
  await import('./main')
}

void bootstrap()
