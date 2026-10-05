import { setAccessToken, type AuthResponse, type AuthUser } from '../lib/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const ATTEMPT_KEY = 'academie_saas_custom_domain_sso_attempt'
const ATTEMPT_TTL_MS = 30_000

type SsoConfig = {
  enabled: boolean
  start_url: string | null
}

function cleanSsoFragment() {
  window.history.replaceState(null, '', window.location.pathname + window.location.search)
}

function currentReturnUrl() {
  return window.location.origin + window.location.pathname + window.location.search
}

export async function consumeCustomDomainSsoHandoff(): Promise<AuthUser | null> {
  const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  const handoff = fragment.get('sso_handoff')
  const checked = fragment.get('sso_checked')

  if (checked) {
    sessionStorage.setItem(ATTEMPT_KEY, String(Date.now()))
    cleanSsoFragment()
    return null
  }
  if (!handoff) return null

  const response = await fetch(`${API_BASE}/auth/sso/exchange`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: handoff }),
  })
  cleanSsoFragment()
  sessionStorage.setItem(ATTEMPT_KEY, String(Date.now()))

  if (!response.ok) return null
  const result = await response.json() as AuthResponse
  setAccessToken(result.access_token)
  return result.user
}

export async function maybeStartCustomDomainSso(): Promise<boolean> {
  const lastAttempt = Number(sessionStorage.getItem(ATTEMPT_KEY) || '0')
  if (Date.now() - lastAttempt < ATTEMPT_TTL_MS) return false

  let config: SsoConfig
  try {
    const response = await fetch(`${API_BASE}/auth/sso/config`, {
      credentials: 'include',
    })
    if (!response.ok) return false
    config = await response.json() as SsoConfig
  } catch {
    return false
  }

  if (!config.enabled || !config.start_url) return false
  sessionStorage.setItem(ATTEMPT_KEY, String(Date.now()))
  const destination = new URL(config.start_url)
  destination.searchParams.set('return_url', currentReturnUrl())
  window.location.replace(destination.toString())
  return true
}
