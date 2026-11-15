export function recolorTealPixels(imageUrl: string, color: string, onReady: (source: string) => void) {
  const image = new Image()
  image.onload = () => {
    try {
      const canvas = document.createElement('canvas')
      canvas.width = image.naturalWidth
      canvas.height = image.naturalHeight
      const context = canvas.getContext('2d', { willReadFrequently: true })
      if (!context) return onReady(imageUrl)

      context.drawImage(image, 0, 0)
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height)
      const rgb = color.match(/[\da-f]{2}/gi)?.map((part) => Number.parseInt(part, 16))
      if (!rgb || rgb.length !== 3) return onReady(imageUrl)

      for (let index = 0; index < pixels.data.length; index += 4) {
        const red = pixels.data[index]
        const green = pixels.data[index + 1]
        const blue = pixels.data[index + 2]
        const maximum = Math.max(red, green, blue)
        const minimum = Math.min(red, green, blue)
        const delta = maximum - minimum
        if (delta === 0 || maximum === 0) continue

        let hue = 0
        if (maximum === green) hue = ((blue - red) / delta + 2) * 60
        else if (maximum === blue) hue = ((red - green) / delta + 4) * 60
        else hue = ((green - blue) / delta + (green < blue ? 6 : 0)) * 60
        const saturation = delta / maximum
        if (hue >= 155 && hue <= 195 && saturation > 0.2) {
          pixels.data[index] = rgb[0]
          pixels.data[index + 1] = rgb[1]
          pixels.data[index + 2] = rgb[2]
        }
      }

      context.putImageData(pixels, 0, 0)
      onReady(canvas.toDataURL('image/png'))
    } catch {
      onReady(imageUrl)
    }
  }
  image.onerror = () => onReady(imageUrl)
  image.src = imageUrl
}
