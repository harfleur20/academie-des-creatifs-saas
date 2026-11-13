import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { ChevronDown, GraduationCap, Save } from 'lucide-react'
import {
  ApiError,
  getTeacherGradebook,
  getTeacherWorkspace,
  saveTeacherGrades,
  type TeacherGradebook,
  type TeacherWorkspaceSession,
} from '../lib/api'
import { initialTeacherSessionId } from '../lib/teacherSession'
import { PersonName } from '../components/PersonAvatar'

function errorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback
}

export function TeacherGradesPage() {
  const [sessions, setSessions] = useState<TeacherWorkspaceSession[]>([])
  const [sessionsLoaded, setSessionsLoaded] = useState(false)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [gradebook, setGradebook] = useState<TeacherGradebook | null>(null)
  const [courseDayId, setCourseDayId] = useState<number | null>(null)
  const [label, setLabel] = useState('Évaluation')
  const [maxScore, setMaxScore] = useState('20')
  const [scores, setScores] = useState<Record<number, string>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    getTeacherWorkspace().then((data) => {
      const guided = data.sessions.filter((item) => item.format_type !== 'ligne')
      setSessions(guided)
      setSessionId(initialTeacherSessionId(guided))
    }).catch((err) => setError(errorMessage(err, 'Chargement impossible.')))
      .finally(() => setSessionsLoaded(true))
  }, [])

  useEffect(() => {
    setGradebook(null)
    setCourseDayId(null)
    setScores({})
    if (sessionId) void getTeacherGradebook(sessionId).then(setGradebook).catch((err) => setError(errorMessage(err, 'Chargement impossible.')))
  }, [sessionId])

  useEffect(() => {
    const own = gradebook?.grades.filter((item) => (
      item.is_own && item.source_type === 'manual' && item.label === label.trim() && item.course_day_id === courseDayId
    )) ?? []
    if (own.length > 0) setScores(Object.fromEntries(own.map((item) => [item.enrollment_id, String(item.score)])))
  }, [gradebook, label, courseDayId])

  const selectedDay = gradebook?.course_days.find((item) => item.id === courseDayId) ?? null
  const canGrade = selectedDay ? selectedDay.can_grade : Boolean(gradebook?.can_grade_session)

  const savedGroups = useMemo(() => {
    const groups = new Map<string, TeacherGradebook['grades']>()
    gradebook?.grades.forEach((item) => {
      const key = `${item.label}|${item.course_day_id ?? 'session'}|${item.teacher_name ?? ''}`
      groups.set(key, [...(groups.get(key) ?? []), item])
    })
    return [...groups.entries()]
  }, [gradebook])

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!gradebook || !sessionId) return
    const entries = gradebook.students
      .filter((item) => scores[item.enrollment_id]?.trim())
      .map((item) => ({
        enrollment_id: item.enrollment_id,
        course_day_id: courseDayId,
        label: label.trim(),
        score: Number(scores[item.enrollment_id]),
        max_score: Number(maxScore),
      }))
    setError('')
    setMessage('')
    if (entries.length === 0) {
      setError('Saisissez au moins une note.')
      return
    }
    setSaving(true)
    try {
      setGradebook(await saveTeacherGrades(sessionId, entries))
      setMessage('Notes enregistrées.')
    } catch (err) {
      setError(errorMessage(err, 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return <main className="app-page academic-page">
    <header className="app-page-header"><div><span className="page-kicker">Espace professeur</span><h1>Notes</h1><p>Notez une séance une fois terminée, ou la session après sa fin.</p></div></header>
    {error && <div className="form-error">{error}</div>}
    {message && <div className="form-success">{message}</div>}
    <label className="academic-session-select">Session<select value={sessionId ?? ''} onChange={(event) => setSessionId(Number(event.target.value))}>
      {sessions.map((item) => <option key={item.session_id} value={item.session_id}>{item.formation_title} · {item.session_label}</option>)}
    </select></label>

    {sessionsLoaded && sessions.length === 0 && <div className="app-card formation-empty"><GraduationCap size={26} /><strong>Aucune session</strong><p>Les notes concernent vos sessions live et présentiel.</p></div>}

    {gradebook && <section className="attendance-day-list teacher-grade-list">
      <form className="app-card attendance-day-card" onSubmit={(event) => void save(event)}>
        <header><div><span className="section-label">Saisie</span><h2>Saisir une évaluation</h2></div></header>
        <div className="grade-entry-fields">
          <label>Séance liée<select value={courseDayId ?? ''} onChange={(event) => setCourseDayId(event.target.value ? Number(event.target.value) : null)}>
            <option value="">Note globale de la session</option>
            {gradebook.course_days.map((item) => <option key={item.id} value={item.id}>{item.title} · {new Date(item.scheduled_at).toLocaleDateString('fr-FR')}</option>)}
          </select></label>
          <label>Intitulé<input value={label} onChange={(event) => setLabel(event.target.value)} maxLength={180} required placeholder="Examen mi-parcours" /></label>
          <label>Barème<input type="number" min={1} value={maxScore} onChange={(event) => setMaxScore(event.target.value)} required /></label>
        </div>
        {!canGrade && <p className="muted-note">Les notes ouvrent après la séance concernée, si vous en êtes le professeur, et les notes globales après la fin de la session.</p>}
        {canGrade && gradebook.students.length === 0 && <p className="muted-note">Aucun étudiant inscrit.</p>}
        {canGrade && gradebook.students.length > 0 && <>
          <div className="attendance-table">
            {gradebook.students.map((item) => <div className="attendance-row" key={item.enrollment_id}>
              <PersonName name={item.student_name} url={item.student_avatar_url} />
              <input
                className="grade-score-input"
                type="number"
                min={0}
                max={Number(maxScore) || undefined}
                step={0.5}
                placeholder="-"
                aria-label={`Note de ${item.student_name}`}
                value={scores[item.enrollment_id] ?? ''}
                onChange={(event) => setScores((current) => ({ ...current, [item.enrollment_id]: event.target.value }))}
              />
            </div>)}
          </div>
          <button className="primary-button grade-save-button" disabled={saving}><Save size={15} /> {saving ? 'Enregistrement…' : 'Enregistrer les notes'}</button>
        </>}
      </form>

      {savedGroups.map(([key, rows]) => <details className="app-card attendance-day-card grade-saved-group" key={key}>
        <summary className="grade-saved-group__summary"><div>
          <span className="section-label">{rows[0].course_day_title ?? 'Note de session'}{rows[0].teacher_name ? ` · ${rows[0].teacher_name}` : ''}</span>
          <h2>{rows[0].label}</h2>
        </div><span className="grade-saved-group__meta">
          {rows.length} étudiant{rows.length > 1 ? 's' : ''}
          <ChevronDown className="grade-saved-group__chevron" size={18} aria-hidden="true" />
        </span></summary>
        <div className="attendance-table">
          {rows.map((item) => <div className="attendance-row" key={item.id}><PersonName name={item.student_name} url={item.student_avatar_url} /><span>{item.score} / {item.max_score}</span></div>)}
        </div>
      </details>)}
    </section>}
  </main>
}
