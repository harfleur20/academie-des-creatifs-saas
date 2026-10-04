import { Building2 } from 'lucide-react'

type SchoolLogoProps = {
  logoUrl?: string | null
  alt: string
  className?: string
}

export function SchoolLogo({ logoUrl, alt, className = '' }: SchoolLogoProps) {
  if (logoUrl?.trim()) {
    return <img className={`brand-logo-image ${className}`.trim()} src={logoUrl} alt={alt} draggable={false} />
  }

  return (
    <span className={`school-logo-placeholder ${className}`.trim()} role="img" aria-label={alt}>
      <Building2 aria-hidden="true" />
    </span>
  )
}
