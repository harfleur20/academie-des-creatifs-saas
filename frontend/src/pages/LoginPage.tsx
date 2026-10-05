import { useEffect, useState, type CSSProperties, type FormEvent } from 'react'
import { BrandLogo } from '../brand/BrandLogo'
import { SchoolLogo } from '../brand/SchoolLogo'
import { ArrowRight, Check, Eye, EyeOff } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { GoogleAuthButton } from '../auth/GoogleAuthButton'
import { useAuth } from '../auth/AuthContext'
import { ApiError, getPublicSchoolIdentity, resolveHostBranding, type HostBranding } from '../lib/api'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, signIn, signUp, signInWithGoogle } = useAuth()
  const requestedReturn = new URLSearchParams(location.search).get('return')
  const returnPath = requestedReturn?.startsWith('/') && !requestedReturn.startsWith('//') && !requestedReturn.includes('\\')
    ? requestedReturn
    : null
  const schoolKey = new URLSearchParams(location.search).get('school')
  const [mode, setMode] = useState<'login' | 'register'>(() =>
    new URLSearchParams(location.search).get('mode') === 'register'
      ? 'register'
      : 'login',
  )
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [hostBrand, setHostBrand] = useState<HostBranding | null>(null)
  const isPublicSchool = Boolean(schoolKey || hostBrand)

  useEffect(() => {
    if (user) navigate(returnPath || '/app', { replace: true })
  }, [user, navigate, returnPath])

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

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')

    try {
      if (mode === 'login') {
        await signIn(email, password)
      } else {
        await signUp(fullName, email, password)
      }
      navigate(returnPath || '/app', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de continuer.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleGoogleCredential(credential: string) {
    setSubmitting(true)
    setError('')
    try {
      await signInWithGoogle(credential)
      navigate(returnPath || '/app', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de continuer avec Google.')
    } finally {
      setSubmitting(false)
    }
  }

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
          <h2>{mode === 'login' ? 'Heureux de vous revoir.' : 'Commençons ensemble.'}</h2>
          <p>
            {mode === 'login'
              ? isPublicSchool ? 'Connectez-vous pour retrouver votre parcours.' : 'Connectez-vous pour retrouver votre espace école.'
              : isPublicSchool ? 'Créez votre compte pour rejoindre les formations.' : 'Créez votre compte, puis donnez vie à votre école.'}
          </p>

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

          <label>
            Mot de passe
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

          {error && <div className="form-error">{error}</div>}

          <button className="primary-button full auth-submit" disabled={submitting}>
            {submitting
              ? 'Veuillez patienter…'
              : mode === 'login'
                ? 'Se connecter'
                : 'Créer mon compte'}
            {!submitting && <ArrowRight size={17} />}
          </button>

          <div className="auth-divider"><span>ou</span></div>
          <GoogleAuthButton
            mode={mode}
            disabled={submitting}
            onCredential={handleGoogleCredential}
            onError={setError}
          />

          <button
            className="auth-switch"
            type="button"
            onClick={() => {
              setError('')
              setMode((value) => (value === 'login' ? 'register' : 'login'))
            }}
          >
            {mode === 'login'
              ? isPublicSchool
                ? <>Pas encore de compte ? <span className="auth-switch-accent">S’inscrire</span></>
                : <>Pas encore de compte ? <span className="auth-switch-accent">Créer mon école</span></>
              : <>Déjà un compte ? <span className="auth-switch-accent">Se connecter</span></>}
          </button>
        </form>
      </section>
    </main>
  )
}
