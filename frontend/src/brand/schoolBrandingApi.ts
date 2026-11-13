import { getAccessToken, getStoredOrganizationId } from '../lib/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const BRAND_CACHE_PREFIX = 'academie_saas_school_branding:'

export type CurrentSchoolBranding = {
  organization_id: number
  school_name: string
  slug: string
  logo_url: string | null
  favicon_url: string | null
  primary_color: string
  secondary_color: string
  accent_color: string
  /** Business plans hide the platform's "Powered by" signature. */
  white_label?: boolean
}

export async function getCurrentSchoolBranding(organizationId?: number): Promise<CurrentSchoolBranding> {
  const headers = new Headers()
  const token = getAccessToken()
  const selectedOrganizationId = organizationId ?? getStoredOrganizationId()

  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (selectedOrganizationId !== null && selectedOrganizationId !== undefined) {
    headers.set('X-Organization-Id', String(selectedOrganizationId))
  }

  const response = await fetch(`${API_BASE}/branding/current`, {
    headers,
    credentials: 'include',
    cache: 'no-store',
  })
  if (!response.ok) {
    throw new Error(`Impossible de charger l’identité de l’école (HTTP ${response.status}).`)
  }
  const branding = await response.json() as CurrentSchoolBranding
  try {
    sessionStorage.setItem(
      BRAND_CACHE_PREFIX + branding.organization_id,
      JSON.stringify(branding),
    )
  } catch {
    // Storage can be unavailable in privacy-restricted browser contexts.
  }
  return branding
}
