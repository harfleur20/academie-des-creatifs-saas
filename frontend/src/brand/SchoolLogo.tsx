import type { CSSProperties } from 'react'
import { AdaptiveLogoImage } from './AdaptiveLogoImage'
import { DEFAULT_SCHOOL_LOGO_URL } from './branding'

type SchoolLogoProps = {
  logoUrl?: string | null
  alt: string
  className?: string
  /** The school is still loading: keep its place empty, never the platform's mark meanwhile. */
  pending?: boolean
  style?: CSSProperties
}

/** A school's logo, or the platform's round mark until the school uploads its own. */
export function SchoolLogo({ logoUrl, alt, className = '', pending = false, style }: SchoolLogoProps) {
  if (pending) return <span className={className} style={{ display: 'inline-block', ...style }} aria-hidden="true" />
  return (
    <AdaptiveLogoImage
      className={className}
      src={logoUrl?.trim() || DEFAULT_SCHOOL_LOGO_URL}
      alt={alt}
      draggable={false}
    />
  )
}
