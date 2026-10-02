import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  CheckCircle2,
  Clock3,
  ExternalLink,
  FileUp,
  MessageSquare,
  Plus,
  Users,
} from 'lucide-react'
import {
  ApiError,
  createAssignmentComment,
  createTeacherAssignment,
  getSessionPlanning,
  getTeacherWorkspace,
  listAssignmentComments,
  listAssignmentSubmissions,
  listTeacherAssignments,
  reviewAssignmentSubmission,
  type Assignment,
  type AssignmentComment,
  type AssignmentSubmission,
  type CourseDay,
  type TeacherWorkspace,
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

export function TeacherAssignmentsPage() {
  const [workspace, setWorkspace] = useState<TeacherWorkspace | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [courseDays, setCourseDays] = useState<CourseDay[]>([])
  const [title, setTitle] = useState('')
  const [instructions, setInstructions] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [courseDayId, setCourseDayId] = useState('')
  const [finalProject, setFinalProject] = useState(false)
  const [selected, setSelected] = useState<Assignment | null>(null)
  const [submissions, setSubmissions] = useState<AssignmentSubmission[]>([])
  const [scores, setScores] = useState<Record<number, string>>({})
  const [threadSubmission, setThreadSubmission] = useState<AssignmentSubmission | null>(null)
  const [comments, setComments] = useState<AssignmentComment[]>([])
  const [comment, setComment] = useState('')
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)

  useEffect(() => {
    getTeacherWorkspace()
      .then((data) => {
        setWorkspace(data)
        setSessionId(data.sessions[0]?.session_id ?? null)
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Chargement impossible.'),
      )
  }, [])

  async function refreshSession(id: number) {
    const [items, planning] = await Promise.all([
      listTeacherAssignments(id),
      getSessionPlanning(id),
    ])
    setAssignments(items)
    setCourseDays(planning.course_days.filter((day) => day.status !== 'cancelled'))
  }

  useEffect(() => {
    if (!sessionId) return
    void refreshSession(sessionId).catch((err) =>
      setError(err instanceof ApiError ? err.message : 'Chargement impossible.'),
    )
  }, [sessionId])

  const currentSession = useMemo(
    () => workspace?.sessions.find((item) => item.session_id === sessionId) ?? null,
    [workspace, sessionId],
  )

  async function createAssignment(event: FormEvent) {
    event.preventDefault()
    if (!sessionId || !dueDate) return

    setWorking(true)
    setError('')
    try {
      await createTeacherAssignment(sessionId, {
        title: title.trim(),
        instructions: instructions.trim(),
        due_date: new Date(dueDate).toISOString(),
        course_day_id: courseDayId ? Number(courseDayId) : null,
        is_final_project: finalProject,
      })
      setTitle('')
      setInstructions('')
      setDueDate('')
      setCourseDayId('')
      setFinalProject(false)
      await refreshSession(sessionId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Création impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function openSubmissions(assignment: Assignment) {
    setSelected(assignment)
    setThreadSubmission(null)
    setComments([])
    try {
      const rows = await listAssignmentSubmissions(assignment.id)
      setSubmissions(rows)
      setScores(
        Object.fromEntries(
          rows.map((submission) => [
            submission.id,
            String(submission.review_score ?? ''),
          ]),
        ),
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Soumissions indisponibles.')
    }
  }

  async function saveScore(submission: AssignmentSubmission) {
    if (!selected) return
    const score = Number(scores[submission.id])
    if (Number.isNaN(score)) return

    try {
      const updated = await reviewAssignmentSubmission(
        selected.id,
        submission.id,
        score,
      )
      setSubmissions((rows) =>
        rows.map((row) => (row.id === updated.id ? updated : row)),
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Correction impossible.')
    }
  }

  async function openThread(submission: AssignmentSubmission) {
    if (!selected) return
    setThreadSubmission(submission)
    setComments(
      await listAssignmentComments(selected.id, submission.enrollment_id),
    )
  }

  async function sendComment() {
    if (!selected || !threadSubmission || !comment.trim()) return
    const created = await createAssignmentComment(
      selected.id,
      threadSubmission.enrollment_id,
      { body: comment.trim() },
    )
    setComments((rows) => [...rows, created])
    setComment('')
  }

  return (
    <main className="app-page assignments-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Espace professeur</span>
          <h1>Devoirs</h1>
          <p>Créez les travaux de vos sessions et corrigez les remises de vos étudiants.</p>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}

      <div className="assignment-session-picker">
        <label>
          Session
          <select
            value={sessionId ?? ''}
            onChange={(event) => setSessionId(Number(event.target.value))}
          >
            {workspace?.sessions.map((session) => (
              <option key={session.session_id} value={session.session_id}>
                {session.formation_title} · {session.session_label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {currentSession && (
        <section className="assignment-layout">
          <form className="app-card assignment-create-card" onSubmit={createAssignment}>
            <span className="section-label">Nouveau devoir</span>
            <h2>{currentSession.session_label}</h2>

            <label>
              Titre
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                required
                minLength={2}
              />
            </label>

            <label>
              Créneau de cours
              <select
                value={courseDayId}
                onChange={(event) => setCourseDayId(event.target.value)}
              >
                <option value="">Sans créneau</option>
                {courseDays
                  .filter((day) => day.can_edit)
                  .map((day) => (
                    <option key={day.id} value={day.id}>
                      {dateTime(day.scheduled_at)} · {day.title}
                    </option>
                  ))}
              </select>
            </label>

            <label>
              Date limite
              <input
                type="datetime-local"
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
                required
              />
            </label>

            <label>
              Consignes
              <textarea
                value={instructions}
                onChange={(event) => setInstructions(event.target.value)}
              />
            </label>

            <label className="assignment-check">
              <input
                type="checkbox"
                checked={finalProject}
                onChange={(event) => setFinalProject(event.target.checked)}
              />
              Projet final
            </label>

            <button className="primary-button" disabled={working}>
              <Plus size={15} />
              {working ? 'Création…' : 'Créer le devoir'}
            </button>
          </form>

          <section className="assignment-list">
            {assignments.map((assignment) => (
              <article className="app-card assignment-card" key={assignment.id}>
                <div>
                  <span className="section-label">
                    {assignment.is_final_project ? 'Projet final' : 'Devoir'}
                  </span>
                  <h3>{assignment.title}</h3>
                  <p>{assignment.instructions}</p>
                </div>
                <div className="assignment-meta">
                  <span>
                    <Clock3 size={14} />
                    Limite : {dateTime(assignment.due_date)}
                  </span>
                  <span>
                    <Users size={14} />
                    {assignment.submissions_count} soumission(s)
                  </span>
                  {assignment.teacher_name && (
                    <span>Prof. {assignment.teacher_name}</span>
                  )}
                </div>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => void openSubmissions(assignment)}
                >
                  <Users size={14} />
                  Voir les soumissions
                </button>
              </article>
            ))}

            {assignments.length === 0 && (
              <div className="app-card formation-empty">
                <FileUp size={28} />
                <strong>Aucun devoir</strong>
                <p>Créez le premier devoir de cette session.</p>
              </div>
            )}
          </section>
        </section>
      )}

      {selected && (
        <div className="assignment-modal-overlay" onClick={() => setSelected(null)}>
          <div className="assignment-modal" onClick={(event) => event.stopPropagation()}>
            <header>
              <div>
                <span className="section-label">Soumissions</span>
                <h2>{selected.title}</h2>
              </div>
              <button type="button" onClick={() => setSelected(null)}>×</button>
            </header>

            <div className="submission-list">
              {submissions.map((submission) => (
                <article className="submission-row" key={submission.id}>
                  <div>
                    <strong>{submission.student_name}</strong>
                    <small>{dateTime(submission.submitted_at)}</small>
                  </div>
                  <a href={submission.file_url} target="_blank" rel="noreferrer">
                    <ExternalLink size={14} /> Travail
                  </a>
                  <div className="submission-score">
                    <input
                      type="number"
                      min="0"
                      max="20"
                      step=".5"
                      value={scores[submission.id] ?? ''}
                      onChange={(event) =>
                        setScores((current) => ({
                          ...current,
                          [submission.id]: event.target.value,
                        }))
                      }
                    />
                    <span>/20</span>
                    <button type="button" onClick={() => void saveScore(submission)}>
                      {submission.is_reviewed && <CheckCircle2 size={15} />}
                      Enregistrer
                    </button>
                  </div>
                  <button
                    type="button"
                    className="secondary-button compact-action"
                    onClick={() => void openThread(submission)}
                  >
                    <MessageSquare size={14} />
                    Échanges {submission.comment_count > 0 ? '(' + submission.comment_count + ')' : ''}
                  </button>
                </article>
              ))}
              {submissions.length === 0 && (
                <div className="empty-row">Aucune soumission reçue.</div>
              )}
            </div>

            {threadSubmission && (
              <section className="assignment-thread">
                <h3>Échanges avec {threadSubmission.student_name}</h3>
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
                    placeholder="Votre retour…"
                  />
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() => void sendComment()}
                    disabled={!comment.trim()}
                  >
                    Envoyer
                  </button>
                </div>
              </section>
            )}
          </div>
        </div>
      )}
    </main>
  )
}
