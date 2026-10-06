import { useEffect, useState, type CSSProperties, type FormEvent } from 'react'
import { BrandLogo } from '../brand/BrandLogo'
import { SchoolLogo } from '../brand/SchoolLogo'
import { ArrowRight, Check, Eye, EyeOff } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { GoogleAuthButton } from '../auth/GoogleAuthButton'
import { confirmPasswordReset, requestPasswordReset } from '../auth/passwordResetApi'
import { useAuth } from '../auth/AuthContext'
import {
  acceptOrganizationInvitation,
  ApiError,
  getInvitationPreview,
  getPublicSchoolIdentity,
  resolveHostBranding,
  setStoredOrganizationId,
  type HostBranding,
  type InvitationPreview,
} from '../lib/api'

type AuthMode = 'login' | 'register' | 'forgot' | 'reset'

const invitationRoleLabels: Record<InvitationPreview['role'], string> = {
  admin: 'Administrateur',
  manager: 'Gestionnaire',
  teacher: 'Enseignant',
}

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, signIn, signUp, signInWithGoogle } = useAuth()
  const searchParams = new URLSearchParams(location.search)
  const requestedReturn = searchParams.get('return')
  const returnPath = requestedReturn?.startsWith('/') && !requestedReturn.startsWith('//') && !requestedReturn.includes('\\')
    ? requestedReturn
    : null
  const invitationMatch = returnPath?.match(/^\/invite\/([^/?#]+)$/)
  const invitationToken = invitationMatch?.[1] ? decodeURIComponent(invitationMatch[1]) : null
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
  const [invitation, setInvitation] = useState<InvitationPreview | null>(null)
  const [invitationLoading, setInvitationLoading] = useState(Boolean(invitationToken))

  useEffect(() => {
    if (!invitationToken) {
      setInvitation(null)
      setInvitationLoading(false)
      return
    }
    let active = true
    setInvitationLoading(true)
    getInvitationPreview(invitationToken)
      .then((preview) => {
        if (!active) return
        setInvitation(preview)
        setEmail(preview.email)
      })
      .catch((cause) => {
        if (!active) return
        setError(cause instanceof ApiError ? cause.message : 'Cette invitation est invalide ou a expiré.')
      })
      .finally(() => {
        if (active) setInvitationLoading(false)
      })
    return () => { active = false }
  }, [invitationToken])

  useEffect(() => {
    if (user && !submitting) navigate(returnPath || '/app', { replace: true })
  }, [user, submitting, navigate, returnPath])

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
    if (invitation) return
    const hostname = window.location.hostname
    if (hostname === 'localhost' || hostname === '127.0.0.1') return
    resolveHostBranding(hostname).then(setHostBrand).catch(() => setHostBrand(null))
  }, [schoolKey, invitation?.organization_id])

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

  async function finishInvitationFlow(authenticatedEmail: string) {
    if (!invitationToken || !invitation) return false
    if (authenticatedEmail.trim().toLowerCase() !== invitation.email.trim().toLowerCase()) {
      throw new Error(`Cette invitation est destinée à ${invitation.email}. Utilisez ce compte pour continuer.`)
    }
    const result = await acceptOrganizationInvitation(invitationToken)
    setStoredOrganizationId(result.organization.id)
    const destination = result.membership.role === 'teacher'
      ? '/app/teacher'
      : '/app/manage'
    window.location.assign(destination)
    return true
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    setSuccess('')

    try {
      if (mode === 'login') {
        await signIn(email, password)
        if (await finishInvitationFlow(email)) return
        navigate(returnPath || '/app', { replace: true })
        return
      }

      if (mode === 'register') {
        await signUp(fullName, email, password)
        if (await finishInvitationFlow(email)) return
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
        err instanceof Error
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
      if (invitation) {
        // Google authentication may resolve to a different address than the prefilled one.
        // The invitation endpoint performs the final identity check server-side.
        const result = await acceptOrganizationInvitation(invitationToken || '')
        setStoredOrganizationId(result.organization.id)
        window.location.assign(result.membership.role === 'teacher' ? '/app/teacher' : '/app/manage')
        return
      }
      navigate(returnPath || '/app', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Impossible de continuer avec Google.')
    } finally {
      setSubmitting(false)
    }
  }

  const invitationBrand = invitation ? {
    organization_id: invitation.organization_id,
    name: invitation.organization_name,
    slug: '',
    subdomain: null,
    hostname: '',
    logo_url: invitation.logo_url,
    primary_color: invitation.primary_color,
    secondary_color: invitation.secondary_color,
    accent_color: invitation.secondary_color,
  } satisfies HostBranding : null
  const activeBrand = invitationBrand || hostBrand
  const isInvitation = Boolean(invitationToken)
  const isPublicSchool = Boolean(schoolKey || hostBrand || invitation)

  const heading = mode === 'login'
    ? isInvitation ? 'Connectez-vous pour rejoindre l’équipe.' : 'Heureux de vous revoir.'
    : mode === 'register'
      ? isInvitation ? `Rejoignez ${invitation?.organization_name || 'votre école'}.` : 'Commençons ensemble.'
      : mode === 'forgot'
        ? 'Mot de passe oublié ?'
        : 'Nouveau mot de passe.'

  const intro = mode === 'login'
    ? isInvitation
      ? `Cette invitation vous donne accès à ${invitation?.organization_name || 'cette école'} en tant que ${invitation ? invitationRoleLabels[invitation.role].toLowerCase() : 'membre de l’équipe'}.`
      : isPublicSchool ? 'Connectez-vous pour retrouver votre parcours.' : 'Connectez-vous pour retrouver votre espace école.'
    : mode === 'register'
      ? isInvitation
        ? `Créez votre compte avec ${invitation?.email || 'l’adresse invitée'} pour rejoindre l’équipe en tant que ${invitation ? invitationRoleLabels[invitation.role].toLowerCase() : 'membre'}.`
        : isPublicSchool ? 'Créez votre compte pour rejoindre les formations.' : 'Créez votre compte, puis donnez vie à votre école.'
      : mode === 'forgot'
        ? 'Indiquez votre adresse email. Nous vous enverrons un lien sécurisé valable 30 minutes.'
        : 'Choisissez un nouveau mot de passe d’au moins 8 caractères.'

  const submitLabel = submitting
    ? mode === 'forgot' ? 'Envoi en cours…' : 'Veuillez patienter…'
    : mode === 'login'
      ? isInvitation ? 'Me connecter et rejoindre' : 'Se connecter'
      : mode === 'register'
        ? isInvitation ? 'Créer mon compte et rejoindre' : 'Créer mon compte'
        : mode === 'forgot'
          ? 'Recevoir le lien'
          : 'Réinitialiser le mot de passe'

  return (
    <main
      className={`auth-page login-redesign ${isPublicSchool ? 'login-school' : 'login-platform'} ${isInvitation ? 'login-invitation' : ''} ${mode === 'register' ? 'auth-register-mode' : 'auth-login-mode'}`}
      style={activeBrand ? {
        '--blue': activeBrand.primary_color,
        '--green': activeBrand.secondary_color,
        '--button-end': `color-mix(in srgb, ${activeBrand.primary_color} 80%, white)`,
      } as CSSProperties : undefined}
    >
      <section className="auth-panel auth-copy-panel">
        <a className="auth-logo" href={schoolKey ? '/school/' + encodeURIComponent(schoolKey) : '/'}>
          {isPublicSchool
            ? <SchoolLogo logoUrl={activeBrand?.logo_url} alt={activeBrand?.name || 'École'} className="platform-brand-logo" />
            : <BrandLogo className="platform-brand-logo" />}
          <span>
            {activeBrand?.name || (isPublicSchool ? 'Votre école' : 'Académie')}
            {!isPublicSchool && <> <strong>SaaS</strong></>}
          </span>
        </a>
        <div className="auth-visual-copy">
          {isInvitation ? <>
            <span className="auth-kicker">Invitation équipe</span>
            <h1>Vous rejoignez une école déjà créée.</h1>
            <p>
              {invitation
                ? `${invitation.organization_name} vous invite comme ${invitationRoleLabels[invitation.role].toLowerCase()}. Créez simplement votre compte pour accéder à votre espace.`
                : 'Créez simplement votre compte pour rejoindre l’équipe de cette école.'}
            </p>
          </> : isPublicSchool ? <>
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
          <span className="auth-visual-caption"><Check size={15} /> {isInvitation ? 'Aucune nouvelle école ne sera créée' : 'Un espace pensé pour apprendre et transmettre'}</span>
        </div>
      </section>

      <section className="auth-panel auth-form-panel">
        <form className="auth-card" onSubmit={submit}>
          <span className="auth-form-kicker">{isInvitation ? 'Invitation · ' + (invitation ? invitationRoleLabels[invitation.role] : 'Équipe') : isPublicSchool ? activeBrand?.name || 'Votre école' : 'Académie des Créatifs'}</span>
          <h2>{heading}</h2>
          <p>{invitationLoading ? 'Chargement de votre invitation…' : intro}</p>

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
                readOnly={Boolean(invitation && (mode === 'register' || mode === 'login'))}
                aria-readonly={Boolean(invitation && (mode === 'register' || mode === 'login'))}
                autoComplete="email"
                placeholder="vous@ecole.com"
              />
              {invitation && (mode === 'register' || mode === 'login') && <small className="auth-invitation-email-note">Adresse imposée par l’invitation.</small>}
            </label>
          )}

          {(mode === 'login' || mode === 'register' || mode === 'reset') && (
            <label>
              <span className="auth-password-label-row">
                <span>{mode === 'reset' ? 'Nouveau mot de passe' : 'Mot de passe'}</span>
                {mode === 'login' && (
                  <button
                    className="auth-forgot-inline"
                    type="button"
                    onClick={() => switchMode('forgot')}
                  >
                    Mot de passe oublié ?
                  </button>
                )}
              </span>
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

          {error && <div className="form-error">{error}</div>}
          {success && <div className="form-success">{success}</div>}

          <button className="primary-button full auth-submit" disabled={submitting || invitationLoading}>
            {submitLabel}
            {!submitting && <ArrowRight size={17} />}
          </button>

          {(mode === 'login' || mode === 'register') && <>
            <div className="auth-divider"><span>ou</span></div>
            <GoogleAuthButton
              mode={mode}
              disabled={submitting || invitationLoading}
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
                ? isInvitation
                  ? <>Pas encore de compte ? <span className="auth-switch-accent">Créer mon compte</span></>
                  : isPublicSchool
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
