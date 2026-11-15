type CachedDirectionAccent = {
  color: string
  followsSchoolAccent: boolean
}

const PREFIX = 'academie_saas_direction_accent:'

export function cacheDirectionAccent(organizationId: number, color: string, followsSchoolAccent: boolean) {
  try {
    sessionStorage.setItem(`${PREFIX}${organizationId}`, JSON.stringify({ color, followsSchoolAccent }))
  } catch {
    // The live organization state remains available if storage is blocked.
  }
}

export function readCachedDirectionAccent(organizationId: number, schoolAccent?: string | null) {
  try {
    const raw = sessionStorage.getItem(`${PREFIX}${organizationId}`)
    if (!raw) return schoolAccent || null
    const cached = JSON.parse(raw) as CachedDirectionAccent
    return cached.followsSchoolAccent ? schoolAccent || cached.color : cached.color
  } catch {
    return schoolAccent || null
  }
}
