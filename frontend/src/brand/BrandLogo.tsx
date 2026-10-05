import { AdaptiveLogoImage } from './AdaptiveLogoImage'
import { resolveBrandLogo } from './branding'

type BrandLogoProps = {
  logoUrl?: string | null
  alt?: string
  className?: string
}

export function BrandLogo({
  logoUrl,
  alt = 'Académie des Créatifs',
  className = '',
}: BrandLogoProps) {
  return (
    <AdaptiveLogoImage
      className={className}
      src={resolveBrandLogo(logoUrl)}
      alt={alt}
      draggable={false}
    />
  )
}
