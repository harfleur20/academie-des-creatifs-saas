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
  /** Chosen on the formation page, preselected on the checkout. */
  payment_mode?: 'full' | 'installments'
  deposit_cents?: number | null
  balance_cents?: number | null
  balance_due_date?: string | null
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
    && (item.deposit_cents === undefined || item.deposit_cents === null || typeof item.deposit_cents === 'number')
    && (item.balance_cents === undefined || item.balance_cents === null || typeof item.balance_cents === 'number')
    && (item.balance_due_date === undefined || item.balance_due_date === null || typeof item.balance_due_date === 'string')
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
