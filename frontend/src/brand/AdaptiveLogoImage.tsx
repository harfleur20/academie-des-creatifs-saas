import { useEffect, useState, type ImgHTMLAttributes } from 'react'

type LogoAlpha = 'unknown' | 'transparent' | 'opaque'
/**
 * What the visible part of a transparent logo looks like on a dark background:
 * - `dark`: dark marks (a black wordmark...), nearly invisible there: dark places turn it white;
 * - `light`: marks bright enough to read as they are;
 * - `tile`: a filled shape (an app-icon square, a badge) that carries its own background.
 */
type LogoTone = 'unknown' | 'dark' | 'light' | 'tile'
type LogoAnalysis = { alpha: LogoAlpha; tone: LogoTone }

type AdaptiveLogoImageProps = Omit<ImgHTMLAttributes<HTMLImageElement>, 'src'> & {
  src: string
}

const SAMPLE_SIZE = 56
const UNKNOWN: LogoAnalysis = { alpha: 'unknown', tone: 'unknown' }
const TILE_COVERAGE = 0.6 // a shape filling 60 % of its box is a tile, not a wordmark
const READABLE_CONTRAST = 3 // against the dark footers and panels (#101d30), WCAG large text

function channel(value: number) {
  const unit = value / 255
  return unit <= 0.03928 ? unit / 12.92 : ((unit + 0.055) / 1.055) ** 2.4
}

function detectTransparency(image: HTMLImageElement): LogoAnalysis {
  try {
    const width = Math.max(1, image.naturalWidth || SAMPLE_SIZE)
    const height = Math.max(1, image.naturalHeight || SAMPLE_SIZE)
    const scale = Math.min(1, SAMPLE_SIZE / width, SAMPLE_SIZE / height)
    const sampleWidth = Math.max(1, Math.round(width * scale))
    const sampleHeight = Math.max(1, Math.round(height * scale))
    const canvas = document.createElement('canvas')
    canvas.width = sampleWidth
    canvas.height = sampleHeight
    const context = canvas.getContext('2d', { willReadFrequently: true })
    if (!context) return UNKNOWN
    context.clearRect(0, 0, sampleWidth, sampleHeight)
    context.drawImage(image, 0, 0, sampleWidth, sampleHeight)
    const pixels = context.getImageData(0, 0, sampleWidth, sampleHeight).data
    const pixelCount = sampleWidth * sampleHeight
    let transparentPixels = 0
    let visiblePixels = 0
    let luminance = 0
    for (let index = 0; index < pixels.length; index += 4) {
      const opacity = pixels[index + 3]
      if (opacity < 245) transparentPixels += 1
      if (opacity >= 128) {
        visiblePixels += 1
        luminance += 0.2126 * channel(pixels[index]) + 0.7152 * channel(pixels[index + 1]) + 0.0722 * channel(pixels[index + 2])
      }
    }
    if (transparentPixels <= Math.max(4, pixelCount * 0.01)) return { alpha: 'opaque', tone: 'tile' }
    if (visiblePixels >= pixelCount * TILE_COVERAGE) return { alpha: 'transparent', tone: 'tile' }
    const average = visiblePixels ? luminance / visiblePixels : 0
    const contrast = (average + 0.05) / (channel(0x10) * 0.2126 + channel(0x1d) * 0.7152 + channel(0x30) * 0.0722 + 0.05)
    return { alpha: 'transparent', tone: contrast < READABLE_CONTRAST ? 'dark' : 'light' }
  } catch {
    return UNKNOWN
  }
}

export function AdaptiveLogoImage({ src, className = '', alt = '', ...props }: AdaptiveLogoImageProps) {
  const [{ alpha, tone }, setAnalysis] = useState<LogoAnalysis>(UNKNOWN)

  useEffect(() => {
    let cancelled = false
    setAnalysis(UNKNOWN)
    const probe = new Image()
    probe.crossOrigin = 'anonymous'
    probe.decoding = 'async'
    probe.onload = () => {
      if (!cancelled) setAnalysis(detectTransparency(probe))
    }
    probe.onerror = () => {
      if (!cancelled) setAnalysis(UNKNOWN)
    }
    probe.src = src
    return () => {
      cancelled = true
      probe.onload = null
      probe.onerror = null
    }
  }, [src])

  return (
    <img
      {...props}
      src={src}
      alt={alt}
      data-logo-alpha={alpha}
      data-logo-tone={tone}
      className={`brand-logo-image adaptive-logo-image logo-alpha-${alpha} logo-tone-${tone} ${className}`.trim()}
    />
  )
}
