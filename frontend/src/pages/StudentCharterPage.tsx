import { useEffect, useState, type FormEvent } from 'react'
import { ArrowRight, Check } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import { SchoolLogo } from '../brand/SchoolLogo'
import {
  acceptSchoolCharter,
  getSchoolCharter,
  type SchoolCharter,
} from '../onboarding/workspaceOnboardingApi'

export function StudentCharterPage() {
  const navigate = useNavigate()
  const { activeOrganization, schoolBranding } = useTenant()
  const [charter, setCharter] = useState<SchoolCharter | null>(null)
  const [accepted, setAccepted] = useState(false)
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    getSchoolCharter('student')
      .then((next) => {
        if (!active) return
        if (!next.is_enabled || next.accepted_current_version) {
          navigate('/app/student', { replace: true })
          return
        }
        setCharter(next)
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : 'Impossible de charger la charte.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [activeOrganization?.id, navigate])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!accepted) return
    setWorking(true)
    setError('')
    try {
      await acceptSchoolCharter('student')
      navigate('/app/student', { replace: true })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Validation impossible.')
    } finally {
      setWorking(false)
    }
  }

  if (loading) return <div className="app-loading">Préparation de votre espace étudiant…</div>

  const schoolName = schoolBranding?.school_name || activeOrganization?.name || 'Votre école'
  const schoolLogo = schoolBranding?.logo_url ?? activeOrganization?.logo_url

  return (
    <main className="student-charter-page">
      <section className="student-charter-card">
        <div className="student-charter-brand">
          <SchoolLogo
            logoUrl={schoolLogo}
            alt={schoolName}
            className="student-charter-brand__logo"
          />
          <div>
            <strong>{schoolName}</strong>
            <small>Espace étudiant</small>
          </div>
        </div>
        <span className="page-kicker">Bienvenue dans {schoolName}</span>
        <h1>{charter?.title || 'Charte de l’étudiant'}</h1>
        <p>Avant d’accéder à vos cours, prenez connaissance des règles de votre école.</p>

        {error && <div className="form-error">{error}</div>}
        {charter && <div className="charter-scroll-box student-charter-content">{charter.content}</div>}

        <form onSubmit={submit}>
          <label className="charter-accept-row">
            <input type="checkbox" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} />
            <span><strong>J’ai lu et j’accepte cette charte.</strong><small>Version {charter?.version}. La date de votre validation sera conservée.</small></span>
          </label>
          <button className="primary-button full" disabled={!accepted || working}>
            {working ? 'Validation…' : 'Valider et accéder à mon espace'}
            {!working && <ArrowRight size={17} />}
          </button>
        </form>

        <div className="student-charter-foot"><Check size={14} /> Cette validation est liée à votre compte et à cette école.</div>
      </section>
    </main>
  )
}
