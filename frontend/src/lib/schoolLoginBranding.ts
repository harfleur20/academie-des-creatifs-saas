import type { HostBranding, PublicSchool } from './api'

export type SchoolLoginBranding = HostBranding & {
  favicon_url: string | null
}

const CACHE_PREFIX = 'academie_saas_school_login_brand:'

export function toSchoolLoginBranding(school: PublicSchool): SchoolLoginBranding {
  return {
    organization_id: school.organization_id,
    name: school.site_name || school.name,
    slug: school.slug,
    subdomain: school.subdomain,
    hostname: school.slug,
    logo_url: school.logo_url,
    favicon_url: school.favicon_url,
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
  if (!favicon) {
    document.querySelector<HTMLLinkElement>("link[rel~='icon']")?.remove()
    return
  }

  let link = document.querySelector<HTMLLinkElement>("link[rel~='icon']")
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }
  link.href = favicon
}
