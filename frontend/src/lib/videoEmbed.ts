export type VideoEmbed = { kind: 'youtube' | 'vimeo' | 'stream' | 'direct'; src: string }

export function parseVideoEmbed(url: string): VideoEmbed {
  try {
    const parsed = new URL(url)
    const host = parsed.hostname.replace(/^www\./, '').toLowerCase()
    if (host === 'youtu.be' || host === 'youtube.com' || host.endsWith('.youtube.com') || host === 'youtube-nocookie.com') {
      const parts = parsed.pathname.split('/').filter(Boolean)
      const id = host === 'youtu.be' ? parts[0]
        : parsed.searchParams.get('v') || (['embed', 'shorts', 'live'].includes(parts[0] ?? '') ? parts[1] : null)
      if (id && /^[a-zA-Z0-9_-]{11}$/.test(id)) {
        return { kind: 'youtube', src: `https://www.youtube.com/embed/${id}?enablejsapi=1&playsinline=1&rel=0` }
      }
    }
    if (host === 'vimeo.com' || host.endsWith('.vimeo.com')) {
      const id = parsed.pathname.split('/').find((part) => /^\d+$/.test(part))
      if (id) return { kind: 'vimeo', src: `https://player.vimeo.com/video/${id}?api=1&playsinline=1` }
    }
    if (host === 'player.mediadelivery.net' || host === 'iframe.mediadelivery.net') {
      return { kind: 'stream', src: url }
    }
  } catch {
    // The native player will reject malformed URLs without loading an external script.
  }
  return { kind: 'direct', src: url }
}

const loadedScripts = new Map<string, Promise<void>>()

function loadScriptOnce(src: string): Promise<void> {
  const existing = loadedScripts.get(src)
  if (existing) return existing
  const promise = new Promise<void>((resolve, reject) => {
    const script = document.querySelector<HTMLScriptElement>(`script[src="${src}"]`) || document.createElement('script')
    if (script.dataset.loaded === 'true') { resolve(); return }
    script.addEventListener('load', () => { script.dataset.loaded = 'true'; resolve() }, { once: true })
    script.addEventListener('error', () => reject(new Error(`Impossible de charger ${src}`)), { once: true })
    if (!script.isConnected) { script.src = src; script.async = true; document.head.appendChild(script) }
  })
  loadedScripts.set(src, promise)
  return promise
}

export function loadYouTubeApi(): Promise<void> {
  if (window.YT?.Player) return Promise.resolve()
  return new Promise<void>((resolve, reject) => {
    const previous = window.onYouTubeIframeAPIReady
    window.onYouTubeIframeAPIReady = () => { previous?.(); resolve() }
    void loadScriptOnce('https://www.youtube.com/iframe_api').catch(reject)
  })
}

export function loadVimeoApi(): Promise<void> {
  if (window.Vimeo?.Player) return Promise.resolve()
  return loadScriptOnce('https://player.vimeo.com/api/player.js')
}

export function loadBunnyPlayerApi(): Promise<void> {
  if (window.playerjs?.Player) return Promise.resolve()
  return loadScriptOnce('https://assets.mediadelivery.net/playerjs/player-0.1.0.min.js')
}
