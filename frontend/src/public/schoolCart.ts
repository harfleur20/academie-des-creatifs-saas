export type SchoolCartItem = {
  organization_id: number
  formation_id: number
  formation_slug: string
  formation_title: string
  session_id: number
  session_label: string
  format_type?: string
  price_cents: number
  currency: string
  cover_image_url: string | null
}

function key(schoolSlug: string) {
  return 'academie_school_cart_' + schoolSlug
}

function isValidCartItem(value: unknown): value is SchoolCartItem {
  if (!value || typeof value !== 'object') return false
  const item = value as Partial<SchoolCartItem>
  return (
    Number.isInteger(item.organization_id)
    && Number.isInteger(item.formation_id)
    && Number.isInteger(item.session_id)
    && typeof item.formation_slug === 'string'
    && typeof item.formation_title === 'string'
    && typeof item.session_label === 'string'
    && typeof item.price_cents === 'number'
    && typeof item.currency === 'string'
  )
}

export function getSchoolCart(schoolSlug: string): SchoolCartItem | null {
  const storageKey = key(schoolSlug)
  const raw = localStorage.getItem(storageKey)
  if (!raw) return null
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!isValidCartItem(parsed)) {
      localStorage.removeItem(storageKey)
      return null
    }
    return parsed
  } catch {
    localStorage.removeItem(storageKey)
    return null
  }
}

export function setSchoolCart(schoolSlug: string, item: SchoolCartItem) {
  localStorage.setItem(key(schoolSlug), JSON.stringify(item))
  window.dispatchEvent(new CustomEvent('school-cart-changed', { detail: { schoolSlug } }))
}

export function clearSchoolCart(schoolSlug: string) {
  localStorage.removeItem(key(schoolSlug))
  window.dispatchEvent(new CustomEvent('school-cart-changed', { detail: { schoolSlug } }))
}
