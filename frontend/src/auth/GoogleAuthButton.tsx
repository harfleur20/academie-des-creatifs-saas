import { useEffect, useRef } from 'react'

type GoogleCredentialResponse = {
  credential?: string
}

type GoogleIdentityApi = {
  initialize: (options: {
    client_id: string
    callback: (response: GoogleCredentialResponse) => void
  }) => void
  renderButton: (
    element: HTMLElement,
    options: {
      type: 'standard'
      theme: 'outline'
      size: 'large'
      text: 'signin_with' | 'signup_with'
      shape: 'rectangular'
      logo_alignment: 'left'
      width: number
      locale: string
    },
  ) => void
}

declare global {
  interface Window {
    google?: {
      accounts?: {
        id?: GoogleIdentityApi
      }
    }
  }
}

type GoogleAuthButtonProps = {
  mode: 'login' | 'register'
  disabled?: boolean
  onCredential: (credential: string) => void | Promise<void>
  onError: (message: string) => void
}

const SCRIPT_ID = 'google-identity-services-script'

export function GoogleAuthButton({
  mode,
  disabled = false,
  onCredential,
  onError,
}: GoogleAuthButtonProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const onCredentialRef = useRef(onCredential)
  const onErrorRef = useRef(onError)
  const clientId = (import.meta.env.VITE_GOOGLE_CLIENT_ID || '').trim()

  useEffect(() => {
    onCredentialRef.current = onCredential
    onErrorRef.current = onError
  }, [onCredential, onError])

  useEffect(() => {
    if (!clientId) return

    let cancelled = false
    const container = containerRef.current
    if (!container) return

    const renderGoogleButton = () => {
      if (cancelled || !containerRef.current) return
      const googleIdentity = window.google?.accounts?.id
      if (!googleIdentity) {
        onErrorRef.current('Impossible de charger la connexion Google.')
        return
      }

      const target = containerRef.current
      target.innerHTML = ''
      googleIdentity.initialize({
        client_id: clientId,
        callback: (response) => {
          if (!response.credential) {
            onErrorRef.current('Google n’a pas renvoyé de jeton de connexion.')
            return
          }
          void onCredentialRef.current(response.credential)
        },
      })
      googleIdentity.renderButton(target, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        text: mode === 'login' ? 'signin_with' : 'signup_with',
        shape: 'rectangular',
        logo_alignment: 'left',
        width: Math.max(240, Math.floor(target.getBoundingClientRect().width || 360)),
        locale: 'fr',
      })
    }

    if (window.google?.accounts?.id) {
      renderGoogleButton()
      return () => {
        cancelled = true
      }
    }

    let script = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null
    const created = !script
    if (!script) {
      script = document.createElement('script')
      script.id = SCRIPT_ID
      script.src = 'https://accounts.google.com/gsi/client'
      script.async = true
      script.defer = true
      document.head.appendChild(script)
    }

    script.addEventListener('load', renderGoogleButton)
    const onScriptError = () => onErrorRef.current('Impossible de charger la connexion Google.')
    script.addEventListener('error', onScriptError)

    return () => {
      cancelled = true
      script?.removeEventListener('load', renderGoogleButton)
      script?.removeEventListener('error', onScriptError)
      if (created && script && !script.dataset.loaded) script.dataset.loaded = 'true'
    }
  }, [clientId, mode])

  if (!clientId) {
    return (
      <button
        type="button"
        className="google-auth-fallback"
        disabled={disabled}
        onClick={() => onError('Connexion Google non configurée. Ajoutez VITE_GOOGLE_CLIENT_ID.')}
      >
        <span className="google-g-mark" aria-hidden="true">G</span>
        {mode === 'login' ? 'Se connecter avec Google' : 'S’inscrire avec Google'}
      </button>
    )
  }

  return (
    <div
      ref={containerRef}
      className={`google-auth-button ${disabled ? 'is-disabled' : ''}`}
      aria-label={mode === 'login' ? 'Se connecter avec Google' : 'S’inscrire avec Google'}
    />
  )
}
