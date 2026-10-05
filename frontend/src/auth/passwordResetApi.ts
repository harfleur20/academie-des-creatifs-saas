const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

type MessageResponse = {
  message: string
}

async function postMessage(path: string, body: Record<string, unknown>) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    let message = `La requête a échoué (HTTP ${response.status}).`
    try {
      const payload = await response.json()
      if (typeof payload?.detail === 'string') message = payload.detail
    } catch {
      // Keep generic message.
    }
    throw new Error(message)
  }

  return response.json() as Promise<MessageResponse>
}

export function requestPasswordReset(email: string, school?: string | null) {
  return postMessage('/auth/forgot-password', {
    email,
    school: school || null,
  })
}

export function confirmPasswordReset(token: string, newPassword: string) {
  return postMessage('/auth/reset-password', {
    token,
    new_password: newPassword,
  })
}
