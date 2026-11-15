import { useEffect, useLayoutEffect, useState, type CSSProperties, type FormEvent } from 'react'
import { BrandWordmark } from '../brand/BrandWordmark'
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
  listPlans,
  resolveHostBranding,
  setStoredOrganizationId,
  type HostBranding,
  type InvitationPreview,
  type Plan,
} from '../lib/api'
import {
  applySchoolLoginBranding,
  cacheSchoolLoginBranding,
  readSchoolLoginBranding,
  toSchoolLoginBranding,
} from '../lib/schoolLoginBranding'
import { planChoiceFromSearch, savePlanChoice } from '../lib/planChoice'
import { formatMoney, monthlyEquivalent } from '../lib/planFeatures'
import { rememberPlatformAuthOrigin, rememberSchoolAuthOrigin } from '../lib/authOrigin'

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
  const cachedSchoolBrand = schoolKey ? readSchoolLoginBranding(schoolKey) : null
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
  const [hostBrand, setHostBrand] = useState<(HostBranding & { favicon_url?: string | null }) | null>(() => cachedSchoolBrand)
  const [schoolBrandLoading, setSchoolBrandLoading] = useState(Boolean(schoolKey && !cachedSchoolBrand))
  const [invitation, setInvitation] = useState<InvitationPreview | null>(null)
  const [invitationLoading, setInvitationLoading] = useState(Boolean(invitationToken))
  // The plan clicked on the landing page: kept for after signup, and reminded here.
  const planChoice = schoolKey || invitationToken ? null : planChoiceFromSearch(location.search)
  const [plans, setPlans] = useState<Plan[]>([])
  useEffect(() => {
    if (!planChoice) return
    savePlanChoice(planChoice)
    let active = true
    listPlans().then((items) => { if (active) setPlans(items) }).catch(() => undefined)
    return () => { active = false }
    // The choice only changes with the address.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search])
  const chosenPlan = planChoice ? plans.find((item) => item.code === planChoice.plan) ?? null : null
  const trialPlan = plans.find((item) => item.code === 'pro') ?? plans.find((item) => item.trial_days > 0) ?? null

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
      let active = true
      setSchoolBrandLoading(!cachedSchoolBrand)
      getPublicSchoolIdentity(schoolKey)
        .then((school) => {
          if (!active) return
          const branding = toSchoolLoginBranding(school)
          cacheSchoolLoginBranding(schoolKey, branding)
          if (school.slug !== schoolKey) cacheSchoolLoginBranding(school.slug, branding)
          setHostBrand(branding)
        })
        .catch(() => {
          if (active && !cachedSchoolBrand) setHostBrand(null)
        })
        .finally(() => { if (active) setSchoolBrandLoading(false) })
      return () => { active = false }
    }
    if (invitation) return
    const hostname = window.location.hostname
    if (hostname === 'localhost' || hostname === '127.0.0.1') return
    resolveHostBranding(hostname).then(setHostBrand).catch(() => setHostBrand(null))
  }, [schoolKey, invitation?.organization_id])

  useLayoutEffect(() => {
    if (!schoolKey) return
    if (hostBrand) {
      applySchoolLoginBranding(hostBrand)
      return
    }
    document.title = 'Inscription à l’école'
    document.querySelector<HTMLLinkElement>("link[rel~='icon']")?.remove()
  }, [schoolKey, hostBrand])

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
    rememberSchoolAuthOrigin(result.organization.slug)
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
        rememberLoginOrigin()
        if (await finishInvitationFlow(email)) return
        navigate(returnPath || '/app', { replace: true })
        return
      }

      if (mode === 'register') {
        await signUp(fullName, email, password)
        rememberLoginOrigin()
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
      rememberLoginOrigin()
      if (invitation) {
        // Google authentication may resolve to a different address than the prefilled one.
        // The invitation endpoint performs the final identity check server-side.
        const result = await acceptOrganizationInvitation(invitationToken || '')
        setStoredOrganizationId(result.organization.id)
        rememberSchoolAuthOrigin(result.organization.slug)
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

  function rememberLoginOrigin() {
    const schoolSlug = hostBrand?.slug || schoolKey
    if (schoolSlug) rememberSchoolAuthOrigin(schoolSlug)
    else rememberPlatformAuthOrigin()
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
  const showSchoolName = activeBrand?.auth_show_school_name !== false
  const schoolAuthBackground = activeBrand?.auth_background_image_url
  const authPageStyle: CSSProperties | undefined = activeBrand ? {
    '--blue': activeBrand.primary_color,
    '--green': activeBrand.secondary_color,
    '--button-end': `color-mix(in srgb, ${activeBrand.primary_color} 80%, white)`,
    ...(schoolAuthBackground ? {
      '--school-auth-background': `url("${schoolAuthBackground.replaceAll('"', '%22')}")`,
    } : {}),
  } as CSSProperties : undefined
  const heading = mode === 'login'
    ? isInvitation ? 'Connectez-vous pour rejoindre l’équipe.' : 'Heureux de vous revoir.'
    : mode === 'register'
      ? isInvitation
        ? `Rejoignez ${invitation?.organization_name || 'votre école'}.`
        : 'Commençons ensemble.'
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
        ? isInvitation
          ? 'Créer mon compte et rejoindre'
          : 'Créer mon compte'
        : mode === 'forgot'
          ? 'Recevoir le lien'
          : 'Réinitialiser le mot de passe'

  if (schoolKey && !hostBrand) {
    return (
      <main className="app-loading" aria-live="polite" aria-busy={schoolBrandLoading}>
        {schoolBrandLoading ? 'Chargement du site de l’école…' : 'Impossible de charger l’identité de cette école.'}
      </main>
    )
  }

  return (
    <main
      className={`auth-page login-redesign ${isPublicSchool ? 'login-school' : 'login-platform'} ${isInvitation ? 'login-invitation' : ''} ${mode === 'register' ? 'auth-register-mode' : 'auth-login-mode'}`}
      style={authPageStyle}
    >
      <section className="auth-panel auth-copy-panel">
        <a className="auth-logo" href={schoolKey ? '/school/' + encodeURIComponent(schoolKey) : '/'}>
          {isPublicSchool ? <>
            <SchoolLogo logoUrl={activeBrand?.logo_url} alt={activeBrand?.name || 'École'} className="platform-brand-logo" />
            {showSchoolName && <span className="auth-logo__name">{activeBrand?.name || 'Votre école'}</span>}
          </> : <BrandWordmark tone="light" className="auth-logo__wordmark" />}
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

          {chosenPlan && planChoice && !isPublicSchool && (
            <div className="auth-plan-choice">
              <span>Forfait choisi</span>
              <strong>
                {chosenPlan.monthly_price_cents === 0
                  ? `${chosenPlan.name} · gratuit`
                  : `${chosenPlan.name} · ${formatMoney(monthlyEquivalent(chosenPlan, planChoice.interval === 'annual') ?? 0, chosenPlan.currency)} / mois${planChoice.interval === 'annual' ? ' en annuel' : ''}`}
              </strong>
              {trialPlan && trialPlan.trial_days > 0 && (
                <small>
                  {chosenPlan.code === trialPlan.code
                    ? `Vous commencez par ${trialPlan.trial_days} jours d’essai gratuit, sans moyen de paiement.`
                    : chosenPlan.monthly_price_cents === 0
                      ? `Vous commencez par ${trialPlan.trial_days} jours d’essai ${trialPlan.name}, puis votre école continue gratuitement.`
                      : `Vous commencez par ${trialPlan.trial_days} jours d’essai ${trialPlan.name}, gratuits : vous payez ${chosenPlan.name} quand vous voulez.`}
                </small>
              )}
            </div>
          )}

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
