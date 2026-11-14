import { AdaptiveLogoImage } from './AdaptiveLogoImage'
import { DEFAULT_SCHOOL_LOGO_URL } from './branding'

type SchoolLogoProps = {
  logoUrl?: string | null
  alt: string
  className?: string
}

/** A school's logo, or the platform's round mark until the school uploads its own. */
export function SchoolLogo({ logoUrl, alt, className = '' }: SchoolLogoProps) {
  return (
    <AdaptiveLogoImage
      className={className}
      src={logoUrl?.trim() || DEFAULT_SCHOOL_LOGO_URL}
      alt={alt}
      draggable={false}
    />
  )
}
