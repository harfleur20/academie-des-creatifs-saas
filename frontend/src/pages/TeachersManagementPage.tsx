import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Copy, MailPlus, RefreshCw, UserRound, Users } from 'lucide-react'
import { useTenant } from '../app/TenantContext'
import { InvitationLink } from '../components/InvitationLink'
import { ApiError, cancelInvitation, createInvitation, listInvitations, listMembers, renewInvitation, type Invitation, type Member } from '../lib/api'

export function TeachersManagementPage() {
  const { activeOrganization } = useTenant()
  const [members, setMembers] = useState<Member[]>([])
  const [invites, setInvites] = useState<Invitation[]>([])
  const [tokens, setTokens] = useState<Record<number, string>>({})
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [working, setWorking] = useState(false)

  async function load() {
    const [nextMembers, nextInvites] = await Promise.all([listMembers(), listInvitations()])
    setMembers(nextMembers)
    setInvites(nextInvites)
  }

  useEffect(() => {
    if (!activeOrganization) return
    setMembers([])
    setInvites([])
    setTokens({})
    void load().catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [activeOrganization?.id])

  const teachers = useMemo(() => members.filter((member) => member.role === 'teacher' || member.roles.some((role) => role.role === 'teacher')), [members])
  const pending = invites.filter((invitation) => invitation.role === 'teacher' && invitation.status === 'pending')

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

  return <main className="app-page">
    <header className="app-page-header"><div><span className="page-kicker">Gestion des enseignants</span><h1>Professeurs</h1><p>Invitez les professeurs dans l’école, puis affectez-les aux sessions.</p></div><button className="secondary-button compact-action" type="button" onClick={() => void load()}><RefreshCw size={15} /> Actualiser</button></header>
    {error && <div className="form-error">{error}</div>}
    {message && <div className="form-success">{message}</div>}

    <section className="app-card teacher-invite-card"><div><span className="section-label">Nouvel enseignant</span><h2>Inviter un professeur</h2></div><form onSubmit={(event) => void invite(event)}><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="professeur@ecole.com" required /><button className="primary-button" disabled={working}><MailPlus size={15} />{working ? 'Invitation…' : 'Inviter'}</button></form></section>

    <section className="teacher-admin-grid">{teachers.map((teacher) => <article className="app-card teacher-admin-card" key={teacher.id}><span className="roster-avatar"><UserRound size={16} /></span><div><h3>{teacher.user.full_name}</h3><p>{teacher.user.email}</p><small>{teacher.status}</small></div></article>)}{teachers.length === 0 && <div className="app-card formation-empty"><Users size={26} /><strong>Aucun professeur</strong><p>Invitez votre premier enseignant.</p></div>}</section>

    {pending.length > 0 && <section className="app-card"><div className="table-heading"><div><span className="section-label">Invitations</span><h2>En attente</h2></div></div><div className="invitation-list">{pending.map((invitation) => <div className="invitation-row teacher-invitation-row" key={invitation.id}><div><strong>{invitation.email}</strong><small>Expire le {new Date(invitation.expires_at).toLocaleDateString('fr-FR')}</small>{tokens[invitation.id] && <InvitationLink token={tokens[invitation.id]} />}</div><div className="teacher-invitation-actions"><button className="secondary-button" type="button" disabled={working} onClick={() => void renew(invitation)}><Copy size={15} /> Nouveau lien à copier</button><button className="text-danger-button" type="button" disabled={working} onClick={() => void cancel(invitation)}>Annuler</button></div></div>)}</div></section>}
  </main>
}
