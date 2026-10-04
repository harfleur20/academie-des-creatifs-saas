import { useEffect, useState, type ChangeEvent } from 'react'
import {
  CheckCircle2,
  Clock3,
  ExternalLink,
  FileUp,
  MessageSquare,
  Upload,
  XCircle,
} from 'lucide-react'
import {
  ApiError,
  createAssignmentComment,
  listAssignmentComments,
  listStudentAssignments,
  submitStudentAssignment,
  uploadSubmissionAsset,
  openAssignmentSubmission,
  type AssignmentComment,
  type StudentAssignment,
} from '../lib/api'

function dateTime(value: string) {
  return new Date(value).toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function StudentAssignmentsPage() {
  const [items, setItems] = useState<StudentAssignment[]>([])
  const [uploading, setUploading] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [thread, setThread] = useState<StudentAssignment | null>(null)
  const [comments, setComments] = useState<AssignmentComment[]>([])
  const [comment, setComment] = useState('')

  async function load() {
    setItems(await listStudentAssignments())
  }

  useEffect(() => {
    void load().catch((err) =>
      setError(err instanceof ApiError ? err.message : 'Chargement impossible.'),
    )
  }, [])

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
      const updated = await submitStudentAssignment(
        assignment.id,
        asset.public_url,
      )
      setItems((rows) =>
        rows.map((item) => (item.id === updated.id ? updated : item)),
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Envoi impossible.')
    } finally {
      setUploading(null)
    }
  }

  async function openThread(assignment: StudentAssignment) {
    setThread(assignment)
    setComments(
      await listAssignmentComments(
        assignment.id,
        assignment.enrollment_id,
      ),
    )
  }

  async function sendComment() {
    if (!thread || !comment.trim()) return
    const created = await createAssignmentComment(
      thread.id,
      thread.enrollment_id,
      { body: comment.trim() },
    )
    setComments((rows) => [...rows, created])
    setComment('')
  }

  return (
    <main className="app-page assignments-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Espace étudiant</span>
          <h1>Mes devoirs</h1>
          <p>
            Consultez les consignes, remettez votre travail et suivez vos corrections.
          </p>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}

      <section className="student-assignment-list">
        {items.map((assignment) => {
          const canSubmit =
            !assignment.is_locked && (
              assignment.student_status === 'pending' ||
              assignment.student_status === 'submitted'
            )

          let badge
          if (assignment.student_status === 'pending') {
            badge = <><Clock3 size={13} /> À rendre</>
          } else if (assignment.student_status === 'submitted') {
            badge = <><Upload size={13} /> Rendu</>
          } else if (assignment.student_status === 'late') {
            badge = <><XCircle size={13} /> En retard</>
          } else {
            badge = <><CheckCircle2 size={13} /> Corrigé</>
          }

          return (
            <article className="app-card student-assignment-card" key={assignment.id}>
              <div className="student-assignment-main">
                <span className={'assignment-status ' + assignment.student_status}>
                  {badge}
                </span>
                <h2>{assignment.title}</h2>
                <strong>
                  {assignment.formation_title} · {assignment.session_label}
                </strong>
                {assignment.is_locked ? (
                  <p>Disponible au début de la séance{assignment.available_at ? `, le ${dateTime(assignment.available_at)}` : ''}.</p>
                ) : <p>{assignment.instructions}</p>}
                <small>
                  Prof. {assignment.teacher_name || '—'} · Date limite :{' '}
                  {dateTime(assignment.due_date)}
                </small>
                {assignment.submitted_at && (
                  <small>Remis le {dateTime(assignment.submitted_at)}</small>
                )}
              </div>

              <div className="student-assignment-actions">
                {assignment.review_score !== null && (
                  <span className="assignment-grade">
                    {assignment.review_score}/{assignment.review_max_score}
                  </span>
                )}

                {assignment.file_url && (
                  <button
                    className="secondary-button compact-action"
                    type="button"
                    onClick={() => void openAssignmentSubmission(assignment.file_url!).catch((cause) => setError(cause instanceof Error ? cause.message : 'Téléchargement impossible.'))}
                  >
                    <ExternalLink size={14} />
                    Voir ma remise
                  </button>
                )}

                {canSubmit && (
                  <label className="primary-button assignment-upload-button">
                    <FileUp size={14} />
                    {uploading === assignment.id
                      ? 'Envoi…'
                      : assignment.student_status === 'submitted'
                        ? 'Modifier la remise'
                        : 'Remettre'}
                    <input
                      type="file"
                      accept=".png,.jpg,.jpeg,.webp,.pdf,.zip,.rar,.docx,.mp4,.webm,.mov"
                      disabled={uploading === assignment.id}
                      onChange={(event) => void chooseFile(assignment, event)}
                    />
                  </label>
                )}

                {!assignment.is_locked && <button
                  type="button"
                  className="secondary-button compact-action"
                  onClick={() => void openThread(assignment)}
                >
                  <MessageSquare size={14} />
                  Échanges{' '}
                  {assignment.comment_count > 0
                    ? '(' + assignment.comment_count + ')'
                    : ''}
                </button>}
              </div>
            </article>
          )
        })}

        {items.length === 0 && (
          <div className="app-card formation-empty">
            <FileUp size={28} />
            <strong>Aucun devoir</strong>
            <p>Les devoirs créés par vos professeurs apparaîtront ici.</p>
          </div>
        )}
      </section>

      {thread && (
        <div className="assignment-modal-overlay" onClick={() => setThread(null)}>
          <div
            className="assignment-modal assignment-thread-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <span className="section-label">Échanges</span>
                <h2>{thread.title}</h2>
              </div>
              <button type="button" onClick={() => setThread(null)}>×</button>
            </header>

            <div className="assignment-thread-stream">
              {comments.map((entry) => (
                <div
                  className={'assignment-message ' + entry.author_role}
                  key={entry.id}
                >
                  <strong>{entry.author_name}</strong>
                  <p>{entry.body}</p>
                  <small>{dateTime(entry.created_at)}</small>
                </div>
              ))}
            </div>

            <div className="assignment-thread-compose">
              <textarea
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                placeholder="Écrire au professeur…"
              />
              <button
                className="primary-button"
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
