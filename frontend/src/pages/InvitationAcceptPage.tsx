import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useState, type CSSProperties } from 'react'
import { ArrowRight, CheckCircle2, Mail, ShieldCheck } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import { useAuth } from '../auth/AuthContext'
import { SchoolLogo } from '../brand/SchoolLogo'
import {
  ApiError,
  acceptOrganizationInvitation,
  getInvitationPreview,
  setStoredOrganizationId,
  type InvitationPreview,
} from '../lib/api'

const roleLabel: Record<InvitationPreview['role'], string> = {
  admin: 'Administrateur',
  manager: 'Manager',
  teacher: 'Enseignant',
}

export function InvitationAcceptPage() {
  const { token = '' } = useParams()
  const navigate = useNavigate()
  const { user, loading: authLoading, signOut } = useAuth()
  const { refreshOrganizations } = useTenant()
  const [preview, setPreview] = useState<InvitationPreview | null>(null)
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)
  const [accepted, setAccepted] = useState(false)

  useEffect(() => {
    if (!token) return
    getInvitationPreview(token)
      .then(setPreview)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Invitation invalide.'),
      )
  }, [token])

  async function accept() {
    if (!token) return
    setWorking(true)
    setError('')
    try {
      const result = await acceptOrganizationInvitation(token)
      setStoredOrganizationId(result.organization.id)
      setAccepted(true)
      const destination = result.membership.role === 'teacher'
        ? '/app/teacher'
        : '/app/manage'
      try {
        await refreshOrganizations()
      } catch {
        window.location.assign(destination)
        return
      }
      window.setTimeout(() => {
        navigate(destination, { replace: true })
      }, 700)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Acceptation impossible.')
    } finally {
      setWorking(false)
    }
  }

  const style = preview
    ? ({
        '--blue': preview.primary_color,
        '--green': preview.secondary_color,
      } as CSSProperties)
    : undefined
  const returnPath = '/invite/' + token
  const loginPath = '/login?return=' + encodeURIComponent(returnPath)
  const accountMatchesInvitation = Boolean(
    user && preview && user.email.trim().toLowerCase() === preview.email.trim().toLowerCase(),
  )

  return (
    <main className="invitation-page" style={style}>
      <section className="invitation-card">
        <SchoolLogo
          logoUrl={preview?.logo_url}
          alt={preview?.organization_name || 'École'}
          className="invitation-school-logo"
        />

        {accepted ? (
          <>
            <CheckCircle2 className="invitation-success-icon" size={34} />
            <span className="section-label">Invitation acceptée</span>
            <h1>Bienvenue chez {preview?.organization_name}</h1>
            <p>Votre espace est en cours d’ouverture.</p>
          </>
        ) : (
          <>
            <span className="section-label">Invitation</span>
            <h1>
              {preview
                ? 'Rejoindre ' + preview.organization_name
                : 'Invitation à rejoindre une école'}
            </h1>
            {preview && (
              <div className="invitation-summary">
                <span><Mail size={14} /> {preview.email}</span>
                <span><ShieldCheck size={14} /> {roleLabel[preview.role]}</span>
                <small>
                  Valable jusqu’au{' '}
                  {new Date(preview.expires_at).toLocaleDateString(activeSchoolLocale())}
                </small>
              </div>
            )}

            {error && <div className="form-error">{error}</div>}

            {authLoading ? (
              <p>Vérification de votre session…</p>
            ) : user && preview && !accountMatchesInvitation ? (
              <div className="invitation-auth-actions">
                <p>
                  Cette invitation est destinée à <strong>{preview.email}</strong>.
                  Vous êtes connecté avec <strong>{user.email}</strong>.
                </p>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => {
                    signOut()
                    navigate(loginPath)
                  }}
                >
                  Changer de compte
                </button>
              </div>
            ) : user ? (
              <>
                <p>
                  Vous êtes connecté avec <strong>{user.email}</strong>.
                </p>
                <button
                  className="primary-button full"
                  type="button"
                  disabled={working || !preview}
                  onClick={() => void accept()}
                >
                  {working ? 'Acceptation…' : 'Accepter l’invitation'}
                  {!working && <ArrowRight size={16} />}
                </button>
              </>
            ) : (
              <div className="invitation-auth-actions">
                <p>Connectez-vous ou créez un compte avec l’adresse invitée.</p>
                <Link
                  className="primary-button"
                  to={loginPath}
                >
                  Se connecter
                </Link>
                <Link
                  className="secondary-button"
                  to={
                    '/login?mode=register&return=' +
                    encodeURIComponent(returnPath)
                  }
                >
                  Créer mon compte
                </Link>
              </div>
            )}
          </>
        )}

        <footer>
          Powered by <strong>Académie des Créatifs</strong>
        </footer>
      </section>
    </main>
  )
}
