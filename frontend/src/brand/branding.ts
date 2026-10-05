export const DEFAULT_PLATFORM_LOGO_URL =
  '/logo_ico_hd.png'

export const DEFAULT_BRAND_COLORS = {
  primary: '#1F2559',
  secondary: '#18A7A3',
  accent: '#131735',
}

export function resolveBrandLogo(logoUrl?: string | null) {
  return logoUrl?.trim() || DEFAULT_PLATFORM_LOGO_URL
}
