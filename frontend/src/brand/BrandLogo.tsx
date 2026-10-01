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
    <img
      className={`brand-logo-image ${className}`.trim()}
      src={resolveBrandLogo(logoUrl)}
      alt={alt}
      draggable={false}
    />
  )
}
