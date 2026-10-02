import { useEffect, useState, type CSSProperties, type FormEvent } from 'react'
import { BrandLogo } from '../brand/BrandLogo'
import { ArrowRight, Building2, Check, Eye, EyeOff } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { ApiError, resolveHostBranding, type HostBranding } from '../lib/api'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, signIn, signUp } = useAuth()
  const returnPath = new URLSearchParams(location.search).get('return')
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

  useEffect(() => {
    if (user) navigate(returnPath || '/app', { replace: true })
  }, [user, navigate, returnPath])

  useEffect(() => {
    if (schoolKey) {
      import('../lib/api').then(({ getPublicSchoolIdentity }) =>
        getPublicSchoolIdentity(schoolKey)
          .then((school) => setHostBrand({
            organization_id: school.organization_id,
            name: school.site_name,
            hostname: school.slug,
            logo_url: school.logo_url,
            primary_color: school.primary_color,
            secondary_color: school.secondary_color,
            accent_color: school.accent_color,
          }))
          .catch(() => setHostBrand(null)),
      )
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

  return (
    <main
      className="auth-page"
      style={hostBrand ? {
        '--blue': hostBrand.primary_color,
        '--green': hostBrand.secondary_color,
      } as CSSProperties : undefined}
    >
      <section className="auth-panel auth-copy-panel">
        <a className="auth-logo" href="/">
          <BrandLogo logoUrl={hostBrand?.logo_url} className="platform-brand-logo" />
          <span>
            {hostBrand?.name || 'Académie'}
            {!hostBrand && <> <strong>SaaS</strong></>}
          </span>
        </a>
        <div>
          <span className="auth-kicker">Votre école digitale</span>
          <h1>Un seul espace pour piloter toute votre école.</h1>
          <p>
            Formations, professeurs, étudiants, cours, lives et suivi pédagogique
            réunis dans une plateforme que vous administrez.
          </p>
          <div className="auth-benefits">
            <span><Check size={16} /> Espace isolé pour chaque école</span>
            <span><Check size={16} /> Rôles et accès maîtrisés</span>
            <span><Check size={16} /> Prêt pour vos abonnements et votre branding</span>
          </div>
        </div>
      </section>

      <section className="auth-panel auth-form-panel">
        <form className="auth-card" onSubmit={submit}>
          <div className="auth-icon"><Building2 size={22} /></div>
          <h2>{mode === 'login' ? 'Bienvenue' : 'Créez votre compte'}</h2>
          <p>
            {mode === 'login'
              ? 'Connectez-vous à votre espace école.'
              : 'Vous pourrez créer votre première école juste après.'}
          </p>

          {mode === 'register' && (
            <label>
              Nom complet
              <input
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                minLength={2}
                maxLength={180}
                required
                placeholder="Votre nom"
              />
            </label>
          )}

          <label>
            Adresse email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              placeholder="vous@ecole.com"
            />
          </label>

          <label>
            Mot de passe
            <span className="password-field">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                minLength={8}
                maxLength={72}
                required
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

          <button className="primary-button full" disabled={submitting}>
            {submitting
              ? 'Veuillez patienter…'
              : mode === 'login'
                ? 'Se connecter'
                : 'Créer mon compte'}
            {!submitting && <ArrowRight size={17} />}
          </button>

          <button
            className="auth-switch"
            type="button"
            onClick={() => {
              setError('')
              setMode((value) => (value === 'login' ? 'register' : 'login'))
            }}
          >
            {mode === 'login'
              ? "Pas encore de compte ? Créer mon école"
              : 'Déjà un compte ? Se connecter'}
          </button>
        </form>
      </section>
    </main>
  )
}
