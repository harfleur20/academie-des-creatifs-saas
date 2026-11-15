import { useEffect, useState } from 'react'
import {
  PLATFORM_ICON_LIGHT_URL,
  PLATFORM_WORDMARK_LIGHT_URL,
} from './branding'
import { recolorTealPixels } from './recolorTealPixels'

function useAccentLogo(source: string, accentColor: string) {
  const [imageSource, setImageSource] = useState(source)

  useEffect(() => {
    if (accentColor.toUpperCase() === '#18A7A3') {
      setImageSource(source)
      return
    }

    let active = true
    recolorTealPixels(source, accentColor, (result) => {
      if (active) setImageSource(result)
    })
    return () => { active = false }
  }, [source, accentColor])

  return imageSource
}

export function DirectionWordmark({ accentColor }: { accentColor: string }) {
  const fullLogo = useAccentLogo(PLATFORM_WORDMARK_LIGHT_URL, accentColor)
  const compactLogo = useAccentLogo(PLATFORM_ICON_LIGHT_URL, accentColor)

  return (
    <div className="direction-brand-wordmark">
      <img
        className="direction-brand-full"
        src={fullLogo}
        alt="L’Académie des Créatifs, pour les écoles"
        width={960}
        height={317}
        draggable={false}
      />
      <img
        className="direction-brand-mark"
        src={compactLogo}
        alt=""
        width={317}
        height={317}
        draggable={false}
      />
    </div>
  )
}
