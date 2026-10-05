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

function GoogleLogo() {
  return (
    <svg
      className="google-g-mark"
      viewBox="0 0 18 18"
      role="img"
      aria-label="Google"
    >
      <path fill="#EA4335" d="M17.64 9.205c0-.639-.057-1.252-.164-1.841H9v3.481h4.844a4.14 4.14 0 0 1-1.797 2.715v2.258h2.909c1.702-1.567 2.684-3.874 2.684-6.613Z" />
      <path fill="#4285F4" d="M9 18c2.43 0 4.468-.806 5.956-2.182l-2.91-2.258c-.806.54-1.835.859-3.046.859-2.344 0-4.328-1.585-5.037-3.714H.956v2.332A9 9 0 0 0 9 18Z" />
      <path fill="#FBBC05" d="M3.963 10.705A5.41 5.41 0 0 1 3.682 9c0-.592.102-1.168.281-1.705V4.963H.956A9 9 0 0 0 0 9c0 1.452.347 2.827.956 4.037l3.007-2.332Z" />
      <path fill="#34A853" d="M9 3.58c1.322 0 2.508.454 3.441 1.346l2.582-2.582C13.464.892 11.426 0 9 0A9 9 0 0 0 .956 4.963l3.007 2.332C4.672 5.166 6.656 3.58 9 3.58Z" />
    </svg>
  )
}

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
        <GoogleLogo />
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
