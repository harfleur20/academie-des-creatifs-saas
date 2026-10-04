interface Window {
  YT?: {
    Player: new (
      element: HTMLIFrameElement,
      options: Record<string, unknown>,
    ) => {
      destroy: () => void
      getCurrentTime: () => number
      getDuration: () => number
      getPlaybackRate: () => number
    }
    PlayerState: { PLAYING: number; ENDED: number }
  }
  onYouTubeIframeAPIReady?: () => void
  Vimeo?: {
    Player: new (element: HTMLIFrameElement) => {
      on: (event: string, callback: (payload?: Record<string, number>) => void) => void
      off: (event: string, callback?: (payload?: Record<string, number>) => void) => void
      getDuration: () => Promise<number>
      getCurrentTime: () => Promise<number>
    }
  }
}
