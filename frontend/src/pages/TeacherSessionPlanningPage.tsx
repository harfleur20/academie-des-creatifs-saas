import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  ArrowLeft,
  CalendarClock,
  Clock3,
  Plus,
  UserRound,
  X,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import {
  ApiError,
  createSessionCourseDay,
  getSessionPlanning,
  updateSessionCourseDay,
  type SessionPlanning,
} from '../lib/api'

function toLocalInput(value: string) {
  const date = new Date(value)
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

export function TeacherSessionPlanningPage() {
  const { sessionId } = useParams()
  const id = Number(sessionId)
  const [planning, setPlanning] = useState<SessionPlanning | null>(null)
  const [title, setTitle] = useState('')
  const [scheduledAt, setScheduledAt] = useState('')
  const [duration, setDuration] = useState('90')
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')

  async function refresh() {
    if (!Number.isInteger(id)) return
    try {
      setPlanning(await getSessionPlanning(id))
      setError('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de charger le planning.')
    }
  }

  useEffect(() => {
    void refresh()
  }, [id])

  const activeDays = useMemo(
    () => planning?.course_days.filter((item) => item.status !== 'cancelled') ?? [],
    [planning],
  )

  async function create(event: FormEvent) {
    event.preventDefault()
    if (!planning || !scheduledAt) return
    setWorking(true)
    setError('')
    try {
      const updated = await createSessionCourseDay(planning.session_id, {
        title: title.trim(),
        scheduled_at: new Date(scheduledAt).toISOString(),
        duration_minutes: Number(duration),
      })
      setPlanning(updated)
      setTitle('')
      setScheduledAt('')
      setDuration('90')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Création impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function cancelDay(dayId: number) {
    setWorking(true)
    setError('')
    try {
      setPlanning(await updateSessionCourseDay(dayId, { status: 'cancelled' }))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Modification impossible.')
    } finally {
      setWorking(false)
    }
  }

  if (!planning && !error) {
    return <div className="page-state">Chargement du planning…</div>
  }

  return (
    <main className="app-page planning-page">
      <Link className="planning-back-link" to="/app/teacher/sessions">
        <ArrowLeft size={15} /> Mes sessions
      </Link>

      {planning && (
        <header className="app-page-header">
          <div>
            <span className="page-kicker">Planning pédagogique</span>
            <h1>{planning.formation_title}</h1>
            <p>
              {planning.session_label} · du{' '}
              {new Date(planning.session_start_date).toLocaleDateString('fr-FR')} au{' '}
              {new Date(planning.session_end_date).toLocaleDateString('fr-FR')}
            </p>
          </div>
          <span className="status-chip">{activeDays.length} séance(s)</span>
        </header>
      )}

      {error && <div className="form-error">{error}</div>}

      {planning && (
        <section className="planning-layout">
          <form className="app-card planning-create-card" onSubmit={create}>
            <div>
              <span className="section-label">Mon créneau</span>
              <h2>Planifier une séance</h2>
              <p>
                Ce créneau vous appartiendra. Les autres professeurs de la session pourront
                le voir mais pas le modifier.
              </p>
            </div>

            <label>
              Titre de la séance
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                minLength={2}
                maxLength={255}
                required
                placeholder="Ex. Principes du mouvement"
              />
            </label>

            <label>
              Date et heure
              <input
                type="datetime-local"
                value={scheduledAt}
                onChange={(event) => setScheduledAt(event.target.value)}
                min={`${planning.session_start_date}T00:00`}
                max={`${planning.session_end_date}T23:59`}
                required
              />
            </label>

            <label>
              Durée
              <select value={duration} onChange={(event) => setDuration(event.target.value)}>
                <option value="60">1 h</option>
                <option value="90">1 h 30</option>
                <option value="120">2 h</option>
                <option value="180">3 h</option>
                <option value="240">4 h</option>
              </select>
            </label>

            <button className="primary-button" disabled={working}>
              <Plus size={15} />
              {working ? 'Enregistrement…' : 'Ajouter au planning'}
            </button>
          </form>

          <section className="planning-list">
            {planning.course_days.map((day) => (
              <article
                className={`app-card planning-day-card ${day.status === 'cancelled' ? 'is-cancelled' : ''}`}
                key={day.id}
              >
                <div className="planning-day-date">
                  <strong>
                    {new Intl.DateTimeFormat('fr-FR', { day: '2-digit' }).format(new Date(day.scheduled_at))}
                  </strong>
                  <span>
                    {new Intl.DateTimeFormat('fr-FR', { month: 'short' }).format(new Date(day.scheduled_at))}
                  </span>
                </div>
                <div className="planning-day-main">
                  <div>
                    <span className="section-label">{day.status === 'cancelled' ? 'Annulée' : 'Planifiée'}</span>
                    <h3>{day.title}</h3>
                  </div>
                  <div className="planning-day-meta">
                    <span><Clock3 size={14} /> {new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' }).format(new Date(day.scheduled_at))} · {day.duration_minutes} min</span>
                    <span><UserRound size={14} /> {day.teacher_name || 'Professeur non disponible'}</span>
                  </div>
                </div>
                {day.can_edit && day.status !== 'cancelled' && (
                  <button
                    className="planning-cancel-button"
                    type="button"
                    disabled={working}
                    onClick={() => void cancelDay(day.id)}
                    title="Annuler cette séance"
                  >
                    <X size={16} />
                  </button>
                )}
              </article>
            ))}

            {planning.course_days.length === 0 && (
              <div className="app-card formation-empty">
                <CalendarClock size={28} />
                <strong>Aucune séance planifiée</strong>
                <p>Ajoutez votre premier créneau pour construire le planning commun.</p>
              </div>
            )}
          </section>
        </section>
      )}
    </main>
  )
}
