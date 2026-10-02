export type SchoolCartItem = {
  formation_slug: string
  formation_title: string
  session_id: number
  session_label: string
  price_cents: number
  currency: string
  cover_image_url: string | null
}

function key(schoolSlug: string) {
  return 'academie_school_cart_' + schoolSlug
}

export function getSchoolCart(schoolSlug: string): SchoolCartItem | null {
  const raw = localStorage.getItem(key(schoolSlug))
  if (!raw) return null
  try {
    return JSON.parse(raw) as SchoolCartItem
  } catch {
    localStorage.removeItem(key(schoolSlug))
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
