import { PLATFORM_WORDMARK_LIGHT_URL, PLATFORM_WORDMARK_URL } from './branding'

type BrandWordmarkProps = {
  /** `light` is the white version, for dark backgrounds. */
  tone?: 'dark' | 'light'
  className?: string
}

export function BrandWordmark({ tone = 'dark', className = '' }: BrandWordmarkProps) {
  return (
    <img
      className={`brand-wordmark ${className}`.trim()}
      src={tone === 'light' ? PLATFORM_WORDMARK_LIGHT_URL : PLATFORM_WORDMARK_URL}
      alt="L’académie des créatifs, pour les écoles"
      width={960}
      height={317}
      draggable={false}
    />
  )
}
