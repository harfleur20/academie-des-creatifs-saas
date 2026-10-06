import type { CSSProperties } from 'react'
import type { Organization } from '../lib/api'
import { DEFAULT_BRAND_COLORS } from './branding'

export type SchoolIdentity = {
  name: string
  logoUrl: string | null
  primary: string
  secondary: string
  accent: string
  style: CSSProperties
}

export function resolveSchoolIdentity(organization?: Organization | null): SchoolIdentity {
  const primary = organization?.primary_color || DEFAULT_BRAND_COLORS.primary
  const secondary = organization?.secondary_color || DEFAULT_BRAND_COLORS.secondary
  const accent = organization?.accent_color || DEFAULT_BRAND_COLORS.accent

  return {
    name: organization?.name || 'Académie des Créatifs',
    logoUrl: organization?.logo_url || null,
    primary,
    secondary,
    accent,
    style: {
      '--blue': primary,
      '--green': secondary,
      '--button-end': `color-mix(in srgb, ${primary} 80%, white)`,
      '--tenant-accent': accent,
      '--school-primary': primary,
      '--school-secondary': secondary,
      '--school-accent': accent,
    } as CSSProperties,
  }
}
