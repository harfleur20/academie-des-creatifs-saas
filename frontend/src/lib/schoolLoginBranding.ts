import type { HostBranding, PublicSchool } from './api'
import { DEFAULT_BRAND_COLORS, DEFAULT_PLATFORM_LOGO_URL } from '../brand/branding'
import { recolorTealPixels } from '../brand/recolorTealPixels'

export type SchoolLoginBranding = HostBranding & {
  locale: string
  favicon_url: string | null
  auth_background_image_url: string | null
  auth_show_school_name: boolean
}

const CACHE_PREFIX = 'academie_saas_school_login_brand:'
let faviconRequestId = 0

function setSchoolFavicon(url: string) {
  let link = document.querySelector<HTMLLinkElement>("link[rel~='icon']")
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }
  link.href = url
}

export function toSchoolLoginBranding(school: PublicSchool): SchoolLoginBranding {
  return {
    organization_id: school.organization_id,
    name: school.site_name || school.name,
    slug: school.slug,
    subdomain: school.subdomain,
    hostname: school.slug,
    locale: school.locale,
    logo_url: school.logo_url,
    favicon_url: school.favicon_url,
    auth_background_image_url: school.auth_background_image_url,
    auth_show_school_name: school.auth_show_school_name,
    primary_color: school.primary_color,
    secondary_color: school.secondary_color,
    accent_color: school.accent_color,
  }
}

export function cacheSchoolLoginBranding(key: string, branding: SchoolLoginBranding) {
  try {
    sessionStorage.setItem(CACHE_PREFIX + key, JSON.stringify(branding))
  } catch {
    // Branding still loads from the public identity endpoint when storage is unavailable.
  }
}

export function readSchoolLoginBranding(key: string): SchoolLoginBranding | null {
  try {
    const raw = sessionStorage.getItem(CACHE_PREFIX + key)
    if (!raw) return null
    const branding = JSON.parse(raw) as SchoolLoginBranding
    return branding.slug && branding.name ? branding : null
  } catch {
    return null
  }
}

export function applySchoolLoginBranding(branding: HostBranding & { favicon_url?: string | null }) {
  document.title = branding.name
  const favicon = branding.favicon_url || branding.logo_url
  const requestId = ++faviconRequestId
  if (!favicon) {
    document.querySelector<HTMLLinkElement>("link[rel~='icon']")?.remove()
    return
  }

  if (favicon !== DEFAULT_PLATFORM_LOGO_URL) {
    setSchoolFavicon(favicon)
    return
  }

  const schoolAccent = branding.secondary_color || DEFAULT_BRAND_COLORS.secondary
  if (schoolAccent.toUpperCase() === DEFAULT_BRAND_COLORS.secondary) {
    setSchoolFavicon(DEFAULT_PLATFORM_LOGO_URL)
    return
  }

  recolorTealPixels(DEFAULT_PLATFORM_LOGO_URL, schoolAccent, (source) => {
    if (faviconRequestId === requestId) setSchoolFavicon(source)
  })
}
