import { ApiError, getAccessToken, getStoredOrganizationId } from '../lib/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export type SupportCategory = 'technical' | 'billing' | 'account' | 'pedagogy' | 'other'
export type SupportPriority = 'normal' | 'urgent'

export type SupportRequestPayload = {
  category: SupportCategory
  priority: SupportPriority
  subject: string
  message: string
  page_url?: string | null
}

export type SupportRequestResult = {
  reference: string
  message: string
}

export async function submitSupportRequest(payload: SupportRequestPayload) {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  const token = getAccessToken()
  const organizationId = getStoredOrganizationId()

  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (organizationId !== null) {
    headers.set('X-Organization-Id', String(organizationId))
  }

  const response = await fetch(`${API_BASE}/support/requests`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    let message = `La demande a échoué (HTTP ${response.status}).`
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') message = body.detail
    } catch {
      // Keep generic message.
    }
    throw new ApiError(response.status, message)
  }

  return response.json() as Promise<SupportRequestResult>
}
