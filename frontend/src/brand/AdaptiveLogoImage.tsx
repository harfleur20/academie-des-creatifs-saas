import { useEffect, useState, type ImgHTMLAttributes } from 'react'

type LogoAlpha = 'unknown' | 'transparent' | 'opaque'

type AdaptiveLogoImageProps = Omit<ImgHTMLAttributes<HTMLImageElement>, 'src'> & {
  src: string
}

const SAMPLE_SIZE = 56

function detectTransparency(image: HTMLImageElement): LogoAlpha {
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
    if (!context) return 'unknown'
    context.clearRect(0, 0, sampleWidth, sampleHeight)
    context.drawImage(image, 0, 0, sampleWidth, sampleHeight)
    const pixels = context.getImageData(0, 0, sampleWidth, sampleHeight).data
    const pixelCount = sampleWidth * sampleHeight
    let transparentPixels = 0
    for (let index = 3; index < pixels.length; index += 4) {
      if (pixels[index] < 245) transparentPixels += 1
    }
    return transparentPixels > Math.max(4, pixelCount * 0.01) ? 'transparent' : 'opaque'
  } catch {
    return 'unknown'
  }
}

export function AdaptiveLogoImage({ src, className = '', alt = '', ...props }: AdaptiveLogoImageProps) {
  const [alpha, setAlpha] = useState<LogoAlpha>('unknown')

  useEffect(() => {
    let cancelled = false
    setAlpha('unknown')
    const probe = new Image()
    probe.crossOrigin = 'anonymous'
    probe.decoding = 'async'
    probe.onload = () => {
      if (!cancelled) setAlpha(detectTransparency(probe))
    }
    probe.onerror = () => {
      if (!cancelled) setAlpha('unknown')
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
      className={`brand-logo-image adaptive-logo-image logo-alpha-${alpha} ${className}`.trim()}
    />
  )
}
