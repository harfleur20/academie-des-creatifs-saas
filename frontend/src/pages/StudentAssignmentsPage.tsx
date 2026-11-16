import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useState, type ChangeEvent } from 'react'
import {
  CheckCircle2,
  Clock3,
  ExternalLink,
  FileText,
  FileUp,
  LockKeyhole,
  MessageSquare,
  Upload,
  X,
  XCircle,
} from 'lucide-react'
import {
  ApiError,
  createAssignmentComment,
  listAssignmentComments,
  listStudentAssignments,
  openAssignmentSubmission,
  submitStudentAssignment,
  uploadSubmissionAsset,
  type AssignmentComment,
  type StudentAssignment,
} from '../lib/api'
import { AssignmentBriefView } from '../components/AssignmentBriefView'

function dateTime(value: string) {
  return new Date(value).toLocaleString(activeSchoolLocale(), {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function assignmentBadge(assignment: StudentAssignment) {
  if (assignment.is_locked) {
    return <span className="dsh-badge dsh-badge--gray"><LockKeyhole size={12} /> À venir</span>
  }
  if (assignment.student_status === 'pending') {
    return <span className="dsh-badge dsh-badge--blue"><Clock3 size={12} /> À rendre</span>
  }
  if (assignment.student_status === 'submitted') {
    return <span className="dsh-badge dsh-badge--yellow"><Upload size={12} /> Rendu</span>
  }
  if (assignment.student_status === 'late' && assignment.submissions_closed) {
    return <span className="dsh-badge dsh-badge--gray"><XCircle size={12} /> Non rendu · session terminée</span>
  }
  if (assignment.student_status === 'late') {
    return <span className="dsh-badge dsh-badge--red"><XCircle size={12} /> En retard</span>
  }
  return <span className="dsh-badge dsh-badge--green"><CheckCircle2 size={12} /> Corrigé</span>
}

export function StudentAssignmentsPage() {
  const [items, setItems] = useState<StudentAssignment[]>([])
  const [uploading, setUploading] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [submitTarget, setSubmitTarget] = useState<StudentAssignment | null>(null)
  const [thread, setThread] = useState<StudentAssignment | null>(null)
  const [comments, setComments] = useState<AssignmentComment[]>([])
  const [comment, setComment] = useState('')
  const [threadLoading, setThreadLoading] = useState(false)

  async function load() {
    setItems(await listStudentAssignments())
  }

  useEffect(() => {
    void load().catch((err) =>
      setError(err instanceof ApiError ? err.message : 'Chargement impossible.'),
    )
  }, [])

  useEffect(() => {
    if (items.length && window.location.hash.startsWith('#assignment-')) {
      document.getElementById(window.location.hash.slice(1))?.scrollIntoView({ block: 'center' })
    }
  }, [items])

  async function chooseFile(
    assignment: StudentAssignment,
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    setUploading(assignment.id)
    setError('')
    try {
      const asset = await uploadSubmissionAsset(file)
      const updated = await submitStudentAssignment(assignment.id, asset.public_url)
      setItems((rows) => rows.map((item) => (item.id === updated.id ? updated : item)))
      setSubmitTarget(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Envoi impossible.')
    } finally {
      setUploading(null)
    }
  }

  async function openThread(assignment: StudentAssignment) {
    setThread(assignment)
    setThreadLoading(true)
    setError('')
    try {
      setComments(await listAssignmentComments(assignment.id, assignment.enrollment_id))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Les échanges sont indisponibles.')
      setComments([])
    } finally {
      setThreadLoading(false)
    }
  }

  async function sendComment() {
    if (!thread || !comment.trim()) return
    setError('')
    try {
      const created = await createAssignmentComment(
        thread.id,
        thread.enrollment_id,
        { body: comment.trim() },
      )
      setComments((rows) => [...rows, created])
      setComment('')
      setItems((rows) => rows.map((item) => item.id === thread.id
        ? { ...item, comment_count: item.comment_count + 1 }
        : item))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Message non envoyé.')
    }
  }

  const openAssignments = items.filter((item) =>
    !item.is_locked && !item.submissions_closed && ['pending', 'submitted', 'late'].includes(item.student_status),
  ).length

  return (
    <main className="app-page">
      <div className="dsh-page dsh-page--assignments">
        <div className="dsh-page__header">
          <h1>Devoirs</h1>
          <p className="dsh-page__subtitle">
            {openAssignments > 0
              ? `${openAssignments} devoir${openAssignments > 1 ? 's' : ''} à suivre, avec remise et échanges au même endroit.`
              : 'Retrouvez vos consignes, remises et corrections au même endroit.'}
          </p>
        </div>

        {error && <div className="dsh-error">{error}</div>}

        {items.length === 0 ? (
          <div className="dsh-empty">
            <div>
              <FileText size={28} />
              <strong>Aucun devoir pour le moment</strong>
              <p>Les devoirs publiés par vos professeurs apparaîtront ici.</p>
            </div>
          </div>
        ) : (
          <div className="dsh-list">
            {items.map((assignment) => {
              const canSubmit = !assignment.is_locked && !assignment.submissions_closed && assignment.student_status !== 'reviewed'

              return (
                <article
                  className={`dsh-list-item asg-list-item${assignment.is_locked ? ' is-locked' : ''}`}
                  id={`assignment-${assignment.id}`}
                  key={assignment.id}
                >
                  <div className="dsh-list-item__main">
                    <strong>{assignment.title}</strong>
                    <span className="dsh-list-item__meta">
                      {assignment.formation_title} · {assignment.session_label} · Prof. {assignment.teacher_name || '-'}
                    </span>
                    <span className="dsh-list-item__meta">
                      {assignment.is_locked
                        ? `Disponible${assignment.available_at ? ` le ${dateTime(assignment.available_at)}` : ' au début de la séance'}`
                        : `Date limite : ${dateTime(assignment.due_date)}`}
                      {assignment.submitted_at ? ` · Remis le ${dateTime(assignment.submitted_at)}` : ''}
                    </span>
                    <AssignmentBriefView brief={assignment.brief} instructions={assignment.instructions} />
                  </div>

                  <div className="dsh-list-item__actions">
                    {assignment.review_score !== null && (
                      <span className="asg-grade">{assignment.review_score}/{assignment.review_max_score}</span>
                    )}
                    {assignmentBadge(assignment)}
                    {assignment.file_url && (
                      <button
                        className="dsh-btn dsh-btn--ghost dsh-btn--sm"
                        type="button"
                        onClick={() => void openAssignmentSubmission(assignment.file_url!).catch((cause) =>
                          setError(cause instanceof Error ? cause.message : 'Téléchargement impossible.'),
                        )}
                      >
                        <ExternalLink size={13} /> Voir ma remise
                      </button>
                    )}
                    {canSubmit && (
                      <button
                        className="dsh-btn dsh-btn--primary dsh-btn--sm"
                        type="button"
                        disabled={uploading !== null}
                        onClick={() => setSubmitTarget(assignment)}
                      >
                        <FileUp size={13} />
                        {assignment.student_status === 'submitted'
                          ? 'Modifier'
                          : assignment.student_status === 'late' ? 'Remettre en retard' : 'Remettre'}
                      </button>
                    )}
                    {!assignment.is_locked && (
                      <button
                        className="dsh-btn dsh-btn--outline dsh-btn--sm"
                        type="button"
                        onClick={() => void openThread(assignment)}
                      >
                        <MessageSquare size={13} /> Échanges
                        {assignment.comment_count > 0 ? ` (${assignment.comment_count})` : ''}
                      </button>
                    )}
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </div>

      {submitTarget && (
        <div className="dsh-modal-overlay" onClick={() => uploading === null && setSubmitTarget(null)}>
          <div className="dsh-modal asg-submit-modal" onClick={(event) => event.stopPropagation()}>
            <div className="dsh-modal__header">
              <div>
                <h3>{submitTarget.student_status === 'submitted' ? 'Modifier ma remise' : 'Remettre le devoir'}</h3>
                <span className="dsh-list-item__meta">{submitTarget.title}</span>
              </div>
              <button className="dsh-icon-btn" type="button" disabled={uploading !== null} onClick={() => setSubmitTarget(null)} aria-label="Fermer">
                <X size={16} />
              </button>
            </div>

            <div className="asg-submit-modal__body">
              <div className="asg-submit-modal__delivery">
                <h4>Votre fichier</h4>
                <label className="asg-submit-upload">
                  <FileUp size={28} />
                  <strong>{uploading === submitTarget.id ? 'Envoi en cours…' : 'Cliquez pour sélectionner votre travail'}</strong>
                  <small>PNG, JPG, WebP, PDF, ZIP, RAR, DOCX, MP4, WebM ou MOV.</small>
                  <input
                    type="file"
                    accept=".png,.jpg,.jpeg,.webp,.pdf,.zip,.rar,.docx,.mp4,.webm,.mov"
                    disabled={uploading === submitTarget.id}
                    onChange={(event) => void chooseFile(submitTarget, event)}
                  />
                </label>
                {submitTarget.file_url && (
                  <button
                    type="button"
                    className="dsh-btn dsh-btn--ghost"
                    onClick={() => void openAssignmentSubmission(submitTarget.file_url!).catch((cause) =>
                      setError(cause instanceof Error ? cause.message : 'Téléchargement impossible.'),
                    )}
                  >
                    <ExternalLink size={13} /> Voir la remise actuelle
                  </button>
                )}
              </div>

              <aside className="asg-submit-modal__instructions-pane">
                <h4>Consignes</h4>
                {submitTarget.brief || submitTarget.instructions
                  ? <AssignmentBriefView brief={submitTarget.brief} instructions={submitTarget.instructions} collapsible={false} />
                  : <p>Aucune consigne supplémentaire.</p>}
                <h4 style={{ marginTop: 22 }}>Date limite</h4>
                <p>{dateTime(submitTarget.due_date)}</p>
                {submitTarget.student_status === 'late' && (
                  <p>La date limite est passée : votre remise reste possible et sera enregistrée à sa date réelle.</p>
                )}
              </aside>
            </div>
          </div>
        </div>
      )}

      {thread && (
        <div className="dsh-modal-overlay" onClick={() => setThread(null)}>
          <div className="dsh-modal asg-thread-modal" onClick={(event) => event.stopPropagation()}>
            <div className="dsh-modal__header">
              <div>
                <h3>Échanges</h3>
                <span className="dsh-list-item__meta">{thread.title}</span>
              </div>
              <button className="dsh-icon-btn" type="button" onClick={() => setThread(null)} aria-label="Fermer">
                <X size={16} />
              </button>
            </div>

            <div className="asg-thread-stream">
              {threadLoading && <div className="dsh-list-item__meta">Chargement des échanges…</div>}
              {!threadLoading && comments.length === 0 && <div className="dsh-list-item__meta">Aucun message pour le moment.</div>}
              {comments.map((entry) => (
                <div className={`asg-message ${entry.author_role}`} key={entry.id}>
                  <strong>{entry.author_name}</strong>
                  <p>{entry.body}</p>
                  <small>{dateTime(entry.created_at)}</small>
                </div>
              ))}
            </div>

            <div className="asg-thread-compose">
              <textarea
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                placeholder="Écrire au professeur…"
              />
              <button
                className="dsh-btn dsh-btn--primary"
                type="button"
                disabled={!comment.trim()}
                onClick={() => void sendComment()}
              >
                Envoyer
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
