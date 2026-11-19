// Google sign-in only works on the addresses registered with Google: the platform's. A school's
// own address (its subdomain or domain) sends the visitor there, then back, signed in.

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

/** The platform's origin when this page is a school's own address; null on the platform itself. */
export function googleRelayOrigin(): string | null {
  const platform = document.querySelector<HTMLMetaElement>('meta[name="academie-platform"]')?.content
  if (!platform) return null
  try {
    const origin = new URL(platform).origin
    return origin === window.location.origin ? null : origin
  } catch {
    return null
  }
}

/** The platform's login page, set to come back to this school once signed in. */
export function googleRelayHref(
  origin: string,
  { mode, school, returnPath }: { mode: 'login' | 'register'; school: string | null; returnPath: string },
): string {
  const params = new URLSearchParams({ mode, google_return: window.location.origin + returnPath })
  if (school) params.set('school', school)
  return `${origin}/login?${params.toString()}`
}

/** Back to the school: the server checks the address, then keeps or hands over the session. */
export function finishGoogleRelay(returnUrl: string) {
  window.location.assign(`${API_BASE}/auth/sso/start?return_url=${encodeURIComponent(returnUrl)}`)
}
