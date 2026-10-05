import { useEffect, useState, type CSSProperties, type FormEvent } from 'react'
import { BrandLogo } from '../brand/BrandLogo'
import { SchoolLogo } from '../brand/SchoolLogo'
import { ArrowRight, Check, Eye, EyeOff } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { GoogleAuthButton } from '../auth/GoogleAuthButton'
import { confirmPasswordReset, requestPasswordReset } from '../auth/passwordResetApi'
import { useAuth } from '../auth/AuthContext'
import { ApiError, getPublicSchoolIdentity, resolveHostBranding, type HostBranding } from '../lib/api'

type AuthMode = 'login' | 'register' | 'forgot' | 'reset'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, signIn, signUp, signInWithGoogle } = useAuth()
  const searchParams = new URLSearchParams(location.search)
  const requestedReturn = searchParams.get('return')
  const returnPath = requestedReturn?.startsWith('/') && !requestedReturn.startsWith('//') && !requestedReturn.includes('\\')
    ? requestedReturn
    : null
  const schoolKey = searchParams.get('school')
  const resetToken = searchParams.get('reset_token')
  const [mode, setMode] = useState<AuthMode>(() =>
    resetToken
      ? 'reset'
      : searchParams.get('mode') === 'register'
        ? 'register'
        : 'login',
  )
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [hostBrand, setHostBrand] = useState<HostBranding | null>(null)
  const isPublicSchool = Boolean(schoolKey || hostBrand)

  useEffect(() => {
    if (user) navigate(returnPath || '/app', { replace: true })
  }, [user, navigate, returnPath])

  useEffect(() => {
    if (resetToken) setMode('reset')
  }, [resetToken])

  useEffect(() => {
    if (schoolKey) {
      getPublicSchoolIdentity(schoolKey)
        .then((school) => setHostBrand({
          organization_id: school.organization_id,
          name: school.site_name,
          slug: school.slug,
          subdomain: school.subdomain,
          hostname: school.slug,
          logo_url: school.logo_url,
          primary_color: school.primary_color,
          secondary_color: school.secondary_color,
          accent_color: school.accent_color,
        }))
        .catch(() => setHostBrand(null))
      return
    }
    const hostname = window.location.hostname
    if (hostname === 'localhost' || hostname === '127.0.0.1') return
    resolveHostBranding(hostname).then(setHostBrand).catch(() => setHostBrand(null))
  }, [schoolKey])

  function switchMode(nextMode: AuthMode) {
    setError('')
    setSuccess('')
    setPassword('')
    setConfirmPassword('')
    setShowPassword(false)
    setMode(nextMode)
  }

  function returnToLogin(message = '') {
    switchMode('login')
    if (message) setSuccess(message)
    const params = new URLSearchParams()
    if (schoolKey) params.set('school', schoolKey)
    if (returnPath) params.set('return', returnPath)
    const query = params.toString()
    navigate(`/login${query ? `?${query}` : ''}`, { replace: true })
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    setSuccess('')

    try {
      if (mode === 'login') {
        await signIn(email, password)
        navigate(returnPath || '/app', { replace: true })
        return
      }

      if (mode === 'register') {
        await signUp(fullName, email, password)
        navigate(returnPath || '/app', { replace: true })
        return
      }

      if (mode === 'forgot') {
        const result = await requestPasswordReset(email, schoolKey || hostBrand?.slug || null)
        setSuccess(result.message)
        return
      }

      if (!resetToken) {
        setError('Le lien de réinitialisation est invalide ou incomplet.')
        return
      }
      if (password !== confirmPassword) {
        setError('Les deux mots de passe ne correspondent pas.')
        return
      }

      const result = await confirmPasswordReset(resetToken, password)
      returnToLogin(result.message)
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : 'Impossible de continuer.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  async function handleGoogleCredential(credential: string) {
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      await signInWithGoogle(credential)
      navigate(returnPath || '/app', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de continuer avec Google.')
    } finally {
      setSubmitting(false)
    }
  }

  const heading = mode === 'login'
    ? 'Heureux de vous revoir.'
    : mode === 'register'
      ? 'Commençons ensemble.'
      : mode === 'forgot'
        ? 'Mot de passe oublié ?'
        : 'Nouveau mot de passe.'

  const intro = mode === 'login'
    ? isPublicSchool ? 'Connectez-vous pour retrouver votre parcours.' : 'Connectez-vous pour retrouver votre espace école.'
    : mode === 'register'
      ? isPublicSchool ? 'Créez votre compte pour rejoindre les formations.' : 'Créez votre compte, puis donnez vie à votre école.'
      : mode === 'forgot'
        ? 'Indiquez votre adresse email. Nous vous enverrons un lien sécurisé valable 30 minutes.'
        : 'Choisissez un nouveau mot de passe d’au moins 8 caractères.'

  const submitLabel = submitting
    ? mode === 'forgot' ? 'Envoi en cours…' : 'Veuillez patienter…'
    : mode === 'login'
      ? 'Se connecter'
      : mode === 'register'
        ? 'Créer mon compte'
        : mode === 'forgot'
          ? 'Recevoir le lien'
          : 'Réinitialiser le mot de passe'

  return (
    <main
      className={`auth-page login-redesign ${isPublicSchool ? 'login-school' : 'login-platform'} ${mode === 'register' ? 'auth-register-mode' : 'auth-login-mode'}`}
      style={hostBrand ? {
        '--blue': hostBrand.primary_color,
        '--green': hostBrand.secondary_color,
        '--button-end': `color-mix(in srgb, ${hostBrand.primary_color} 80%, white)`,
      } as CSSProperties : undefined}
    >
      <section className="auth-panel auth-copy-panel">
        <a className="auth-logo" href={schoolKey ? '/school/' + encodeURIComponent(schoolKey) : '/'}>
          {isPublicSchool
            ? <SchoolLogo logoUrl={hostBrand?.logo_url} alt={hostBrand?.name || 'École'} className="platform-brand-logo" />
            : <BrandLogo className="platform-brand-logo" />}
          <span>
            {hostBrand?.name || (isPublicSchool ? 'Votre école' : 'Académie')}
            {!isPublicSchool && <> <strong>SaaS</strong></>}
          </span>
        </a>
        <div className="auth-visual-copy">
          {isPublicSchool ? <>
            <span className="auth-kicker">Votre espace personnel</span>
            <h1>La suite de votre parcours commence ici.</h1>
            <p>Retrouvez vos formations, vos cours et vos progrès dans un espace à votre image.</p>
          </> : <>
            <span className="auth-kicker">Votre école digitale</span>
            <h1>Toute votre école, à votre image.</h1>
            <p>
              Créez vos formations, accompagnez vos élèves et faites grandir
              votre communauté créative.
            </p>
          </>}
          <span className="auth-visual-caption"><Check size={15} /> Un espace pensé pour apprendre et transmettre</span>
        </div>
      </section>

      <section className="auth-panel auth-form-panel">
        <form className="auth-card" onSubmit={submit}>
          <span className="auth-form-kicker">{isPublicSchool ? hostBrand?.name || 'Votre école' : 'Académie des Créatifs'}</span>
          <h2>{heading}</h2>
          <p>{intro}</p>

          {mode === 'register' && (
            <label>
              Nom complet
              <input
                id="auth-full-name"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                minLength={2}
                maxLength={180}
                required
                autoComplete="name"
                placeholder="Votre nom"
              />
            </label>
          )}

          {(mode === 'login' || mode === 'register' || mode === 'forgot') && (
            <label>
              Adresse email
              <input
                id="auth-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                autoComplete="email"
                placeholder="vous@ecole.com"
              />
            </label>
          )}

          {(mode === 'login' || mode === 'register' || mode === 'reset') && (
            <label>
              {mode === 'reset' ? 'Nouveau mot de passe' : 'Mot de passe'}
              <span className="password-field">
                <input
                  id="auth-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  minLength={8}
                  maxLength={72}
                  required
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  placeholder="8 caractères minimum"
                />
                <button
                  type="button"
                  aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                  onClick={() => setShowPassword((value) => !value)}
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </span>
            </label>
          )}

          {mode === 'reset' && (
            <label>
              Confirmer le mot de passe
              <input
                id="auth-password-confirm"
                type={showPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                minLength={8}
                maxLength={72}
                required
                autoComplete="new-password"
                placeholder="Confirmez votre mot de passe"
              />
            </label>
          )}

          {mode === 'login' && (
            <button
              className="auth-forgot-link"
              type="button"
              onClick={() => switchMode('forgot')}
            >
              Mot de passe oublié ?
            </button>
          )}

          {error && <div className="form-error">{error}</div>}
          {success && <div className="form-success">{success}</div>}

          <button className="primary-button full auth-submit" disabled={submitting}>
            {submitLabel}
            {!submitting && <ArrowRight size={17} />}
          </button>

          {(mode === 'login' || mode === 'register') && <>
            <div className="auth-divider"><span>ou</span></div>
            <GoogleAuthButton
              mode={mode}
              disabled={submitting}
              onCredential={handleGoogleCredential}
              onError={setError}
            />
          </>}

          {(mode === 'forgot' || mode === 'reset') ? (
            <button
              className="auth-switch"
              type="button"
              onClick={() => returnToLogin()}
            >
              Retour à la connexion
            </button>
          ) : (
            <button
              className="auth-switch"
              type="button"
              onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}
            >
              {mode === 'login'
                ? isPublicSchool
                  ? <>Pas encore de compte ? <span className="auth-switch-accent">S’inscrire</span></>
                  : <>Pas encore de compte ? <span className="auth-switch-accent">Créer mon école</span></>
                : <>Déjà un compte ? <span className="auth-switch-accent">Se connecter</span></>}
            </button>
          )}
        </form>
      </section>
    </main>
  )
}
