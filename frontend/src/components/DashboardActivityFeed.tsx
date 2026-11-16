import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, ClipboardList, MessageCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useTenant } from '../app/TenantContext'
import {
  listMessageThreads,
  listSchoolCourseDayReports,
  type SchoolCourseDayReport,
  type SchoolMessageThread,
} from '../lib/api'

type ActivityRow = {
  key: string
  kind: 'message' | 'report'
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
  if (sameDay) return date.toLocaleTimeString(activeSchoolLocale(), { hour: '2-digit', minute: '2-digit' })
  return date.toLocaleDateString(activeSchoolLocale(), { day: '2-digit', month: 'short' })
}

function messageRow(thread: SchoolMessageThread, currentUserId?: number): ActivityRow | null {
  if (!thread.last_message || !thread.last_message_at) return null
  const sender = thread.participants.find((participant) => participant.id === thread.last_message?.sender_user_id)
  const fallback = thread.participants.find((participant) => participant.id !== currentUserId) || thread.participants[0]
  return {
    key: `message-${thread.id}`,
    kind: 'message',
    date: thread.last_message_at,
    name: thread.last_message.sender_name || sender?.full_name || fallback?.full_name || 'Message',
    avatarUrl: sender?.avatar_url || fallback?.avatar_url || null,
    title: thread.subject || 'Conversation',
    preview: thread.last_message.body,
    to: '/app/manage/messages',
    unread: thread.unread_count > 0,
  }
}

function reportRow(report: SchoolCourseDayReport): ActivityRow {
  return {
    key: `report-${report.course_day_id}`,
    kind: 'report',
    date: report.submitted_at,
    name: report.teacher_name ? `Prof. ${report.teacher_name}` : 'Enseignant',
    avatarUrl: null,
    title: report.title,
    preview: report.summary,
    to: '/app/manage/course-reports',
    unread: false,
  }
}

export function DashboardActivityFeed() {
  const { user } = useAuth()
  const { activeOrganization } = useTenant()
  const [threads, setThreads] = useState<SchoolMessageThread[]>([])
  const [reports, setReports] = useState<SchoolCourseDayReport[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!activeOrganization) {
      setThreads([])
      setReports([])
      setLoading(false)
      return
    }

    let active = true
    setLoading(true)
    void Promise.allSettled([listMessageThreads(), listSchoolCourseDayReports()])
      .then(([threadResult, reportResult]) => {
        if (!active) return
        setThreads(threadResult.status === 'fulfilled' ? threadResult.value : [])
        setReports(reportResult.status === 'fulfilled' ? reportResult.value : [])
      })
      .finally(() => { if (active) setLoading(false) })

    return () => { active = false }
  }, [activeOrganization?.id])

  const rows = useMemo(() => {
    const messageRows = threads
      .map((thread) => messageRow(thread, user?.id))
      .filter((row): row is ActivityRow => Boolean(row))
    const reportRows = reports.map(reportRow)
    return [...messageRows, ...reportRows]
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
      .slice(0, 4)
  }, [threads, reports, user?.id])

  return (
    <section className="owner-dashboard-activity-card" aria-label="Messages et activité récente">
      <div className="owner-dashboard-card-title owner-dashboard-activity-title">
        <span>Messagerie</span>
        <small>Messages & comptes rendus</small>
      </div>

      {loading ? (
        <div className="owner-dashboard-activity-empty">Chargement des échanges…</div>
      ) : rows.length === 0 ? (
        <div className="owner-dashboard-activity-empty">
          <MessageCircle size={20} />
          <span>Aucun échange récent.</span>
        </div>
      ) : (
        <div className="owner-dashboard-activity-list">
          {rows.map((row) => (
            <Link key={row.key} className={`owner-dashboard-activity-row${row.unread ? ' is-unread' : ''}`} to={row.to}>
              <span className={`owner-dashboard-activity-avatar${row.kind === 'report' ? ' is-report' : ''}`}>
                {row.avatarUrl ? <img src={row.avatarUrl} alt="" /> : row.kind === 'report' ? <ClipboardList size={17} /> : initials(row.name)}
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
        <Link to="/app/manage/messages">Tous les messages <ArrowRight size={14} /></Link>
        <Link to="/app/manage/course-reports">Comptes rendus <ArrowRight size={14} /></Link>
      </div>
    </section>
  )
}
