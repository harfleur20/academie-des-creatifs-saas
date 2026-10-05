import { ApiError, setAccessToken, type AuthResponse } from '../lib/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export async function authenticateWithGoogle(credential: string) {
  const response = await fetch(`${API_BASE}/auth/google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential }),
  })

  if (!response.ok) {
    let message = `La connexion Google a échoué (HTTP ${response.status}).`
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') message = body.detail
    } catch {
      // Keep generic message.
    }
    throw new ApiError(response.status, message)
  }

  const result = await response.json() as AuthResponse
  setAccessToken(result.access_token)
  return result
}
