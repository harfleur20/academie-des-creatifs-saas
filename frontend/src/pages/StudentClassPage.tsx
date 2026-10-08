import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react'
import { ImagePlus, MessageCircle, Send, Users, X } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { LiveRecordingsPanel } from '../components/LiveRecordingsPanel'
import { badgeRingPercent, StudentLevelBadge } from '../components/StudentLevelBadge'
import {
  ApiError,
  createClassDiscussionPost,
  createClassDiscussionReply,
  listClassDiscussion,
  listStudentClasses,
  uploadClassDiscussionImage,
  type DiscussionPost,
  type StudentClass,
} from '../lib/api'

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toLocaleUpperCase('fr-FR')
}

function ClassAvatar({ name, url }: { name: string; url: string | null }) {
  const [imageFailed, setImageFailed] = useState(false)
  useEffect(() => setImageFailed(false), [url])
  return <span className="class-person-avatar">
    {url && !imageFailed
      ? <img src={url} alt={name} onError={() => setImageFailed(true)} />
      : <span aria-label={name}>{initials(name)}</span>}
  </span>
}

function ClassmateCard({ mate }: { mate: StudentClass['classmates'][number] }) {
  return <article className={`student-classmate-card${mate.is_current_user ? ' is-current-user' : ''}`}>
    <ClassAvatar name={mate.full_name} url={mate.avatar_url} />
    <div className="student-classmate-card__identity">
      <div><h3>{mate.full_name}</h3>{mate.is_current_user && <span>Vous</span>}</div>
      <p>{mate.student_code ? `Matricule ${mate.student_code}` : 'Matricule non attribué'}</p>
    </div>
    <div className="student-classmate-card__badge">
      <StudentLevelBadge level={mate.badge.level} ringPct={badgeRingPercent(mate.badge)} />
      <div><small>Badge actuel</small><strong>{mate.badge.label}</strong></div>
    </div>
    {!mate.is_current_user && <Link className="student-classmate-card__contact" to={`/app/student/messages?recipient=${mate.user_id}`}><MessageCircle size={14} aria-hidden="true" /> Contacter</Link>}
  </article>
}

export function StudentClassPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedSession = searchParams.get('session')
  const [classes, setClasses] = useState<StudentClass[]>([])
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [posts, setPosts] = useState<DiscussionPost[]>([])
  const [draft, setDraft] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [replyDrafts, setReplyDrafts] = useState<Record<number, string>>({})
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)

  useEffect(() => {
    listStudentClasses().then(setClasses).catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [])
  useEffect(() => {
    const requested = Number(requestedSession)
    setSessionId(classes.find((item) => item.session_id === requested)?.session_id ?? classes[0]?.session_id ?? null)
  }, [classes, requestedSession])
  useEffect(() => {
    if (!sessionId) return
    let cancelled = false
    setPosts([])
    listClassDiscussion(sessionId)
      .then((rows) => { if (!cancelled) setPosts(rows) })
      .catch((err) => { if (!cancelled) setError(err instanceof ApiError ? err.message : 'Discussion indisponible.') })
    return () => { cancelled = true }
  }, [sessionId])
  const current = classes.find((item) => item.session_id === sessionId) ?? null

  async function uploadImage(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || !sessionId) return
    setWorking(true)
    setError('')
    try {
      const asset = await uploadClassDiscussionImage(sessionId, file)
      setImageUrl(asset.public_url)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Image impossible à ajouter.')
    } finally {
      setWorking(false)
    }
  }

  async function publish(event: FormEvent) {
    event.preventDefault()
    if (!sessionId || (!draft.trim() && !imageUrl)) return
    setWorking(true)
    setError('')
    try {
      const created = await createClassDiscussionPost(sessionId, { body: draft.trim(), image_url: imageUrl || null })
      setPosts((rows) => [created, ...rows])
      setDraft('')
      setImageUrl('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Publication impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function reply(postId: number) {
    if (!sessionId) return
    const body = (replyDrafts[postId] || '').trim()
    if (!body) return
    setError('')
    try {
      const created = await createClassDiscussionReply(sessionId, postId, { body })
      setPosts((rows) => rows.map((post) => post.id === postId ? { ...post, replies: [...post.replies, created] } : post))
      setReplyDrafts((drafts) => ({ ...drafts, [postId]: '' }))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Réponse impossible.')
    }
  }

  return <main className="app-page academic-page student-class-page">
    <header className="app-page-header"><div><span className="page-kicker">Espace étudiant</span><h1>Ma classe</h1><p>Retrouvez votre cohorte et échangez avec votre classe.</p></div></header>
    {error && <div className="form-error">{error}</div>}
    {classes.length > 0 && <label className="academic-session-select">Classe
      <select value={sessionId ?? ''} onChange={(event) => setSearchParams({ session: event.target.value })}>
        {classes.map((item) => <option key={item.session_id} value={item.session_id}>{item.formation_title} · {item.session_label}</option>)}
      </select>
    </label>}
    {current && <section className="class-layout">
      <aside className="app-card class-roster">
        <div className="settings-section-heading"><div><span className="section-label">Cohorte</span><h2>{current.classmates.length} étudiant(s)</h2></div><Users size={18} aria-hidden="true" /></div>
        <div className="student-class-grid">{current.classmates.map((mate) => <ClassmateCard mate={mate} key={mate.enrollment_id} />)}</div>
      </aside>
      <section className="class-discussion">
        <form className="app-card class-composer" onSubmit={(event) => void publish(event)}>
          <textarea value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Question, remarque, partage avec la classe…" aria-label="Votre publication" />
          {imageUrl && <div className="class-composer__preview"><img src={imageUrl} alt="Aperçu de votre image" /><button type="button" onClick={() => setImageUrl('')} aria-label="Retirer l'image"><X size={16} /></button></div>}
          <div><label className="secondary-button compact-action"><ImagePlus size={13} aria-hidden="true" /> Image<input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => void uploadImage(event)} /></label><button className="primary-button compact-action" type="submit" disabled={working || (!draft.trim() && !imageUrl)}><Send size={13} aria-hidden="true" /> Publier</button></div>
        </form>
        <div className="class-post-list">{posts.map((post) => <article className="app-card class-post" key={post.id}>
          <header><ClassAvatar name={post.author.full_name} url={post.author.avatar_url} /><div><strong>{post.author.full_name}</strong><small>{post.author.role === 'student' ? 'Étudiant' : post.author.role === 'teacher' ? 'Professeur' : 'Gestion'} · {new Date(post.created_at).toLocaleString('fr-FR')}</small></div></header>
          {post.body && <p>{post.body}</p>}
          {post.image_url && <img src={post.image_url} alt="Image de la publication" />}
          <div className="class-replies">{post.replies.map((reply) => <div className="class-reply" key={reply.id}><ClassAvatar name={reply.author.full_name} url={reply.author.avatar_url} /><div><strong>{reply.author.full_name}</strong><span>{reply.body}</span><small>{new Date(reply.created_at).toLocaleString('fr-FR')}</small></div></div>)}</div>
          <div className="class-reply-box"><input value={replyDrafts[post.id] || ''} onChange={(event) => setReplyDrafts((drafts) => ({ ...drafts, [post.id]: event.target.value }))} placeholder="Répondre…" aria-label={`Répondre à ${post.author.full_name}`} /><button type="button" onClick={() => void reply(post.id)} aria-label="Publier la réponse"><MessageCircle size={13} /></button></div>
        </article>)}</div>
      </section>
    </section>}
    {current && <LiveRecordingsPanel sessionId={current.session_id} />}
  </main>
}
