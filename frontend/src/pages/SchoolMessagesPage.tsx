import { MessageCircle, Plus, Send, ShieldCheck, UserRound, X } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useLocation } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import { useAuth } from '../auth/AuthContext'
import {
  createMessageThread,
  getMessageThread,
  listMessageRecipients,
  listMessageThreads,
  sendSchoolMessage,
  subscribeSchoolMessages,
  type SchoolMessageRecipient,
  type SchoolMessageThread,
  type SchoolMessageThreadDetail,
} from '../lib/api'
import './school-messages.css'

const institutionRoles = new Set(['owner', 'admin', 'manager'])
const isInstitutionRole = (role?: string | null) => Boolean(role && institutionRoles.has(role))
const roleLabel = (role: string) => isInstitutionRole(role)
  ? 'Administration'
  : role === 'teacher'
    ? 'Enseignant'
    : 'Étudiant'

const messageDate = (value: string | null) => value
  ? new Date(value).toLocaleString('fr-FR', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    })
  : ''

function initials(value?: string | null) {
  return (value || '?')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || '?'
}

function MessageAvatar({
  person,
  institutionLogo,
  className = '',
}: {
  person?: SchoolMessageRecipient | null
  institutionLogo?: string | null
  className?: string
}) {
  const institution = isInstitutionRole(person?.role)
  const avatarUrl = person?.avatar_url || (institution ? institutionLogo : null)
  return (
    <span className={`school-message-avatar${institution ? ' is-institution' : ''}${className ? ` ${className}` : ''}`}>
      {avatarUrl ? (
        <img src={avatarUrl} alt="" />
      ) : institution ? (
        <ShieldCheck size={19} aria-hidden="true" />
      ) : person ? (
        <span>{initials(person.full_name)}</span>
      ) : (
        <UserRound size={18} aria-hidden="true" />
      )}
    </span>
  )
}

export function SchoolMessagesPage() {
  const location = useLocation()
  const requestedRecipient = Number(new URLSearchParams(location.search).get('recipient'))
  const { activeOrganization } = useTenant()
  const { user } = useAuth()
  const [threads, setThreads] = useState<SchoolMessageThread[]>([])
  const [recipients, setRecipients] = useState<SchoolMessageRecipient[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<SchoolMessageThreadDetail | null>(null)
  const [composing, setComposing] = useState(false)
  const [recipientIds, setRecipientIds] = useState<number[]>([])
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [reply, setReply] = useState('')
  const [working, setWorking] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let active = true
    setThreads([])
    setRecipients([])
    setSelectedId(null)
    setDetail(null)
    setComposing(false)
    setRecipientIds([])
    setLoading(true)
    setError('')
    Promise.all([listMessageThreads(), listMessageRecipients()])
      .then(([items, people]) => {
        if (!active) return
        setThreads(items)
        setRecipients(people)
        setSelectedId(items[0]?.id ?? null)
        if (people.some((person) => person.id === requestedRecipient)) {
          setRecipientIds([requestedRecipient])
          setComposing(true)
        }
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : 'Chargement impossible.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [activeOrganization?.id, requestedRecipient])

  useEffect(() => {
    if (selectedId === null) {
      setDetail(null)
      return
    }
    let active = true
    getMessageThread(selectedId)
      .then((value) => {
        if (active) {
          setDetail(value)
          setThreads((items) => items.map((item) => (
            item.id === selectedId ? { ...item, unread_count: 0 } : item
          )))
        }
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : 'Conversation inaccessible.')
      })
    return () => { active = false }
  }, [selectedId, activeOrganization?.id])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [detail?.messages.length])

  useEffect(() => {
    if (!activeOrganization) return
    let active = true
    const unsubscribe = subscribeSchoolMessages((event) => {
      if (!active || event.type !== 'messages.changed') return
      void listMessageThreads()
        .then((items) => { if (active) setThreads(items) })
        .catch(() => {})
      if (selectedId !== null) {
        void getMessageThread(selectedId)
          .then((value) => { if (active) setDetail(value) })
          .catch(() => {})
      }
    })
    const timer = window.setInterval(() => {
      listMessageThreads()
        .then((items) => { if (active) setThreads(items) })
        .catch(() => {})
      if (selectedId !== null) {
        getMessageThread(selectedId)
          .then((value) => { if (active) setDetail(value) })
          .catch(() => {})
      }
    }, 15000)
    return () => {
      active = false
      unsubscribe()
      window.clearInterval(timer)
    }
  }, [activeOrganization?.id, selectedId])

  async function create(event: FormEvent) {
    event.preventDefault()
    if (recipientIds.length === 0 || !body.trim()) return
    setWorking(true)
    setError('')
    try {
      const created = await createMessageThread({
        participant_ids: recipientIds,
        subject,
        body,
      })
      setDetail(created)
      setSelectedId(created.id)
      setComposing(false)
      setRecipientIds([])
      setSubject('')
      setBody('')
      setThreads(await listMessageThreads())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Envoi impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function answer(event: FormEvent) {
    event.preventDefault()
    if (!detail || !reply.trim()) return
    setWorking(true)
    setError('')
    try {
      await sendSchoolMessage(detail.id, reply)
      setReply('')
      setDetail(await getMessageThread(detail.id))
      setThreads(await listMessageThreads())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Envoi impossible.')
    } finally {
      setWorking(false)
    }
  }

  const institutionLogo = activeOrganization?.logo_url
  const selectedOthers = detail?.participants.filter((person) => person.id !== user?.id) ?? []
  const selectedPrimary = selectedOthers[0] ?? null

  return (
    <main className="app-page school-messages-page">
      <header className="app-page-header school-messages-page__header">
        <div>
          <span className="page-kicker">Échanges</span>
          <h1>Messagerie</h1>
          <p>Échangez avec les membres autorisés de votre école.</p>
        </div>
        <button
          className="primary-button school-messages-new-button"
          type="button"
          onClick={() => setComposing(true)}
        >
          <Plus size={17} /> Nouveau message
        </button>
      </header>

      {error && <p className="form-error" role="alert">{error}</p>}

      <div className="school-messages-layout">
        <aside className="school-messages-threads" aria-label="Conversations">
          {loading && <p>Chargement…</p>}
          {!loading && threads.length === 0 && <p>Aucune conversation pour le moment.</p>}
          {threads.map((thread) => {
            const others = thread.participants.filter((person) => person.id !== user?.id)
            const primary = others[0] ?? null
            const participantLine = others
              .map((person) => `${person.full_name} · ${roleLabel(person.role)}`)
              .join(', ')
            return (
              <button
                type="button"
                key={thread.id}
                className={`school-messages-thread${selectedId === thread.id && !composing ? ' is-selected' : ''}`}
                onClick={() => {
                  setComposing(false)
                  setSelectedId(thread.id)
                }}
              >
                <MessageAvatar person={primary} institutionLogo={institutionLogo} />
                <span className="school-messages-thread__body">
                  <strong>{thread.subject || primary?.full_name || 'Conversation'}</strong>
                  <small className="school-messages-thread__participant">{participantLine}</small>
                  <small className="school-messages-thread__preview">{thread.last_message?.body || 'Conversation ouverte'}</small>
                </span>
                <span className="school-messages-thread__meta">
                  <time>{messageDate(thread.last_message_at)}</time>
                  {thread.unread_count > 0 && <i>{thread.unread_count}</i>}
                </span>
              </button>
            )
          })}
        </aside>

        <section className="school-messages-detail">
          {detail && !composing ? (
            <>
              <header className="school-messages-detail__header">
                <MessageAvatar
                  person={selectedPrimary}
                  institutionLogo={institutionLogo}
                  className="school-message-avatar--header"
                />
                <div className="school-messages-detail__identity">
                  <h2>{detail.subject || selectedPrimary?.full_name || 'Conversation'}</h2>
                  <p>
                    {selectedOthers.map((person) => (
                      `${person.full_name} · ${roleLabel(person.role)}`
                    )).join(', ')}
                  </p>
                </div>
              </header>

              <div className="school-messages-feed">
                {detail.messages.map((message) => {
                  const isMine = message.sender_user_id === user?.id
                  const sender = detail.participants.find(
                    (person) => person.id === message.sender_user_id,
                  ) ?? null
                  const institution = !isMine && isInstitutionRole(sender?.role)
                  return (
                    <div
                      key={message.id}
                      className={`school-message-row${isMine ? ' is-mine' : ''}${institution ? ' is-institution' : ''}`}
                    >
                      {!isMine && (
                        <MessageAvatar
                          person={sender}
                          institutionLogo={institutionLogo}
                          className="school-message-avatar--bubble"
                        />
                      )}
                      <article className="school-message-bubble">
                        <span className="school-message-bubble__meta">
                          <strong>{isMine ? 'Vous' : message.sender_name}</strong>
                          {!isMine && sender && (
                            <small className="school-message-role">{roleLabel(sender.role)}</small>
                          )}
                          <time>{messageDate(message.created_at)}</time>
                        </span>
                        <p>{message.body}</p>
                      </article>
                    </div>
                  )
                })}
                <div ref={messagesEndRef} />
              </div>

              <form
                className="school-messages-reply"
                onSubmit={(event) => void answer(event)}
              >
                <textarea
                  id="school-message-reply"
                  value={reply}
                  maxLength={5000}
                  onChange={(event) => setReply(event.target.value)}
                  placeholder="Écrire un message…"
                  aria-label="Répondre à la conversation"
                  required
                />
                <button
                  className="school-messages-send-button"
                  type="submit"
                  disabled={working || !reply.trim()}
                  aria-label="Envoyer le message"
                >
                  <Send size={17} />
                </button>
              </form>
            </>
          ) : (
            <div className="school-messages-placeholder">
              <MessageCircle size={34} />
              <p>Sélectionnez une conversation ou écrivez un nouveau message.</p>
            </div>
          )}
        </section>
      </div>

      {composing && (
        <div
          className="school-messages-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setComposing(false)
          }}
        >
          <div className="school-messages-modal" role="dialog" aria-modal="true" aria-labelledby="school-new-message-title">
            <header>
              <div>
                <span>Nouveau message</span>
                <h2 id="school-new-message-title">Nouvelle conversation</h2>
              </div>
              <button
                type="button"
                onClick={() => setComposing(false)}
                aria-label="Fermer"
              >
                <X size={19} />
              </button>
            </header>
            <form onSubmit={(event) => void create(event)}>
              <fieldset>
                <legend>Destinataires <small>{recipientIds.length}/8</small></legend>
                {recipients.length === 0 && <p>Aucun destinataire disponible.</p>}
                <div className="school-messages-recipient-grid">
                  {recipients.map((person) => {
                    const selected = recipientIds.includes(person.id)
                    return (
                      <label key={person.id} className={selected ? 'is-selected' : ''}>
                        <input
                          type="checkbox"
                          checked={selected}
                          disabled={!selected && recipientIds.length >= 8}
                          onChange={(event) => setRecipientIds((ids) => (
                            event.target.checked
                              ? [...ids, person.id]
                              : ids.filter((id) => id !== person.id)
                          ))}
                        />
                        <MessageAvatar person={person} institutionLogo={institutionLogo} />
                        <span>
                          <strong>{person.full_name}</strong>
                          <small>{roleLabel(person.role)}</small>
                        </span>
                      </label>
                    )
                  })}
                </div>
              </fieldset>

              <label>
                <span>Sujet</span>
                <input
                  value={subject}
                  maxLength={255}
                  onChange={(event) => setSubject(event.target.value)}
                  placeholder="Sujet de la conversation"
                />
              </label>
              <label>
                <span>Message</span>
                <textarea
                  value={body}
                  maxLength={5000}
                  onChange={(event) => setBody(event.target.value)}
                  placeholder="Écrivez votre message…"
                  required
                />
              </label>
              <div className="school-messages-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => setComposing(false)}
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  className="primary-button"
                  disabled={working || recipientIds.length === 0 || !body.trim()}
                >
                  <Send size={16} /> Envoyer
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  )
}
