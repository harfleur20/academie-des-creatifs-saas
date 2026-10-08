import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react'
import {
  BadgeCheck,
  ImagePlus,
  Loader2,
  MessageCircle,
  Send,
  Smile,
  Trash2,
  Users,
  X,
} from 'lucide-react'
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
import {
  deleteClassDiscussionPost,
  deleteClassDiscussionReply,
} from '../lib/classDiscussionApi'

const REPLY_EMOJIS = ['👍', '🙏', '🔥', '👏', '💡', '✅']
const DISCUSSION_INITIAL_VISIBLE_POSTS = 2
const DISCUSSION_VISIBLE_POSTS_STEP = 2

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toLocaleUpperCase('fr-FR')
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function discussionRoleLabel(role: string) {
  if (role === 'teacher') return 'Professeur'
  if (role === 'admin') return 'Admin'
  return 'Étudiant'
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

function DiscussionAuthorName({ author }: { author: DiscussionPost['author'] }) {
  return <strong className="class-discussion-author-name">
    <span>{author.full_name}{author.is_current_user ? ' · Vous' : ''}</span>
    {author.role === 'teacher' && <BadgeCheck className="class-discussion-verified" size={13} aria-label="Professeur" />}
  </strong>
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

function ClassDiscussionPanel({ sessionId }: { sessionId: number }) {
  const [posts, setPosts] = useState<DiscussionPost[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [postBody, setPostBody] = useState('')
  const [postImageUrl, setPostImageUrl] = useState('')
  const [postImageName, setPostImageName] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [isPosting, setIsPosting] = useState(false)
  const [replyDrafts, setReplyDrafts] = useState<Record<number, string>>({})
  const [replyImageUrls, setReplyImageUrls] = useState<Record<number, string>>({})
  const [replyImageNames, setReplyImageNames] = useState<Record<number, string>>({})
  const [uploadingReplyPostId, setUploadingReplyPostId] = useState<number | null>(null)
  const [replyingPostId, setReplyingPostId] = useState<number | null>(null)
  const [visiblePostCount, setVisiblePostCount] = useState(DISCUSSION_INITIAL_VISIBLE_POSTS)
  const [imagePreview, setImagePreview] = useState<{ src: string; alt: string } | null>(null)
  const [deletingItem, setDeletingItem] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setVisiblePostCount(DISCUSSION_INITIAL_VISIBLE_POSTS)
    setIsLoading(true)
    setPosts([])
    listClassDiscussion(sessionId)
      .then((rows) => {
        if (cancelled) return
        setPosts(rows)
        setError('')
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Discussion indisponible.')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => { cancelled = true }
  }, [sessionId])

  async function handleImageChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setError('Ajoutez une image JPG, PNG ou WebP.')
      return
    }
    setIsUploading(true)
    setError('')
    try {
      const asset = await uploadClassDiscussionImage(sessionId, file)
      setPostImageUrl(asset.public_url)
      setPostImageName(asset.filename)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'ajouter l'image.")
    } finally {
      setIsUploading(false)
    }
  }

  async function handleSubmitPost(event: FormEvent) {
    event.preventDefault()
    const body = postBody.trim()
    if (!body && !postImageUrl) return
    setIsPosting(true)
    setError('')
    try {
      const created = await createClassDiscussionPost(sessionId, {
        body,
        image_url: postImageUrl || null,
      })
      setPosts((current) => [created, ...current])
      setPostBody('')
      setPostImageUrl('')
      setPostImageName('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de publier.')
    } finally {
      setIsPosting(false)
    }
  }

  async function handleReplyImageChange(postId: number, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setError('Ajoutez une image JPG, PNG ou WebP.')
      return
    }
    setUploadingReplyPostId(postId)
    setError('')
    try {
      const asset = await uploadClassDiscussionImage(sessionId, file)
      setReplyImageUrls((current) => ({ ...current, [postId]: asset.public_url }))
      setReplyImageNames((current) => ({ ...current, [postId]: asset.filename }))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'ajouter l'image.")
    } finally {
      setUploadingReplyPostId(null)
    }
  }

  async function handleSubmitReply(postId: number) {
    const body = (replyDrafts[postId] ?? '').trim()
    const imageUrl = replyImageUrls[postId] ?? ''
    if (!body && !imageUrl) return
    setReplyingPostId(postId)
    setError('')
    try {
      const created = await createClassDiscussionReply(sessionId, postId, {
        body,
        image_url: imageUrl || null,
      })
      setPosts((rows) => rows.map((post) => (
        post.id === postId ? { ...post, replies: [...post.replies, created] } : post
      )))
      setReplyDrafts((current) => ({ ...current, [postId]: '' }))
      clearReplyImage(postId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'ajouter le commentaire.")
    } finally {
      setReplyingPostId(null)
    }
  }

  function appendReplyEmoji(postId: number, emoji: string) {
    setReplyDrafts((current) => ({ ...current, [postId]: `${current[postId] ?? ''}${emoji}` }))
  }

  function clearReplyImage(postId: number) {
    setReplyImageUrls((current) => {
      const next = { ...current }
      delete next[postId]
      return next
    })
    setReplyImageNames((current) => {
      const next = { ...current }
      delete next[postId]
      return next
    })
  }

  async function handleDeletePost(postId: number) {
    if (!window.confirm('Supprimer cette publication pour toute la classe ?')) return
    setDeletingItem(`post-${postId}`)
    setError('')
    try {
      await deleteClassDiscussionPost(sessionId, postId)
      setPosts((current) => current.filter((post) => post.id !== postId))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de supprimer la publication.')
    } finally {
      setDeletingItem(null)
    }
  }

  async function handleDeleteReply(postId: number, replyId: number) {
    if (!window.confirm('Supprimer ce commentaire ?')) return
    setDeletingItem(`reply-${replyId}`)
    setError('')
    try {
      await deleteClassDiscussionReply(sessionId, postId, replyId)
      setPosts((current) => current.map((post) => (
        post.id === postId
          ? { ...post, replies: post.replies.filter((reply) => reply.id !== replyId) }
          : post
      )))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de supprimer le commentaire.')
    } finally {
      setDeletingItem(null)
    }
  }

  const inputId = `class-discussion-image-${sessionId}`
  const visiblePosts = posts.slice(0, visiblePostCount)
  const hiddenPosts = posts.slice(visiblePostCount)
  const hiddenPreviewPosts = hiddenPosts.slice(0, DISCUSSION_VISIBLE_POSTS_STEP)
  const hiddenPostCount = hiddenPosts.length
  const nextPostCount = Math.min(DISCUSSION_VISIBLE_POSTS_STEP, hiddenPostCount)

  return <section className="class-discussion">
    <div className="class-discussion__top">
      <div>
        <h3><MessageCircle size={16} /> Discussion de classe</h3>
        <span>{posts.length} publication{posts.length > 1 ? 's' : ''}</span>
      </div>
    </div>

    <form className="class-discussion-composer" onSubmit={(event) => void handleSubmitPost(event)}>
      <textarea
        rows={3}
        value={postBody}
        onChange={(event) => setPostBody(event.target.value)}
        placeholder="Question, capture de travail, remarque sur le cours..."
        maxLength={2000}
      />
      {postImageUrl && <div className="class-discussion-composer__image">
        <img src={postImageUrl} alt={postImageName || 'Image jointe'} />
        <button type="button" onClick={() => { setPostImageUrl(''); setPostImageName('') }} aria-label="Retirer l'image"><X size={14} /></button>
      </div>}
      <div className="class-discussion-composer__actions">
        <input id={inputId} type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => void handleImageChange(event)} />
        <label className="class-discussion-composer__upload" htmlFor={inputId}>
          {isUploading ? <Loader2 size={15} className="spin-icon" /> : <ImagePlus size={15} />}
          Image
        </label>
        <button type="submit" disabled={isPosting || isUploading || (!postBody.trim() && !postImageUrl)}>
          {isPosting ? <Loader2 size={15} className="spin-icon" /> : <Send size={15} />}
          Publier
        </button>
      </div>
    </form>

    {error && <div className="class-discussion__error">{error}</div>}

    {isLoading ? <div className="class-discussion__loading"><Loader2 size={16} className="spin-icon" /> Chargement...</div>
      : posts.length === 0 ? <div className="class-discussion__empty">Aucune publication pour cette classe.</div>
        : <div className="class-discussion-feed">
          {visiblePosts.map((post) => <article className="class-discussion-post" key={post.id}>
            <div className="class-discussion-post__head">
              <ClassAvatar name={post.author.full_name} url={post.author.avatar_url} />
              <div className="class-discussion-post__meta">
                <DiscussionAuthorName author={post.author} />
                <span>{discussionRoleLabel(post.author.role)} · {formatDateTime(post.created_at)}</span>
              </div>
              {post.author.is_current_user && <div className="class-discussion-post__actions">
                <button
                  type="button"
                  className="class-discussion-icon-button class-discussion-icon-button--danger"
                  onClick={() => void handleDeletePost(post.id)}
                  disabled={deletingItem === `post-${post.id}`}
                  title="Supprimer la publication"
                >
                  {deletingItem === `post-${post.id}` ? <Loader2 size={14} className="spin-icon" /> : <Trash2 size={14} />}
                </button>
              </div>}
            </div>

            {post.body && <p className="class-discussion-post__body">{post.body}</p>}
            {post.image_url && <button
              type="button"
              className="class-discussion-post__image class-discussion-image-button"
              onClick={() => setImagePreview({ src: post.image_url ?? '', alt: 'Publication de classe' })}
              aria-label="Voir l'image en grand"
            ><img src={post.image_url} alt="Publication de classe" /></button>}

            <div className="class-discussion-replies">
              {post.replies.map((reply) => <div className="class-discussion-reply" key={reply.id}>
                <ClassAvatar name={reply.author.full_name} url={reply.author.avatar_url} />
                <div>
                  <div className="class-discussion-reply__head">
                    <div>
                      <DiscussionAuthorName author={reply.author} />
                      <span>{discussionRoleLabel(reply.author.role)} · {formatDateTime(reply.created_at)}</span>
                    </div>
                    {reply.author.is_current_user && <button
                      type="button"
                      className="class-discussion-icon-button class-discussion-icon-button--danger"
                      onClick={() => void handleDeleteReply(post.id, reply.id)}
                      disabled={deletingItem === `reply-${reply.id}`}
                      title="Supprimer le commentaire"
                    >
                      {deletingItem === `reply-${reply.id}` ? <Loader2 size={14} className="spin-icon" /> : <Trash2 size={14} />}
                    </button>}
                  </div>
                  {reply.body && <p>{reply.body}</p>}
                  {reply.image_url && <button
                    type="button"
                    className="class-discussion-reply__image class-discussion-image-button"
                    onClick={() => setImagePreview({ src: reply.image_url ?? '', alt: 'Image ajoutée à la réponse' })}
                    aria-label="Voir l'image en grand"
                  ><img src={reply.image_url} alt="Image ajoutée à la réponse" /></button>}
                </div>
              </div>)}
            </div>

            <form className="class-discussion-reply-form" onSubmit={(event) => { event.preventDefault(); void handleSubmitReply(post.id) }}>
              {replyImageUrls[post.id] && <div className="class-discussion-reply-form__preview">
                <img src={replyImageUrls[post.id]} alt={replyImageNames[post.id] || 'Image jointe'} />
                <button type="button" onClick={() => clearReplyImage(post.id)} aria-label="Retirer l'image"><X size={13} /></button>
              </div>}
              <div className="class-discussion-reply-form__main">
                <textarea
                  rows={1}
                  value={replyDrafts[post.id] ?? ''}
                  onChange={(event) => setReplyDrafts((current) => ({ ...current, [post.id]: event.target.value }))}
                  placeholder="Répondre..."
                  maxLength={2000}
                />
                <button
                  type="submit"
                  disabled={replyingPostId === post.id || uploadingReplyPostId === post.id || (!(replyDrafts[post.id] ?? '').trim() && !replyImageUrls[post.id])}
                  aria-label="Publier la réponse"
                >
                  {replyingPostId === post.id ? <Loader2 size={14} className="spin-icon" /> : <Send size={14} />}
                </button>
              </div>
              <div className="class-discussion-reply-form__tools">
                <span><Smile size={14} /> Emoji</span>
                <div className="class-discussion-emoji-row">
                  {REPLY_EMOJIS.map((emoji) => <button type="button" key={emoji} onClick={() => appendReplyEmoji(post.id, emoji)}>{emoji}</button>)}
                </div>
                <input
                  id={`class-discussion-reply-image-${post.id}`}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(event) => void handleReplyImageChange(post.id, event)}
                />
                <label className="class-discussion-reply-form__upload" htmlFor={`class-discussion-reply-image-${post.id}`}>
                  {uploadingReplyPostId === post.id ? <Loader2 size={14} className="spin-icon" /> : <ImagePlus size={14} />}
                  Image
                </label>
              </div>
            </form>
          </article>)}

          {hiddenPostCount > 0 && <div className="class-discussion-more">
            <div className="class-discussion-more__preview" aria-hidden="true">
              {hiddenPreviewPosts.map((post) => <div className="class-discussion-more-card" key={`hidden-${post.id}`}>
                <ClassAvatar name={post.author.full_name} url={post.author.avatar_url} />
                <div>
                  <strong>{post.author.full_name}</strong>
                  <span>{discussionRoleLabel(post.author.role)} · {formatDateTime(post.created_at)}</span>
                  <p>{post.body || (post.image_url ? 'Image partagée' : 'Publication de classe')}</p>
                </div>
              </div>)}
            </div>
            <button type="button" className="class-discussion-more__button" onClick={() => setVisiblePostCount((current) => current + DISCUSSION_VISIBLE_POSTS_STEP)}>
              Voir {nextPostCount} publication{nextPostCount > 1 ? 's' : ''} de plus
            </button>
          </div>}
        </div>}

    {imagePreview && <div className="class-discussion-lightbox" role="dialog" aria-modal="true" onClick={() => setImagePreview(null)}>
      <button type="button" className="class-discussion-lightbox__close" onClick={() => setImagePreview(null)} aria-label="Fermer l'image"><X size={22} /></button>
      <img src={imagePreview.src} alt={imagePreview.alt} onClick={(event) => event.stopPropagation()} />
    </div>}
  </section>
}

export function StudentClassPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedSession = searchParams.get('session')
  const [classes, setClasses] = useState<StudentClass[]>([])
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    listStudentClasses().then(setClasses).catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [])

  useEffect(() => {
    const requested = Number(requestedSession)
    setSessionId(classes.find((item) => item.session_id === requested)?.session_id ?? classes[0]?.session_id ?? null)
  }, [classes, requestedSession])

  const current = classes.find((item) => item.session_id === sessionId) ?? null

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
      <ClassDiscussionPanel sessionId={current.session_id} />
    </section>}
    {current && <LiveRecordingsPanel sessionId={current.session_id} />}
  </main>
}
