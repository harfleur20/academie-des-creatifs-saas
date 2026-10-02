import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  MailPlus,
  MoreHorizontal,
  RefreshCw,
  Shield,
  UserRoundCheck,
  Users,
} from 'lucide-react'
import { useTenant } from '../app/TenantContext'
import {
  ApiError,
  cancelInvitation,
  createInvitation,
  listInvitations,
  listMembers,
  updateMember,
  updateMemberFunctionalRoles,
  type Invitation,
  type Member,
} from '../lib/api'

const roleLabels: Record<Member['role'], string> = {
  owner: 'Propriétaire',
  admin: 'Administrateur',
  manager: 'Manager',
  teacher: 'Professeur',
  student: 'Étudiant',
}

export function TeamPage() {
  const { activeOrganization } = useTenant()
  const [members, setMembers] = useState<Member[]>([])
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Invitation['role']>('teacher')
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function load() {
    if (!activeOrganization) return
    setLoading(true)
    setError('')
    try {
      const [memberItems, invitationItems] = await Promise.all([
        listMembers(),
        listInvitations(),
      ])
      setMembers(memberItems)
      setInvitations(invitationItems)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de charger l’équipe.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [activeOrganization?.id])

  const activeCount = useMemo(
    () => members.filter((member) => member.status === 'active').length,
    [members],
  )

  async function invite(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    setMessage('')
    try {
      await createInvitation({ email, role })
      setEmail('')
      setMessage('Invitation créée. L’envoi par email sera branché au service Brevo.')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Invitation impossible.')
    } finally {
      setSubmitting(false)
    }
  }

  function hasRole(member: Member, role: 'teacher' | 'student') {
    return member.role === role || member.roles.some((item) => item.role === role)
  }

  async function toggleFunctionalRole(
    member: Member,
    role: 'teacher' | 'student',
  ) {
    if (member.role === role) return
    const current = new Set(
      (['teacher', 'student'] as const).filter((item) => hasRole(member, item)),
    )
    if (current.has(role)) current.delete(role)
    else current.add(role)

    setError('')
    try {
      await updateMemberFunctionalRoles(member.id, [...current])
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Modification des accès impossible.')
    }
  }

  async function changeMember(
    member: Member,
    payload: { role?: Member['role']; status?: Member['status'] },
  ) {
    setError('')
    try {
      await updateMember(member.id, payload)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Modification impossible.')
    }
  }

  if (!activeOrganization) {
    return <div className="page-state">Créez d’abord une école.</div>
  }

  return (
    <main className="app-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Équipe & accès</span>
          <h1>Qui peut faire quoi dans {activeOrganization.name} ?</h1>
          <p>Invitez votre équipe et contrôlez les droits par rôle.</p>
        </div>
        <button className="secondary-button compact-action" onClick={() => void load()}>
          <RefreshCw size={16} /> Actualiser
        </button>
      </header>

      <div className="team-overview">
        <article><Users size={20} /><div><strong>{activeCount}</strong><span>Membres actifs</span></div></article>
        <article><MailPlus size={20} /><div><strong>{invitations.filter((item) => item.status === 'pending').length}</strong><span>Invitations en attente</span></div></article>
        <article><Shield size={20} /><div><strong>5</strong><span>Rôles disponibles</span></div></article>
      </div>

      <section className="app-card invite-card">
        <div>
          <span className="section-label">Ajouter quelqu’un</span>
          <h2>Inviter un membre</h2>
          <p>Invitez uniquement l’équipe administrative et les professeurs. Les étudiants arrivent par leurs achats.</p>
        </div>
        <form className="invite-form" onSubmit={invite}>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="email@exemple.com"
            required
          />
          <select value={role} onChange={(event) => setRole(event.target.value as Invitation['role'])}>
            <option value="admin">Administrateur</option>
            <option value="manager">Manager</option>
            <option value="teacher">Professeur</option>
          </select>
          <button className="primary-button" disabled={submitting}>
            <MailPlus size={17} />
            {submitting ? 'Invitation…' : 'Inviter'}
          </button>
        </form>
        {message && <div className="form-success">{message}</div>}
        {error && <div className="form-error">{error}</div>}
      </section>

      <section className="app-card">
        <div className="table-heading">
          <div>
            <span className="section-label">Membres</span>
            <h2>Équipe actuelle</h2>
          </div>
          {loading && <span className="muted-note">Mise à jour…</span>}
        </div>

        <div className="member-table">
          <div className="member-row member-header">
            <span>Membre</span><span>Rôle principal</span><span>Accès pédagogiques</span><span>Statut</span><span />
          </div>
          {members.map((member) => (
            <div className="member-row" key={member.id}>
              <div className="member-person">
                <span className="mini-avatar">
                  {member.user.full_name
                    .split(' ')
                    .slice(0, 2)
                    .map((part) => part[0]?.toUpperCase())
                    .join('')}
                </span>
                <span>
                  <strong>{member.user.full_name}</strong>
                  <small>{member.user.email}</small>
                </span>
              </div>

              <select
                value={member.role}
                onChange={(event) =>
                  void changeMember(member, {
                    role: event.target.value as Member['role'],
                  })
                }
              >
                {Object.entries(roleLabels).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>

              <div className="member-functional-roles">
                {(['teacher', 'student'] as const).map((functionalRole) => {
                  const active = hasRole(member, functionalRole)
                  const locked = member.role === functionalRole
                  return (
                    <button
                      key={functionalRole}
                      type="button"
                      className={`functional-role-toggle ${active ? 'active' : ''}`}
                      disabled={locked}
                      title={locked ? 'Ce rôle est déjà le rôle principal.' : undefined}
                      onClick={() => void toggleFunctionalRole(member, functionalRole)}
                    >
                      {functionalRole === 'teacher' ? 'Professeur' : 'Étudiant'}
                    </button>
                  )
                })}
              </div>

              <button
                className={member.status === 'active' ? 'member-status active' : 'member-status suspended'}
                onClick={() =>
                  void changeMember(member, {
                    status: member.status === 'active' ? 'suspended' : 'active',
                  })
                }
              >
                <UserRoundCheck size={15} />
                {member.status === 'active' ? 'Actif' : 'Suspendu'}
              </button>

              <button className="icon-button" title="Options"><MoreHorizontal size={18} /></button>
            </div>
          ))}
          {!loading && members.length === 0 && (
            <div className="empty-row">Aucun membre dans cette école.</div>
          )}
        </div>
      </section>

      <section className="app-card">
        <div className="table-heading">
          <div>
            <span className="section-label">Invitations</span>
            <h2>Invitations envoyées</h2>
          </div>
        </div>
        <div className="invitation-list">
          {invitations.map((invitation) => (
            <div className="invitation-row" key={invitation.id}>
              <div>
                <strong>{invitation.email}</strong>
                <small>{invitation.role} · {invitation.status}</small>
              </div>
              {invitation.status === 'pending' && (
                <button
                  className="text-danger-button"
                  onClick={async () => {
                    await cancelInvitation(invitation.id)
                    await load()
                  }}
                >
                  Annuler
                </button>
              )}
            </div>
          ))}
          {!loading && invitations.length === 0 && (
            <div className="empty-row">Aucune invitation pour le moment.</div>
          )}
        </div>
      </section>
    </main>
  )
}
