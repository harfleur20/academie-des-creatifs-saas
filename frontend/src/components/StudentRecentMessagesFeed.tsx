import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, MessageCircle, MessagesSquare } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useTenant } from '../app/TenantContext'
import {
  listClassDiscussion,
  listMessageThreads,
  listStudentClasses,
  type DiscussionPost,
  type SchoolMessageThread,
  type StudentClass,
} from '../lib/api'

type StudentCommunicationRow = {
  key: string
  kind: 'message' | 'post' | 'reply'
  date: string
  name: string
  avatarUrl: string | null
  title: string
  preview: string
  to: string
  unread: boolean
}

function initials(value: string) {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || '?'
}

function compactDate(value: string) {
  const date = new Date(value)
  const now = new Date()
  const sameDay = date.toDateString() === now.toDateString()
  if (sameDay) {
    return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  }
  return date.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' })
}

function privateMessageRow(
  thread: SchoolMessageThread,
  currentUserId?: number,
): StudentCommunicationRow | null {
  if (!thread.last_message || !thread.last_message_at) return null
  const sender = thread.participants.find(
    (participant) => participant.id === thread.last_message?.sender_user_id,
  )
  const fallback = thread.participants.find(
    (participant) => participant.id !== currentUserId,
  ) || thread.participants[0]

  return {
    key: `message-${thread.id}`,
    kind: 'message',
    date: thread.last_message_at,
    name: thread.last_message.sender_name || sender?.full_name || fallback?.full_name || 'Message',
    avatarUrl: sender?.avatar_url || fallback?.avatar_url || null,
    title: thread.subject || 'Conversation privée',
    preview: thread.last_message.body,
    to: '/app/student/messages',
    unread: thread.unread_count > 0,
  }
}

function classRows(
  studentClass: StudentClass,
  posts: DiscussionPost[],
): StudentCommunicationRow[] {
  const classTitle = `${studentClass.formation_title} · ${studentClass.session_label}`
  const to = `/app/student/class?session=${studentClass.session_id}`

  return posts.flatMap((post) => {
    const postRow: StudentCommunicationRow = {
      key: `post-${studentClass.session_id}-${post.id}`,
      kind: 'post',
      date: post.created_at,
      name: post.author.full_name,
      avatarUrl: post.author.avatar_url,
      title: `Publication · ${classTitle}`,
      preview: post.body || 'Nouvelle publication dans la discussion de classe.',
      to,
      unread: false,
    }

    const replyRows: StudentCommunicationRow[] = post.replies.map((reply) => ({
      key: `reply-${studentClass.session_id}-${post.id}-${reply.id}`,
      kind: 'reply',
      date: reply.created_at,
      name: reply.author.full_name,
      avatarUrl: reply.author.avatar_url,
      title: `Commentaire · ${classTitle}`,
      preview: reply.body,
      to,
      unread: false,
    }))

    return [postRow, ...replyRows]
  })
}

export function StudentRecentMessagesFeed() {
  const { user } = useAuth()
  const { activeOrganization } = useTenant()
  const [threads, setThreads] = useState<SchoolMessageThread[]>([])
  const [classActivity, setClassActivity] = useState<StudentCommunicationRow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!activeOrganization) {
      setThreads([])
      setClassActivity([])
      setLoading(false)
      return
    }

    let active = true
    setLoading(true)

    async function load() {
      const [threadResult, classesResult] = await Promise.allSettled([
        listMessageThreads(),
        listStudentClasses(),
      ])
      if (!active) return

      setThreads(threadResult.status === 'fulfilled' ? threadResult.value : [])

      if (classesResult.status !== 'fulfilled') {
        setClassActivity([])
        return
      }

      const classes = classesResult.value
      const discussionResults = await Promise.allSettled(
        classes.map((studentClass) => listClassDiscussion(studentClass.session_id)),
      )
      if (!active) return

      setClassActivity(
        discussionResults.flatMap((result, index) => (
          result.status === 'fulfilled'
            ? classRows(classes[index], result.value)
            : []
        )),
      )
    }

    void load().finally(() => {
      if (active) setLoading(false)
    })

    return () => {
      active = false
    }
  }, [activeOrganization?.id])

  const rows = useMemo(() => {
    const privateRows = threads
      .map((thread) => privateMessageRow(thread, user?.id))
      .filter((row): row is StudentCommunicationRow => Boolean(row))

    return [...privateRows, ...classActivity]
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
      .slice(0, 4)
  }, [threads, classActivity, user?.id])

  const unreadCount = rows.filter((row) => row.unread).length

  return (
    <section className="owner-dashboard-activity-card student-dashboard-communications" aria-label="Messages et échanges récents">
      <div className="owner-dashboard-card-title owner-dashboard-activity-title">
        <span>MESSAGES RÉCENTS</span>
        <small>{unreadCount > 0 ? `${unreadCount} non lu${unreadCount > 1 ? 's' : ''}` : 'Messagerie & classe'}</small>
      </div>

      {loading ? (
        <div className="owner-dashboard-activity-empty">Chargement des échanges…</div>
      ) : rows.length === 0 ? (
        <div className="owner-dashboard-activity-empty">
          <MessageCircle size={20} />
          <span>Aucun message récent.</span>
        </div>
      ) : (
        <div className="owner-dashboard-activity-list">
          {rows.map((row) => (
            <Link
              key={row.key}
              className={`owner-dashboard-activity-row${row.unread ? ' is-unread' : ''}`}
              to={row.to}
            >
              <span className={`owner-dashboard-activity-avatar${row.kind !== 'message' ? ' is-report' : ''}`}>
                {row.avatarUrl
                  ? <img src={row.avatarUrl} alt="" />
                  : row.kind === 'message'
                    ? initials(row.name)
                    : <MessagesSquare size={17} />}
              </span>
              <span className="owner-dashboard-activity-copy">
                <span className="owner-dashboard-activity-meta">
                  <strong>{row.name}</strong>
                  <time dateTime={row.date}>{compactDate(row.date)}</time>
                </span>
                <b>{row.title}</b>
                <small>{row.preview}</small>
              </span>
              <ArrowRight className="owner-dashboard-activity-arrow" size={15} />
            </Link>
          ))}
        </div>
      )}

      <div className="owner-dashboard-activity-actions">
        <Link to="/app/student/messages">Tous les messages <ArrowRight size={14} /></Link>
        <Link to="/app/student/class">Ma classe <ArrowRight size={14} /></Link>
      </div>
    </section>
  )
}
