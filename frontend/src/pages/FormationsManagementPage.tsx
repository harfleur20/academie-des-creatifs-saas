import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  ArrowRight,
  BookOpen,
  CalendarDays,
  GraduationCap,
  Plus,
  Users,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  ApiError,
  createFormation,
  listFormations,
  type FormationSummary,
} from '../lib/api'

function slugify(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

const formatLabels = {
  live: 'Live',
  ligne: 'En ligne',
  presentiel: 'Présentiel',
}

export function FormationsManagementPage() {
  const [formations, setFormations] = useState<FormationSummary[]>([])
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('')
  const [level, setLevel] = useState('')
  const [formatType, setFormatType] = useState<'live' | 'ligne' | 'presentiel'>('ligne')
  const [trainingHours, setTrainingHours] = useState('')
  const [description, setDescription] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  async function refresh() {
    try {
      setFormations(await listFormations())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de charger les formations.')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    const slug = slugify(title)
    if (!slug) return
    setCreating(true)
    setError('')
    try {
      await createFormation({
        slug,
        title: title.trim(),
        category: category.trim(),
        level: level.trim(),
        format_type: formatType,
        training_hours: trainingHours ? Number(trainingHours) : null,
        description: description.trim(),
      })
      setTitle('')
      setCategory('')
      setLevel('')
      setTrainingHours('')
      setDescription('')
      await refresh()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Création impossible.')
    } finally {
      setCreating(false)
    }
  }

  const totals = useMemo(
    () => ({
      sessions: formations.reduce((sum, item) => sum + item.session_count, 0),
      students: formations.reduce((sum, item) => sum + item.student_count, 0),
      courses: formations.reduce((sum, item) => sum + item.course_count, 0),
    }),
    [formations],
  )

  return (
    <main className="app-page formations-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Formations</span>
          <h1>Vos formations réelles</h1>
          <p>
            Créez vos programmes, ouvrez des cohortes, affectez les professeurs et
            construisez les cours.
          </p>
        </div>
      </header>

      <section className="formation-metrics">
        <article><GraduationCap size={18} /><div><strong>{formations.length}</strong><span>Formations</span></div></article>
        <article><CalendarDays size={18} /><div><strong>{totals.sessions}</strong><span>Sessions</span></div></article>
        <article><Users size={18} /><div><strong>{totals.students}</strong><span>Étudiants inscrits</span></div></article>
        <article><BookOpen size={18} /><div><strong>{totals.courses}</strong><span>Cours</span></div></article>
      </section>

      <section className="formation-layout">
        <form className="app-card formation-create-card" onSubmit={submit}>
          <div>
            <span className="section-label">Nouvelle formation</span>
            <h2>Créer un programme</h2>
          </div>

          <label>
            Nom
            <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={255} placeholder="Ex. Motion Design" />
          </label>

          <div className="formation-form-grid">
            <label>
              Catégorie
              <input value={category} onChange={(e) => setCategory(e.target.value)} maxLength={120} placeholder="Design" />
            </label>
            <label>
              Niveau
              <input value={level} onChange={(e) => setLevel(e.target.value)} maxLength={120} placeholder="Intermédiaire" />
            </label>
            <label>
              Format
              <select value={formatType} onChange={(e) => setFormatType(e.target.value as typeof formatType)}>
                <option value="ligne">En ligne</option>
                <option value="live">Live</option>
                <option value="presentiel">Présentiel</option>
              </select>
            </label>
            <label>
              Volume horaire
              <input type="number" min={1} max={10000} value={trainingHours} onChange={(e) => setTrainingHours(e.target.value)} placeholder="40" />
            </label>
          </div>

          <label>
            Description
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} maxLength={5000} />
          </label>

          {error && <div className="form-error">{error}</div>}

          <button className="primary-button" disabled={creating}>
            <Plus size={16} />
            {creating ? 'Création…' : 'Créer la formation'}
          </button>
        </form>

        <section className="formation-list">
          {formations.map((formation) => (
            <article className="formation-card" key={formation.id}>
              <div className="formation-card-head">
                <div>
                  <span className="formation-format">{formatLabels[formation.format_type]}</span>
                  <h2>{formation.title}</h2>
                  <p>{formation.description || 'Aucune description.'}</p>
                </div>
                <span className={`formation-status ${formation.status}`}>{formation.status}</span>
              </div>

              <div className="formation-card-meta">
                <span><CalendarDays size={14} /> {formation.session_count} session(s)</span>
                <span><Users size={14} /> {formation.student_count} étudiant(s)</span>
                <span><GraduationCap size={14} /> {formation.teacher_count} prof(s)</span>
                <span><BookOpen size={14} /> {formation.course_count} cours</span>
              </div>

              <Link className="secondary-button" to={`/app/manage/formations/${formation.id}`}>
                Ouvrir la formation <ArrowRight size={15} />
              </Link>
            </article>
          ))}

          {formations.length === 0 && (
            <div className="app-card formation-empty">
              <GraduationCap size={28} />
              <strong>Aucune formation</strong>
              <p>Créez votre premier programme avec le formulaire.</p>
            </div>
          )}
        </section>
      </section>
    </main>
  )
}
