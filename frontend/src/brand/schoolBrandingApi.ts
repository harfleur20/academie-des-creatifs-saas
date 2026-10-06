import { getAccessToken, getStoredOrganizationId } from '../lib/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export type CurrentSchoolBranding = {
  organization_id: number
  school_name: string
  logo_url: string | null
  favicon_url: string | null
  primary_color: string
  secondary_color: string
  accent_color: string
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
    cache: 'no-store',
  })
  if (!response.ok) {
    throw new Error(`Impossible de charger l’identité de l’école (HTTP ${response.status}).`)
  }
  return response.json() as Promise<CurrentSchoolBranding>
}
