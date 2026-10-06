import { MessageCircle, Plus, Send } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useTenant } from '../app/TenantContext'
import { useAuth } from '../auth/AuthContext'
import {
  createMessageThread, getMessageThread, listMessageRecipients, listMessageThreads, sendSchoolMessage,
  subscribeSchoolMessages,
  type SchoolMessageRecipient, type SchoolMessageThread, type SchoolMessageThreadDetail,
} from '../lib/api'
import './school-messages.css'

const roleLabel = (role: string) => role === 'admin' ? 'Équipe' : role === 'teacher' ? 'Enseignant' : 'Étudiant'
const messageDate = (value: string | null) => value ? new Date(value).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }) : ''

export function SchoolMessagesPage() {
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

  useEffect(() => {
    let active = true
    setThreads([]); setRecipients([]); setSelectedId(null); setDetail(null); setLoading(true); setError('')
    Promise.all([listMessageThreads(), listMessageRecipients()])
      .then(([items, people]) => { if (!active) return; setThreads(items); setRecipients(people); setSelectedId(items[0]?.id ?? null) })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : 'Chargement impossible.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [activeOrganization?.id])

  useEffect(() => {
    if (selectedId === null) { setDetail(null); return }
    let active = true
    getMessageThread(selectedId)
      .then((value) => { if (active) { setDetail(value); setThreads((items) => items.map((item) => item.id === selectedId ? { ...item, unread_count: 0 } : item)) } })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : 'Conversation inaccessible.') })
    return () => { active = false }
  }, [selectedId, activeOrganization?.id])

  useEffect(() => {
    if (!activeOrganization) return
    let active = true
    const unsubscribe = subscribeSchoolMessages((event) => {
      if (!active || event.type !== 'messages.changed') return
      void listMessageThreads().then((items) => { if (active) setThreads(items) }).catch(() => {})
      if (selectedId !== null) void getMessageThread(selectedId).then((value) => { if (active) setDetail(value) }).catch(() => {})
    })
    const timer = window.setInterval(() => {
      listMessageThreads().then((items) => { if (active) setThreads(items) }).catch(() => {})
      if (selectedId !== null) getMessageThread(selectedId).then((value) => { if (active) setDetail(value) }).catch(() => {})
    }, 15000)
    return () => { active = false; unsubscribe(); window.clearInterval(timer) }
  }, [activeOrganization?.id, selectedId])

  async function create(event: FormEvent) {
    event.preventDefault()
    if (recipientIds.length === 0 || !body.trim()) return
    setWorking(true); setError('')
    try {
      const created = await createMessageThread({ participant_ids: recipientIds, subject, body })
      setDetail(created); setSelectedId(created.id); setComposing(false); setRecipientIds([]); setSubject(''); setBody('')
      setThreads(await listMessageThreads())
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Envoi impossible.') }
    finally { setWorking(false) }
  }

  async function answer(event: FormEvent) {
    event.preventDefault()
    if (!detail || !reply.trim()) return
    setWorking(true); setError('')
    try {
      await sendSchoolMessage(detail.id, reply)
      setReply('')
      setDetail(await getMessageThread(detail.id))
      setThreads(await listMessageThreads())
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Envoi impossible.') }
    finally { setWorking(false) }
  }

  return <main className="app-page school-messages-page">
    <header className="app-page-header"><div><span className="page-kicker">Échanges</span><h1>Messagerie</h1><p>Échangez avec les membres autorisés de votre école.</p></div><button className="primary-button" type="button" onClick={() => setComposing(true)}><Plus size={17}/> Nouveau message</button></header>
    {error && <p className="form-error" role="alert">{error}</p>}
    <div className="school-messages-layout">
      <aside className="school-messages-threads" aria-label="Conversations">
        {loading && <p>Chargement…</p>}
        {!loading && threads.length === 0 && <p>Aucune conversation pour le moment.</p>}
        {threads.map((thread) => <button type="button" key={thread.id} className={selectedId === thread.id && !composing ? 'is-selected' : ''} onClick={() => { setComposing(false); setSelectedId(thread.id) }}>
          <span><strong>{thread.subject}</strong>{thread.unread_count > 0 && <i>{thread.unread_count}</i>}</span>
          <small>{thread.participants.filter((person) => person.id !== user?.id).map((person) => person.full_name).join(', ')}</small>
          <small>{thread.last_message?.body || ''}</small>
          <time>{messageDate(thread.last_message_at)}</time>
        </button>)}
      </aside>
      <section className="school-messages-detail">
        {composing ? <form onSubmit={(event) => void create(event)}>
          <h2>Nouvelle conversation</h2>
          <fieldset><legend>Destinataires (8 maximum)</legend>{recipients.length === 0 && <p>Aucun destinataire disponible.</p>}{recipients.map((person) => <label key={person.id}><input type="checkbox" checked={recipientIds.includes(person.id)} disabled={!recipientIds.includes(person.id) && recipientIds.length >= 8} onChange={(event) => setRecipientIds((ids) => event.target.checked ? [...ids, person.id] : ids.filter((id) => id !== person.id))}/><span>{person.full_name} <small>{roleLabel(person.role)}</small></span></label>)}</fieldset>
          <label>Sujet<input value={subject} maxLength={255} onChange={(event) => setSubject(event.target.value)} placeholder="Sujet de la conversation"/></label>
          <label>Message<textarea value={body} maxLength={5000} onChange={(event) => setBody(event.target.value)} required/></label>
          <div className="school-messages-actions"><button type="button" className="secondary-button" onClick={() => setComposing(false)}>Annuler</button><button type="submit" className="primary-button" disabled={working || recipientIds.length === 0 || !body.trim()}><Send size={16}/> Envoyer</button></div>
        </form> : detail ? <>
          <header><h2>{detail.subject}</h2><p>{detail.participants.filter((person) => person.id !== user?.id).map((person) => person.full_name).join(', ')}</p></header>
          <div className="school-messages-feed">{detail.messages.map((message) => <article key={message.id} className={message.sender_user_id === user?.id ? 'is-mine' : ''}><strong>{message.sender_name}</strong><p>{message.body}</p><time>{messageDate(message.created_at)}</time></article>)}</div>
          <form className="school-messages-reply" onSubmit={(event) => void answer(event)}><label htmlFor="school-message-reply">Répondre</label><textarea id="school-message-reply" value={reply} maxLength={5000} onChange={(event) => setReply(event.target.value)} required/><button className="primary-button" type="submit" disabled={working || !reply.trim()}><Send size={16}/> Envoyer</button></form>
        </> : <div className="school-messages-placeholder"><MessageCircle size={34}/><p>Sélectionnez une conversation ou écrivez un nouveau message.</p></div>}
      </section>
    </div>
  </main>
}
