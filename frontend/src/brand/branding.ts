export const DEFAULT_PLATFORM_LOGO_URL =
  'https://academiecreatif.com/logo_ico_hd.png'

export const DEFAULT_BRAND_COLORS = {
  primary: '#1768FF',
  secondary: '#21C889',
  accent: '#10233F',
}

export function resolveBrandLogo(logoUrl?: string | null) {
  return logoUrl?.trim() || DEFAULT_PLATFORM_LOGO_URL
}
