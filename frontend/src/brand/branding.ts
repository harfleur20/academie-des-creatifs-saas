export const DEFAULT_PLATFORM_LOGO_URL =
  '/logo-academie-icone.png'

/** Transparent light mark for dark platform surfaces. */
export const PLATFORM_ICON_LIGHT_URL = '/logo-academie-icone-clair.png'

/** The full "L'académie des créatifs · Pour les écoles" wordmark, for light backgrounds. */
export const PLATFORM_WORDMARK_URL = '/logo-academie-ecoles.png'

/** The same wordmark in white and bright teal, for the dark sidebars and panels. */
export const PLATFORM_WORDMARK_LIGHT_URL = '/logo-academie-ecoles-clair.png'

/** What a school shows until it uploads its own logo: the transparent platform mark. */
export const DEFAULT_SCHOOL_LOGO_URL = '/logo-academie-icone.png'

export const DEFAULT_BRAND_COLORS = {
  primary: '#1F2559',
  secondary: '#18A7A3',
  accent: '#131735',
}

export function resolveBrandLogo(logoUrl?: string | null) {
  return logoUrl?.trim() || DEFAULT_PLATFORM_LOGO_URL
}
