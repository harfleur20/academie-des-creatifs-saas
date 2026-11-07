import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import {
  CheckCircle2,
  Clock3,
  ExternalLink,
  FileUp,
  LoaderCircle,
  MessageSquare,
  Pencil,
  Plus,
  Send,
  Sparkles,
  Trash2,
  Users,
  WandSparkles,
  X,
} from 'lucide-react'
import {
  ApiError,
  createAssignmentComment,
  createTeacherAssignment,
  deleteTeacherAssignment,
  getSessionPlanning,
  getTeacherWorkspace,
  listAssignmentComments,
  listAssignmentSubmissions,
  listTeacherAssignments,
  openAssignmentSubmission,
  publishTeacherAssignment,
  reviewAssignmentSubmission,
  updateTeacherAssignment,
  type Assignment,
  type AssignmentBrief,
  type AssignmentComment,
  type AssignmentSubmission,
  type CourseDay,
  type TeacherWorkspace,
} from '../lib/api'
import {
  generateTeacherAssignmentDraft,
  getTeacherAIStatus,
} from '../lib/tenantIntegrationApi'
import { initialTeacherSessionId } from '../lib/teacherSession'
import {
  AssignmentBriefEditor,
  assignmentBriefProblem,
  assignmentBriefToText,
  cleanAssignmentBrief,
  emptyAssignmentBrief,
} from '../components/AssignmentBriefEditor'
import { AssignmentBriefView } from '../components/AssignmentBriefView'

function dateTime(value: string) {
  return new Date(value).toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function toDateTimeLocal(date: Date) {
  const adjusted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return adjusted.toISOString().slice(0, 16)
}

type CreationMode = 'manual' | 'ai'

export function TeacherAssignmentsPage() {
  const [workspace, setWorkspace] = useState<TeacherWorkspace | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [courseDays, setCourseDays] = useState<CourseDay[]>([])
  const [title, setTitle] = useState('')
  const [instructions, setInstructions] = useState('')
  const [brief, setBrief] = useState<AssignmentBrief | null>(null)
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
  const formErrorRef = useRef<HTMLDivElement>(null)
  const [working, setWorking] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Assignment | null>(null)
  const [busyAssignmentId, setBusyAssignmentId] = useState<number | null>(null)
  const [creationMode, setCreationMode] = useState<CreationMode>('manual')

  const [aiConnected, setAiConnected] = useState<boolean | null>(null)
  const [aiTopic, setAiTopic] = useState('')
  const [aiLevel, setAiLevel] = useState('')
  const [aiObjectives, setAiObjectives] = useState('')
  const [aiDurationDays, setAiDurationDays] = useState(7)
  const [aiAssignmentType, setAiAssignmentType] = useState('auto')
  const [aiGenerating, setAiGenerating] = useState(false)

  useEffect(() => {
    Promise.all([
      getTeacherWorkspace(),
      getTeacherAIStatus().catch(() => null),
    ]).then(([data, aiStatus]) => {
      setWorkspace(data)
      setSessionId(initialTeacherSessionId(data.sessions))
      setAiConnected(aiStatus?.connected ?? false)
    }).catch((err) =>
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

  useEffect(() => {
    // The form scrolls: bring a refusal into view instead of leaving it below the fold.
    if (error) formErrorRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [error])

  const currentSession = useMemo(
    () => workspace?.sessions.find((item) => item.session_id === sessionId) ?? null,
    [workspace, sessionId],
  )

  function resetForm() {
    setTitle('')
    setInstructions('')
    setBrief(null)
    setDueDate('')
    setCourseDayId('')
    setFinalProject(false)
    setCreationMode('manual')
    setAiTopic('')
    setAiLevel('')
    setAiObjectives('')
    setAiDurationDays(7)
    setAiAssignmentType('auto')
  }

  function openEdit(assignment: Assignment) {
    setEditing(assignment)
    setTitle(assignment.title)
    setInstructions(assignment.instructions)
    setBrief(assignment.brief)
    setDueDate(toDateTimeLocal(new Date(assignment.due_date)))
    setCourseDayId(assignment.course_day_id ? String(assignment.course_day_id) : '')
    setFinalProject(assignment.is_final_project)
    setCreationMode('manual')
    setError('')
    setShowForm(true)
  }

  function closeForm() {
    setShowForm(false)
    if (editing) {
      setEditing(null)
      resetForm()
    }
  }

  async function generateWithAI() {
    if (!sessionId || !aiTopic.trim()) return
    setAiGenerating(true)
    setError('')
    try {
      const draft = await generateTeacherAssignmentDraft({
        session_id: sessionId,
        topic: aiTopic.trim(),
        level: aiLevel.trim() || null,
        objectives: aiObjectives.trim() || null,
        course_day_id: courseDayId ? Number(courseDayId) : null,
        duration_days: aiDurationDays,
        is_final_project: finalProject,
        assignment_type: finalProject ? 'final_project' : aiAssignmentType,
      })
      setTitle(draft.title)
      setBrief(draft.brief)
      setInstructions(draft.instructions)
      setFinalProject(draft.is_final_project)
      const deadline = new Date()
      deadline.setDate(deadline.getDate() + draft.duration_days)
      deadline.setHours(23, 59, 0, 0)
      setDueDate(toDateTimeLocal(deadline))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Impossible de générer le devoir.')
    } finally {
      setAiGenerating(false)
    }
  }

  async function saveAssignment(event: FormEvent) {
    event.preventDefault()
    if (!sessionId || !dueDate || title.trim().length < 2) return

    const cleanBrief = brief ? cleanAssignmentBrief(brief) : null
    const briefProblem = cleanBrief ? assignmentBriefProblem(cleanBrief) : null
    if (briefProblem) {
      setError(briefProblem)
      return
    }

    setWorking(true)
    setError('')
    const fields = {
      title: title.trim(),
      instructions: instructions.trim(),
      brief: cleanBrief,
      course_day_id: courseDayId ? Number(courseDayId) : null,
      is_final_project: finalProject,
    }
    const due_date = new Date(dueDate).toISOString()
    try {
      if (editing) {
        const dueDateChanged = dueDate !== toDateTimeLocal(new Date(editing.due_date))
        await updateTeacherAssignment(editing.id, dueDateChanged ? { ...fields, due_date } : fields)
      } else {
        await createTeacherAssignment(sessionId, { ...fields, due_date })
      }
      resetForm()
      setEditing(null)
      setShowForm(false)
      await refreshSession(sessionId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Enregistrement impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function publishAssignment(assignment: Assignment) {
    if (!sessionId) return
    setBusyAssignmentId(assignment.id)
    setError('')
    try {
      await publishTeacherAssignment(assignment.id)
      await refreshSession(sessionId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Publication impossible.')
    } finally {
      setBusyAssignmentId(null)
    }
  }

  async function removeAssignment(assignment: Assignment) {
    if (!sessionId || !window.confirm(`Supprimer le devoir « ${assignment.title} » ?`)) return
    setBusyAssignmentId(assignment.id)
    setError('')
    try {
      await deleteTeacherAssignment(assignment.id)
      await refreshSession(sessionId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Suppression impossible.')
    } finally {
      setBusyAssignmentId(null)
    }
  }

  async function openSubmissions(assignment: Assignment) {
    setSelected(assignment)
    setThreadSubmission(null)
    setComments([])
    try {
      const rows = await listAssignmentSubmissions(assignment.id)
      setSubmissions(rows)
      setScores(Object.fromEntries(rows.map((submission) => [submission.id, String(submission.review_score ?? '')])))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Soumissions indisponibles.')
    }
  }

  async function saveScore(submission: AssignmentSubmission) {
    if (!selected) return
    const score = Number(scores[submission.id])
    if (Number.isNaN(score) || score < 0 || score > 20) {
      setError('La note doit être comprise entre 0 et 20.')
      return
    }
    try {
      const updated = await reviewAssignmentSubmission(selected.id, submission.id, score)
      setSubmissions((rows) => rows.map((row) => (row.id === updated.id ? updated : row)))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Correction impossible.')
    }
  }

  async function openThread(submission: AssignmentSubmission) {
    if (!selected) return
    setThreadSubmission(submission)
    try {
      setComments(await listAssignmentComments(selected.id, submission.enrollment_id))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Échanges indisponibles.')
    }
  }

  async function sendComment() {
    if (!selected || !threadSubmission || !comment.trim()) return
    try {
      const created = await createAssignmentComment(selected.id, threadSubmission.enrollment_id, { body: comment.trim() })
      setComments((rows) => [...rows, created])
      setComment('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Message non envoyé.')
    }
  }

  return (
    <main className="app-page teacher-mother-page">
      <div className="dsh-page teacher-dsh-page">
        <div className="teacher-page-head">
          <div>
            <h1>Devoirs</h1>
            <p>Créez les travaux de vos sessions et corrigez les remises de vos étudiants.</p>
          </div>
          <button className="dsh-btn dsh-btn--primary" type="button" disabled={!currentSession} onClick={() => setShowForm(true)}>
            <Plus size={14} /> Nouveau devoir
          </button>
        </div>

        {error && <div className="dsh-error">{error}</div>}

        <label className="teacher-session-select">
          <span>Session</span>
          <select value={sessionId ?? ''} onChange={(event) => setSessionId(Number(event.target.value))}>
            {workspace?.sessions.map((session) => (
              <option key={session.session_id} value={session.session_id}>{session.formation_title} · {session.session_label}</option>
            ))}
          </select>
        </label>

        <div className="teacher-assignment-list dsh-list">
          {assignments.map((assignment) => (
            <article className="dsh-list-item teacher-assignment-row" key={assignment.id}>
              <div className="dsh-list-item__main">
                <div className="teacher-assignment-title-row">
                  <strong>{assignment.title}</strong>
                  {assignment.publication_status === 'draft' && <span className="dsh-badge dsh-badge--gray">Brouillon</span>}
                  {assignment.brief && <span className="dsh-badge dsh-badge--blue">Fiche TP</span>}
                  {assignment.is_final_project && <span className="dsh-badge dsh-badge--yellow">Projet final</span>}
                </div>
                {assignment.publication_status === 'draft' && <span className="dsh-list-item__meta">Invisible pour les étudiants</span>}
                <span className="dsh-list-item__meta"><Clock3 size={12} /> Date limite : {dateTime(assignment.due_date)}</span>
                <span className="dsh-list-item__meta"><Users size={12} /> {assignment.submissions_count} soumission(s){assignment.teacher_name ? ` · Prof. ${assignment.teacher_name}` : ''}</span>
                <AssignmentBriefView brief={assignment.brief} instructions={assignment.instructions} />
              </div>
              <div className="dsh-list-item__actions">
                {assignment.can_manage && assignment.publication_status === 'draft' && (
                  <button className="dsh-btn dsh-btn--primary dsh-btn--sm" type="button" disabled={busyAssignmentId === assignment.id} onClick={() => void publishAssignment(assignment)}>
                    <Send size={13} /> {busyAssignmentId === assignment.id ? 'Publication…' : 'Publier'}
                  </button>
                )}
                <button className="dsh-btn dsh-btn--outline dsh-btn--sm" type="button" onClick={() => void openSubmissions(assignment)}>
                  <Users size={13} /> Voir les soumissions
                </button>
                {assignment.can_manage && (
                  <button className="dsh-icon-btn" type="button" title="Modifier" aria-label="Modifier" onClick={() => openEdit(assignment)}>
                    <Pencil size={15} />
                  </button>
                )}
                {assignment.can_manage && (
                  <button
                    className="dsh-icon-btn"
                    type="button"
                    disabled={assignment.delete_blocked_reason !== null || busyAssignmentId === assignment.id}
                    title={assignment.delete_blocked_reason ?? 'Supprimer'}
                    aria-label="Supprimer"
                    onClick={() => void removeAssignment(assignment)}
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
            </article>
          ))}
          {assignments.length === 0 && (
            <div className="dsh-empty"><FileUp size={28} /><strong>Aucun devoir</strong><p>Créez le premier devoir de cette session.</p></div>
          )}
        </div>
      </div>

      {showForm && currentSession && (
        <div className="dsh-modal-overlay" onClick={() => !working && !aiGenerating && closeForm()}>
          <form className="dsh-modal dsh-modal--large teacher-create-modal" onSubmit={saveAssignment} onClick={(event) => event.stopPropagation()}>
            <div className="dsh-modal__header">
              <div><span className="section-label">{currentSession.session_label}</span><h3>{editing ? 'Modifier le devoir' : 'Nouveau devoir'}</h3></div>
              <button className="dsh-icon-btn" type="button" disabled={working || aiGenerating} onClick={closeForm}><X size={16} /></button>
            </div>

            {!editing && (
              <div className="teacher-create-tabs">
                <button type="button" className={creationMode === 'manual' ? 'is-active' : ''} onClick={() => setCreationMode('manual')}>Manuel</button>
                <button type="button" className={creationMode === 'ai' ? 'is-active' : ''} onClick={() => setCreationMode('ai')}><WandSparkles size={14} /> Avec IA</button>
              </div>
            )}

            <div className="teacher-create-body">
              {creationMode === 'ai' && (
                <section className="teacher-ai-panel">
                  <div className="teacher-ai-title"><Sparkles size={17} /><div><strong>Générer un brouillon de devoir</strong><span>Le résultat reste modifiable avant création.</span></div></div>
                  {aiConnected === false ? (
                    <div className="teacher-ai-unavailable">OpenAI n’est pas connecté pour cette école. Demandez à un administrateur de l’activer dans Connect.</div>
                  ) : (
                    <>
                      <label>Sujet / brief<textarea value={aiTopic} onChange={(event) => setAiTopic(event.target.value)} placeholder="Ex. Concevoir une identité visuelle complète pour une marque locale" /></label>
                      <div className="teacher-form-grid two-columns">
                        <label>Niveau<input value={aiLevel} onChange={(event) => setAiLevel(event.target.value)} placeholder="Débutant, intermédiaire…" /></label>
                        <label>Type<select value={aiAssignmentType} onChange={(event) => setAiAssignmentType(event.target.value)}><option value="auto">Automatique</option><option value="creative">Créatif / design</option><option value="marketing">Marketing / stratégie</option><option value="technical">Technique / développement</option><option value="case_study">Étude de cas</option></select></label>
                      </div>
                      <label>Objectifs<textarea value={aiObjectives} onChange={(event) => setAiObjectives(event.target.value)} placeholder="Compétences à mobiliser ou résultats attendus" /></label>
                      <label>Durée prévue<select value={aiDurationDays} onChange={(event) => setAiDurationDays(Number(event.target.value))}><option value={3}>3 jours</option><option value={7}>7 jours</option><option value={14}>14 jours</option><option value={21}>21 jours</option><option value={30}>30 jours</option></select></label>
                      <button className="dsh-btn dsh-btn--ai" type="button" disabled={aiGenerating || !aiTopic.trim()} onClick={() => void generateWithAI()}>
                        {aiGenerating ? <LoaderCircle className="openai-spin" size={14} /> : <WandSparkles size={14} />} {aiGenerating ? 'Génération…' : 'Générer le brouillon'}
                      </button>
                    </>
                  )}
                </section>
              )}

              <section className="teacher-manual-fields">
                <label>Titre<input value={title} onChange={(event) => setTitle(event.target.value)} required minLength={2} /></label>
                <div className="teacher-form-grid two-columns">
                  <label>Créneau de cours<select value={courseDayId} onChange={(event) => setCourseDayId(event.target.value)}><option value="">Sans créneau</option>{courseDays.filter((day) => day.can_edit || day.id === Number(courseDayId)).map((day) => <option key={day.id} value={day.id}>{dateTime(day.scheduled_at)} · {day.title}</option>)}</select></label>
                  <label>Date limite<input type="datetime-local" value={dueDate} onChange={(event) => setDueDate(event.target.value)} required /></label>
                </div>
                {brief ? (
                  <>
                    <AssignmentBriefEditor brief={brief} onChange={setBrief} />
                    <button
                      className="dsh-btn dsh-btn--ghost dsh-btn--sm"
                      type="button"
                      onClick={() => {
                        setInstructions(assignmentBriefToText(brief))
                        setBrief(null)
                      }}
                    >
                      Revenir à une consigne libre
                    </button>
                  </>
                ) : (
                  <>
                    <label>Consignes<textarea className="teacher-long-textarea" value={instructions} onChange={(event) => setInstructions(event.target.value)} /></label>
                    <button className="dsh-btn dsh-btn--ghost dsh-btn--sm" type="button" onClick={() => setBrief(emptyAssignmentBrief())}>
                      Structurer en fiche TP
                    </button>
                  </>
                )}
                <label className="teacher-check-row"><input type="checkbox" checked={finalProject} onChange={(event) => setFinalProject(event.target.checked)} /> Projet final</label>
                {editing?.publication_status === 'published' && <span className="dsh-list-item__meta">Ce devoir est publié : les étudiants seront prévenus de vos modifications.</span>}
                {error && <div className="dsh-error" ref={formErrorRef}>{error}</div>}
              </section>
            </div>

            <div className="dsh-modal__footer">
              <button className="dsh-btn dsh-btn--ghost" type="button" disabled={working} onClick={closeForm}>Annuler</button>
              <button className="dsh-btn dsh-btn--primary" disabled={working || title.trim().length < 2 || !dueDate}>{working ? 'Enregistrement…' : editing ? 'Enregistrer' : 'Créer en brouillon'}</button>
            </div>
          </form>
        </div>
      )}

      {selected && (
        <div className="dsh-modal-overlay" onClick={() => setSelected(null)}>
          <div className="dsh-modal dsh-modal--large teacher-submissions-modal" onClick={(event) => event.stopPropagation()}>
            <div className="dsh-modal__header"><div><span className="section-label">Soumissions</span><h3>{selected.title}</h3></div><button className="dsh-icon-btn" type="button" onClick={() => setSelected(null)}><X size={16} /></button></div>
            <div className="teacher-submission-list">
              {submissions.map((submission) => (
                <article className="teacher-submission-row" key={submission.id}>
                  <div><strong>{submission.student_name}</strong><small>{dateTime(submission.submitted_at)}</small>{new Date(submission.submitted_at) > new Date(selected.due_date) && <span className="dsh-badge dsh-badge--red">Remis en retard</span>}</div>
                  <button className="dsh-btn dsh-btn--ghost dsh-btn--sm" type="button" onClick={() => void openAssignmentSubmission(submission.file_url).catch((cause) => setError(cause instanceof Error ? cause.message : 'Téléchargement impossible.'))}><ExternalLink size={13} /> Travail</button>
                  <div className="teacher-score-control"><input type="number" min="0" max="20" step=".5" value={scores[submission.id] ?? ''} onChange={(event) => setScores((current) => ({ ...current, [submission.id]: event.target.value }))} /><span>/20</span><button className="dsh-btn dsh-btn--outline dsh-btn--sm" type="button" onClick={() => void saveScore(submission)}>{submission.is_reviewed && <CheckCircle2 size={13} />} Enregistrer</button></div>
                  <button className="dsh-btn dsh-btn--outline dsh-btn--sm" type="button" onClick={() => void openThread(submission)}><MessageSquare size={13} /> Échanges {submission.comment_count > 0 ? `(${submission.comment_count})` : ''}</button>
                </article>
              ))}
              {submissions.length === 0 && <div className="dsh-empty">Aucune soumission reçue.</div>}
            </div>

            {threadSubmission && (
              <section className="teacher-assignment-thread">
                <h4>Échanges avec {threadSubmission.student_name}</h4>
                <div className="assignment-thread-stream">{comments.map((entry) => <div className={`assignment-message ${entry.author_role}`} key={entry.id}><strong>{entry.author_name}</strong><p>{entry.body}</p><small>{dateTime(entry.created_at)}</small></div>)}</div>
                <div className="assignment-thread-compose"><textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Votre retour…" /><button className="dsh-btn dsh-btn--primary" type="button" onClick={() => void sendComment()} disabled={!comment.trim()}>Envoyer</button></div>
              </section>
            )}
          </div>
        </div>
      )}
    </main>
  )
}
