import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { BookOpen, BriefcaseBusiness, CalendarDays, Copy, Eye, FileText, Globe2, Link2, MailPlus, MapPin, PauseCircle, PlayCircle, RefreshCw, UserRound, Users, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import { InvitationLink } from '../components/InvitationLink'
import { ApiError, cancelInvitation, createInvitation, getOnboardingStatus, listInvitations, listMembers, renewInvitation, updateMember, type Invitation, type Member, type OnboardingStatus } from '../lib/api'
import { getTeacherProfessionalProfileForAdmin, previewTeacherProfessionalDocument, type TeacherDocumentKind, type TeacherProfessionalProfile } from '../onboarding/workspaceOnboardingApi'
import { toast } from '../ui/toast'
import '../management-profiles.css'
import '../teacher-profile-admin.css'

const FLAG_BASE_URL = 'https://purecatamphetamine.github.io/country-flag-icons/3x2'

function flagImageUrl(code: string | null) {
  if (!code) return null
  return `${FLAG_BASE_URL}/${code.toUpperCase()}.svg`
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return 'Non renseigné'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Non renseigné' : new Intl.DateTimeFormat(activeSchoolLocale(), { dateStyle: 'long', timeStyle: 'short' }).format(date)
}

function TeacherAvatar({ teacher, large = false }: { teacher: Member; large?: boolean }) {
  const initials = teacher.user.full_name.split(' ').filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
  return <span className={`management-avatar${large ? ' management-avatar--large' : ''}`}>
    {teacher.user.avatar_url ? <img src={teacher.user.avatar_url} alt="" /> : <span>{initials || <UserRound size={16} />}</span>}
  </span>
}

export function TeachersManagementPage() {
  const { activeOrganization } = useTenant()
  const [members, setMembers] = useState<Member[]>([])
  const [invites, setInvites] = useState<Invitation[]>([])
  const [tokens, setTokens] = useState<Record<number, string>>({})
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [working, setWorking] = useState(false)
  const [setup, setSetup] = useState<OnboardingStatus | null>(null)
  const [selectedTeacher, setSelectedTeacher] = useState<Member | null>(null)
  const [teacherProfile, setTeacherProfile] = useState<TeacherProfessionalProfile | null>(null)
  const [profileLoading, setProfileLoading] = useState(false)
  const [profileError, setProfileError] = useState('')

  async function load() {
    const [nextMembers, nextInvites, setupStatus] = await Promise.all([listMembers(), listInvitations(), getOnboardingStatus()])
    setMembers(nextMembers)
    setInvites(nextInvites)
    setSetup(setupStatus)
  }

  useEffect(() => {
    if (!activeOrganization) return
    setMembers([])
    setInvites([])
    setTokens({})
    setSelectedTeacher(null)
    setTeacherProfile(null)
    void load().catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [activeOrganization?.id])

  const teachers = useMemo(() => members.filter((member) => member.role === 'teacher' || member.roles.some((role) => role.role === 'teacher')), [members])
  const pending = invites.filter((invitation) => invitation.role === 'teacher' && invitation.status === 'pending')
  const setupBlockingStep = setup?.steps.find((step) => !step.completed)
  const invitationReady = Boolean(setup?.is_complete)

  async function invite(event: FormEvent) {
    event.preventDefault()
    setWorking(true)
    setError('')
    setMessage('')
    try {
      const created = await createInvitation({ email, role: 'teacher' })
      if (created.acceptance_token) setTokens((current) => ({ ...current, [created.id]: created.acceptance_token! }))
      setEmail('')
      setMessage('Invitation créée. Copiez le lien ci-dessous ; un e-mail a aussi été préparé.')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Invitation impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function renew(invitation: Invitation) {
    setWorking(true)
    setError('')
    setMessage('')
    try {
      const renewed = await renewInvitation(invitation.id)
      if (renewed.acceptance_token) setTokens((current) => ({ ...current, [renewed.id]: renewed.acceptance_token! }))
      setMessage(`Nouveau lien créé pour ${invitation.email}. Le précédent lien n’est plus valide.`)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Renouvellement impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function cancel(invitation: Invitation) {
    setWorking(true)
    setError('')
    try {
      await cancelInvitation(invitation.id)
      setTokens((current) => { const next = { ...current }; delete next[invitation.id]; return next })
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Annulation impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function openTeacherProfile(teacher: Member) {
    setSelectedTeacher(teacher)
    setTeacherProfile(null)
    setProfileError('')
    setProfileLoading(true)
    try {
      setTeacherProfile(await getTeacherProfessionalProfileForAdmin(teacher.user.id))
    } catch (err) {
      setProfileError(err instanceof ApiError ? err.message : 'Impossible de charger la fiche enseignant.')
    } finally {
      setProfileLoading(false)
    }
  }

  async function previewDocument(kind: TeacherDocumentKind) {
    if (!teacherProfile) return
    setProfileError('')
    try {
      await previewTeacherProfessionalDocument(teacherProfile.user_id, kind)
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : 'Aperçu du document impossible.')
    }
  }

  async function toggleTeacherAccess(teacher: Member) {
    if (working) return
    const nextStatus = teacher.status === 'suspended' ? 'active' : 'suspended'
    setWorking(true)
    setError('')
    try {
      const updated = await updateMember(teacher.id, { status: nextStatus })
      setMembers((current) => current.map((member) => member.id === updated.id ? updated : member))
      setSelectedTeacher((current) => current?.id === updated.id ? updated : current)
      toast.success(nextStatus === 'suspended' ? 'Accès du professeur suspendu pour cette école.' : 'Accès du professeur rétabli.')
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Modification de l’accès impossible.'
      setError(message)
      toast.error(message)
    } finally {
      setWorking(false)
    }
  }

  function closeTeacherProfile() {
    setSelectedTeacher(null)
    setTeacherProfile(null)
    setProfileError('')
  }

  const whatsappFlag = teacherProfile ? flagImageUrl(teacherProfile.whatsapp_country) : null

  return <main className="app-page">
    <header className="app-page-header"><div><span className="page-kicker">Gestion des enseignants</span><h1>Professeurs</h1><p>Invitez les professeurs dans l’école, consultez leur fiche puis affectez-les aux sessions.</p></div><button className="secondary-button compact-action" type="button" onClick={() => void load()}><RefreshCw size={15} /> Actualiser</button></header>
    {error && <div className="form-error">{error}</div>}
    {message && <div className="form-success">{message}</div>}

    {setupBlockingStep && <section className="app-card formation-readiness"><strong>Invitations d’enseignants verrouillées</strong><p>Terminez les 7 étapes de mise en route. Il reste notamment : {setupBlockingStep.label.toLowerCase()}.</p><Link className="secondary-button compact-action" to={setupBlockingStep.path}>Configurer cette étape</Link></section>}

    <section className="app-card teacher-invite-card"><div><span className="section-label">Nouvel enseignant</span><h2>Inviter un professeur</h2></div><form onSubmit={(event) => void invite(event)}><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="professeur@ecole.com" required /><button className="primary-button" disabled={working || !invitationReady}><MailPlus size={15} />{working ? 'Invitation…' : 'Inviter'}</button></form></section>

    <section className="teacher-admin-grid">
      {teachers.map((teacher) => <article className="app-card teacher-admin-card teacher-profile-summary-card" key={teacher.id}>
        <TeacherAvatar teacher={teacher} />
        <div className="teacher-profile-summary-copy"><h3>{teacher.user.full_name}</h3><p>{teacher.user.email}</p><small className={teacher.status === 'suspended' ? 'teacher-member-status is-suspended' : 'teacher-member-status'}>{teacher.status === 'suspended' ? 'Accès suspendu' : 'Accès actif'} · Depuis le {new Intl.DateTimeFormat(activeSchoolLocale(), { dateStyle: 'medium' }).format(new Date(teacher.created_at))}</small></div>
        <button className="secondary-button compact-action teacher-profile-open-button" type="button" onClick={() => void openTeacherProfile(teacher)}><Eye size={15} /> Voir la fiche</button>
        <button className="text-danger-button teacher-access-action" type="button" disabled={working} onClick={() => void toggleTeacherAccess(teacher)}>{teacher.status === 'suspended' ? <><PlayCircle size={15} /> Rétablir</> : <><PauseCircle size={15} /> Suspendre</>}</button>
      </article>)}
      {teachers.length === 0 && <div className="app-card formation-empty"><Users size={26} /><strong>Aucun professeur</strong><p>Invitez votre premier enseignant.</p></div>}
    </section>

    {pending.length > 0 && <section className="app-card"><div className="table-heading"><div><span className="section-label">Invitations</span><h2>En attente</h2></div></div><div className="invitation-list">{pending.map((invitation) => <div className="invitation-row teacher-invitation-row" key={invitation.id}><div><strong>{invitation.email}</strong><small>Expire le {new Date(invitation.expires_at).toLocaleDateString(activeSchoolLocale())}</small>{tokens[invitation.id] && <InvitationLink token={tokens[invitation.id]} />}</div><div className="teacher-invitation-actions"><button className="secondary-button" type="button" disabled={working || !invitationReady} onClick={() => void renew(invitation)}><Copy size={15} /> Nouveau lien</button><button className="text-danger-button" type="button" disabled={working} onClick={() => void cancel(invitation)}>Annuler</button></div></div>)}</div></section>}

    {selectedTeacher && <div className="teacher-profile-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) closeTeacherProfile() }}>
      <section className="teacher-profile-modal" role="dialog" aria-modal="true" aria-label={`Fiche de ${selectedTeacher.user.full_name}`}>
        <button className="teacher-profile-close" type="button" aria-label="Fermer" onClick={closeTeacherProfile}><X size={19} /></button>

        <header className="teacher-profile-modal-header">
          <TeacherAvatar teacher={selectedTeacher} large />
          <div>
            <span className="section-label">Fiche enseignant</span>
            <h2>{teacherProfile?.full_name || selectedTeacher.user.full_name}</h2>
            <p>{teacherProfile?.email || selectedTeacher.user.email}</p>
          </div>
          <span className={`teacher-profile-completion ${selectedTeacher.status === 'suspended' ? 'is-incomplete' : 'is-complete'}`}>{selectedTeacher.status === 'suspended' ? 'Accès suspendu' : 'Accès actif'}</span>
        </header>

        <section className="teacher-profile-panel teacher-profile-registration-panel">
          <div className="teacher-profile-panel-title"><CalendarDays size={18} /><div><span>Inscription à l’école</span><strong>{formatDateTime(teacherProfile?.joined_at || selectedTeacher.created_at)}</strong></div></div>
          <div className="teacher-profile-facts">
            <div><small>Nom complet</small><strong>{teacherProfile?.full_name || selectedTeacher.user.full_name}</strong></div>
            <div><small>Email</small><strong>{teacherProfile?.email || selectedTeacher.user.email}</strong></div>
            <div><small>Téléphone</small><strong>{teacherProfile?.phone || selectedTeacher.user.phone || 'Non renseigné'}</strong></div>
            <div><small>Compte créé</small><strong>{formatDateTime(teacherProfile?.registered_at || selectedTeacher.user.created_at)}</strong></div>
            {teacherProfile?.teacher_code && <div><small>Matricule enseignant</small><strong>{teacherProfile.teacher_code}</strong></div>}
          </div>
        </section>

        {profileLoading && <div className="teacher-profile-loading">Chargement de la fiche…</div>}
        {profileError && <div className="form-error">{profileError}</div>}

        {teacherProfile && <div className="teacher-profile-content">
          <section className="teacher-profile-panel">
            <div className="teacher-profile-panel-title"><BriefcaseBusiness size={18} /><div><span>Expertise</span><strong>{teacherProfile.professional_title || 'Non renseigné'}</strong></div></div>
            <div className="teacher-profile-facts">
              <div><small>Expérience</small><strong>{teacherProfile.experience_years} an(s)</strong></div>
              <div><small>Domaines</small><strong>{teacherProfile.activity_domains.join(', ') || 'Non renseignés'}</strong></div>
              <div><small>Compétences</small><strong>{teacherProfile.skills.join(', ') || 'Non renseignées'}</strong></div>
              <div><small>Langues</small><strong>{teacherProfile.languages.join(', ') || 'Non renseignées'}</strong></div>
            </div>
            <div className="teacher-profile-bio"><small>Bio professionnelle</small><p>{teacherProfile.bio || 'Non renseignée'}</p></div>
          </section>

          <section className="teacher-profile-panel">
            <div className="teacher-profile-panel-title"><MapPin size={18} /><div><span>Coordonnées</span><strong>{[teacherProfile.city, teacherProfile.country].filter(Boolean).join(', ') || 'Localisation non renseignée'}</strong></div></div>
            <div className="teacher-profile-contact-row">
              {whatsappFlag && <img src={whatsappFlag} alt="" aria-hidden="true" />}
              <div><small>WhatsApp</small><strong>{teacherProfile.whatsapp_phone || 'Non renseigné'}</strong></div>
            </div>
          </section>

          <section className="teacher-profile-panel teacher-profile-assignment-panel">
            <div className="teacher-profile-panel-title"><BookOpen size={18} /><div><span>Enseignement</span><strong>Formations et sessions affectées</strong></div></div>
            {teacherProfile.assigned_sessions.length ? <div className="teacher-assignment-list">{teacherProfile.assigned_sessions.map((assignment, index) => <article key={`${assignment.formation_title}-${assignment.session_label}-${index}`}>
              <div><strong>{assignment.formation_title}</strong><small>{assignment.session_label} · {new Intl.DateTimeFormat(activeSchoolLocale(), { dateStyle: 'medium' }).format(new Date(`${assignment.start_date}T00:00:00`))} – {new Intl.DateTimeFormat(activeSchoolLocale(), { dateStyle: 'medium' }).format(new Date(`${assignment.end_date}T00:00:00`))}</small><small>{assignment.course_titles.length ? `Cours : ${assignment.course_titles.join(', ')}` : 'Aucun cours attribué individuellement'}</small></div><span>{assignment.role}</span>
            </article>)}</div> : <p className="teacher-assignment-empty">Aucune session ne lui est affectée pour le moment.</p>}
          </section>

          <section className="teacher-profile-panel teacher-profile-documents-panel">
            <div className="teacher-profile-panel-title"><FileText size={18} /><div><span>Documents & liens</span><strong>Aperçus sécurisés</strong></div></div>
            <div className="teacher-profile-document-buttons">
              {teacherProfile.portfolio_file_name && <button type="button" className="secondary-button compact-action" onClick={() => void previewDocument('portfolio')}><Eye size={15} /> Portfolio PDF</button>}
              {teacherProfile.cv_file_name && <button type="button" className="secondary-button compact-action" onClick={() => void previewDocument('cv')}><Eye size={15} /> CV PDF</button>}
              {teacherProfile.portfolio_url && <a className="secondary-button compact-action" href={teacherProfile.portfolio_url} target="_blank" rel="noopener noreferrer"><Globe2 size={15} /> Portfolio en ligne</a>}
            </div>
            <div className="teacher-profile-links">
              {teacherProfile.linkedin_url && <a href={teacherProfile.linkedin_url} target="_blank" rel="noopener noreferrer"><Link2 size={14} /> LinkedIn</a>}
              {teacherProfile.behance_url && <a href={teacherProfile.behance_url} target="_blank" rel="noopener noreferrer"><Link2 size={14} /> Behance</a>}
              {teacherProfile.github_url && <a href={teacherProfile.github_url} target="_blank" rel="noopener noreferrer"><Link2 size={14} /> GitHub</a>}
              {teacherProfile.website_url && <a href={teacherProfile.website_url} target="_blank" rel="noopener noreferrer"><Link2 size={14} /> Site personnel</a>}
            </div>
          </section>
        </div>}
        <footer className="teacher-profile-modal-actions">
          {teacherProfile && <span className={`teacher-profile-completion ${teacherProfile.is_complete ? 'is-complete' : 'is-incomplete'}`}>{teacherProfile.is_complete ? 'Fiche professionnelle complète' : 'Fiche professionnelle à compléter'}</span>}
          <button className={selectedTeacher.status === 'suspended' ? 'primary-button' : 'text-danger-button'} type="button" disabled={working} onClick={() => void toggleTeacherAccess(selectedTeacher)}>{selectedTeacher.status === 'suspended' ? <><PlayCircle size={16} /> Rétablir l’accès à l’école</> : <><PauseCircle size={16} /> Suspendre l’accès à l’école</>}</button>
        </footer>
      </section>
    </div>}
  </main>
}
