import { MessageCircle, Plus, Search, Send, UserRound, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
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

const roleLabel = (role: string) => {
  if (isInstitutionRole(role)) return 'Admin'
  if (role === 'teacher') return 'Enseignant'
  if (role === 'student') return 'Étudiant'
  return role
}

const messageDate = (value: string | null) => value
  ? new Date(value).toLocaleString('fr-FR', {
      day: 'numeric',
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
  const [selectedRecipientId, setSelectedRecipientId] = useState<number | null>(null)
  const [recipientSearch, setRecipientSearch] = useState('')
  const [recipientDropdownOpen, setRecipientDropdownOpen] = useState(false)
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [reply, setReply] = useState('')
  const [working, setWorking] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const recipientBoxRef = useRef<HTMLDivElement>(null)

  const selectedThread = useMemo(
    () => threads.find((thread) => thread.id === selectedId) ?? null,
    [threads, selectedId],
  )

  const selectedRecipient = useMemo(
    () => recipients.find((person) => person.id === selectedRecipientId) ?? null,
    [recipients, selectedRecipientId],
  )

  const personName = (person?: SchoolMessageRecipient | null) => {
    if (!person) return ''
    return isInstitutionRole(person.role)
      ? (activeOrganization?.name || person.full_name)
      : person.full_name
  }

  const personAvatar = (person?: SchoolMessageRecipient | null) => {
    if (!person) return null
    if (isInstitutionRole(person.role)) return activeOrganization?.logo_url || null
    return person.avatar_url
  }

  const filteredRecipients = useMemo(() => {
    const query = recipientSearch.trim().toLowerCase()
    if (!query) return recipients
    return recipients.filter((person) => {
      const displayName = isInstitutionRole(person.role)
        ? (activeOrganization?.name || person.full_name)
        : person.full_name
      return displayName.toLowerCase().includes(query)
        || roleLabel(person.role).toLowerCase().includes(query)
    })
  }, [recipients, recipientSearch, activeOrganization?.name])

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (recipientBoxRef.current && !recipientBoxRef.current.contains(event.target as Node)) {
        setRecipientDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    let active = true
    setThreads([])
    setRecipients([])
    setSelectedId(null)
    setDetail(null)
    setComposing(false)
    setSelectedRecipientId(null)
    setRecipientSearch('')
    setLoading(true)
    setError('')

    Promise.all([listMessageThreads(), listMessageRecipients()])
      .then(([items, people]) => {
        if (!active) return
        setThreads(items)
        setRecipients(people)
        setSelectedId(items[0]?.id ?? null)
        if (people.some((person) => person.id === requestedRecipient)) {
          setSelectedRecipientId(requestedRecipient)
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
        if (!active) return
        setDetail(value)
        setThreads((items) => items.map((item) => (
          item.id === selectedId ? { ...item, unread_count: 0 } : item
        )))
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
    const refresh = () => {
      void listMessageThreads()
        .then((items) => { if (active) setThreads(items) })
        .catch(() => {})
      if (selectedId !== null) {
        void getMessageThread(selectedId)
          .then((value) => { if (active) setDetail(value) })
          .catch(() => {})
      }
    }

    const unsubscribe = subscribeSchoolMessages((event) => {
      if (!active || event.type !== 'messages.changed') return
      refresh()
    })
    const timer = window.setInterval(refresh, 15000)

    return () => {
      active = false
      unsubscribe()
      window.clearInterval(timer)
    }
  }, [activeOrganization?.id, selectedId])

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedRecipientId || !body.trim()) return

    setWorking(true)
    setError('')
    try {
      const created = await createMessageThread({
        participant_ids: [selectedRecipientId],
        subject: subject.trim(),
        body: body.trim(),
      })
      setDetail(created)
      setSelectedId(created.id)
      setComposing(false)
      setSelectedRecipientId(null)
      setRecipientSearch('')
      setSubject('')
      setBody('')
      setThreads(await listMessageThreads())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Envoi impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function answer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!detail || !reply.trim()) return

    const nextMessage = reply.trim()
    setWorking(true)
    setError('')
    try {
      setReply('')
      await sendSchoolMessage(detail.id, nextMessage)
      setDetail(await getMessageThread(detail.id))
      setThreads(await listMessageThreads())
    } catch (cause) {
      setReply(nextMessage)
      setError(cause instanceof Error ? cause.message : 'Envoi impossible.')
    } finally {
      setWorking(false)
    }
  }

  function avatar(person: SchoolMessageRecipient | null | undefined, className: string, iconFallback = false) {
    const image = personAvatar(person)
    const institution = isInstitutionRole(person?.role)
    const name = personName(person)
    return (
      <span className={`${className}${institution ? ' is-institution' : ''}`}>
        {image ? (
          <img src={image} alt="" />
        ) : iconFallback ? (
          <UserRound size={18} />
        ) : (
          initials(name)
        )}
      </span>
    )
  }

  if (loading) {
    return <div className="app-page messages-page school-messages-page"><div className="messages-empty">Chargement…</div></div>
  }

  return (
    <main className="app-page messages-page school-messages-page">
      <div className="messages-header">
        <div>
          <h1>Messages</h1>
        </div>
        <button
          type="button"
          className="messages-new-btn"
          onClick={() => setComposing(true)}
        >
          <Plus size={16} />
          Nouveau
        </button>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}

      <div className="messages-shell">
        <aside className="messages-list" aria-label="Conversations">
          {threads.length === 0 ? (
            <div className="messages-empty">
              <MessageCircle size={28} />
              <p>Aucune conversation pour le moment.</p>
            </div>
          ) : (
            threads.map((thread) => {
              const others = thread.participants.filter((person) => person.id !== user?.id)
              const first = others[0] ?? null
              const title = thread.subject || others.map((person) => personName(person)).join(', ')
              return (
                <button
                  key={thread.id}
                  type="button"
                  className={`messages-thread${thread.id === selectedId ? ' is-active' : ''}`}
                  onClick={() => {
                    setComposing(false)
                    setSelectedId(thread.id)
                  }}
                >
                  {avatar(first, 'messages-thread__avatar', true)}
                  <span className="messages-thread__body">
                    <strong>{title}</strong>
                    <small>{thread.last_message?.body ?? 'Conversation ouverte'}</small>
                  </span>
                  <span className="messages-thread__meta">
                    {messageDate(thread.last_message_at)}
                    {thread.unread_count > 0 && <b>{thread.unread_count}</b>}
                  </span>
                </button>
              )
            })
          )}
        </aside>

        <article className="messages-detail">
          {!selectedThread || !detail ? (
            <div className="messages-empty messages-empty--detail">
              <MessageCircle size={34} />
              <p>Sélectionnez une conversation.</p>
            </div>
          ) : (
            <>
              <header className="messages-detail__header">
                {(() => {
                  const others = detail.participants.filter((person) => person.id !== user?.id)
                  const first = others[0] ?? null
                  return (
                    <>
                      {avatar(first, 'messages-detail__header-avatar', true)}
                      <div className="messages-detail__header-info">
                        <h2>{detail.subject || others.map((person) => personName(person)).join(', ')}</h2>
                        <p>
                          {others.map((person) => `${personName(person)} · ${roleLabel(person.role)}`).join(', ')}
                        </p>
                      </div>
                    </>
                  )
                })()}
              </header>

              <div className="messages-feed">
                {detail.messages.map((message) => {
                  const isMine = message.sender_user_id === user?.id
                  const sender = detail.participants.find((person) => person.id === message.sender_user_id)
                  const author = sender && isInstitutionRole(sender.role)
                    ? (activeOrganization?.name || message.sender_name)
                    : message.sender_name

                  return (
                    <div key={message.id} className={`messages-bubble-row${isMine ? ' is-mine' : ''}`}>
                      <div className="messages-bubble">
                        <span className="messages-bubble__author">
                          {author}
                          <time>{messageDate(message.created_at)}</time>
                        </span>
                        <p>{message.body}</p>
                      </div>
                    </div>
                  )
                })}
                <div ref={messagesEndRef} />
              </div>

              <form className="messages-reply" onSubmit={(event) => void answer(event)}>
                <textarea
                  value={reply}
                  onChange={(event) => setReply(event.target.value)}
                  rows={2}
                  maxLength={5000}
                  placeholder="Écrire un message…"
                />
                <button type="submit" disabled={working || !reply.trim()} aria-label="Envoyer">
                  <Send size={16} />
                </button>
              </form>
            </>
          )}
        </article>
      </div>

      {composing && (
        <div
          className="messages-modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setComposing(false)
          }}
        >
          <div className="messages-modal" role="dialog" aria-modal="true" aria-labelledby="school-new-message-title">
            <div className="messages-modal__header">
              <h2 id="school-new-message-title">Nouveau message</h2>
              <button
                type="button"
                className="messages-modal__close"
                onClick={() => setComposing(false)}
                aria-label="Fermer"
              >
                <X size={18} />
              </button>
            </div>

            <form className="messages-compose" onSubmit={(event) => void create(event)}>
              <div className="messages-recipient-field">
                <span>Destinataire</span>
                <div className="messages-recipient-box" ref={recipientBoxRef}>
                  {selectedRecipient ? (
                    <div className="messages-recipient-selected">
                      {avatar(selectedRecipient, 'messages-recipient-selected__avatar')}
                      <span className="messages-recipient-selected__name">
                        {personName(selectedRecipient)}
                        <small>{roleLabel(selectedRecipient.role)}</small>
                      </span>
                      <button
                        type="button"
                        className="messages-recipient-selected__clear"
                        onClick={() => {
                          setSelectedRecipientId(null)
                          setRecipientSearch('')
                        }}
                        aria-label="Effacer"
                      >
                        <X size={18} />
                      </button>
                    </div>
                  ) : (
                    <div className="messages-recipient-search">
                      <Search size={15} className="messages-recipient-search__icon" />
                      <input
                        type="text"
                        placeholder="Rechercher un contact…"
                        value={recipientSearch}
                        onChange={(event) => {
                          setRecipientSearch(event.target.value)
                          setRecipientDropdownOpen(true)
                        }}
                        onFocus={() => setRecipientDropdownOpen(true)}
                        autoComplete="off"
                      />
                    </div>
                  )}

                  {recipientDropdownOpen && !selectedRecipient && (
                    <div className="messages-recipient-dropdown">
                      {filteredRecipients.length === 0 ? (
                        <div className="messages-recipient-dropdown__empty">Aucun contact trouvé</div>
                      ) : (
                        filteredRecipients.map((person) => (
                          <button
                            key={person.id}
                            type="button"
                            className="messages-recipient-option"
                            onClick={() => {
                              setSelectedRecipientId(person.id)
                              setRecipientDropdownOpen(false)
                              setRecipientSearch('')
                            }}
                          >
                            {avatar(person, 'messages-recipient-option__avatar')}
                            <span className="messages-recipient-option__info">
                              <strong>{personName(person)}</strong>
                              <small>{roleLabel(person.role)}</small>
                            </span>
                          </button>
                        ))
                      )}
                    </div>
                  )}
                </div>
              </div>

              <label>
                <span>Sujet</span>
                <input
                  value={subject}
                  maxLength={255}
                  onChange={(event) => setSubject(event.target.value)}
                  placeholder="Sujet de la conversation"
                />
              </label>

              <label className="messages-compose__body">
                <span>Message</span>
                <textarea
                  value={body}
                  maxLength={5000}
                  onChange={(event) => setBody(event.target.value)}
                  rows={5}
                  required
                />
              </label>

              <button type="submit" disabled={working || !selectedRecipientId || !body.trim()}>
                <Send size={15} />
                Envoyer
              </button>
            </form>
          </div>
        </div>
      )}
    </main>
  )
}
