import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  ArrowRight,
  BookOpen,
  CalendarDays,
  GraduationCap,
  Plus,
  Send,
  Users,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import {
  ApiError,
  createFormation,
  getOnboardingStatus,
  listFormations,
  updateFormation,
  type FormationSummary,
  type OnboardingStatus,
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

const suggestedCategories = [
  'Design & graphisme',
  'Photo & vidéo',
  'Animation & motion design',
  'Communication & marketing',
  'Développement & numérique',
  'Musique & audio',
  'Mode & artisanat',
  'Entrepreneuriat',
  'Langues',
]

const suggestedLevels = [
  'Tous niveaux',
  'Initiation',
  'Débutant',
  'Intermédiaire',
  'Avancé',
  'Expert',
]

const otherCategoryValue = '__other__'

export function FormationsManagementPage() {
  const { activeOrganization } = useTenant()
  const [formations, setFormations] = useState<FormationSummary[]>([])
  const [setup, setSetup] = useState<OnboardingStatus | null>(null)
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('')
  const [customCategory, setCustomCategory] = useState('')
  const [level, setLevel] = useState('')
  const [formatType, setFormatType] = useState<'live' | 'ligne' | 'presentiel'>('ligne')
  const [trainingHours, setTrainingHours] = useState('')
  const [description, setDescription] = useState('')
  const [creating, setCreating] = useState(false)
  const [publishingId, setPublishingId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function refresh() {
    try {
      const [items, setupStatus] = await Promise.all([listFormations(), getOnboardingStatus()])
      setFormations(items)
      setSetup(setupStatus)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de charger les formations.')
    }
  }

  useEffect(() => {
    void refresh()
  }, [activeOrganization?.id])

  async function submit(event: FormEvent) {
    event.preventDefault()
    const slug = slugify(title)
    if (!slug) return
    setCreating(true)
    setError('')
    setMessage('')
    try {
      await createFormation({
        slug,
        title: title.trim(),
        category: category === otherCategoryValue ? customCategory.trim() : category,
        level,
        format_type: formatType,
        training_hours: trainingHours ? Number(trainingHours) : null,
        description: description.trim(),
      })
      setTitle('')
      setCategory('')
      setCustomCategory('')
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

  async function publish(formation: FormationSummary) {
    setPublishingId(formation.id)
    setError('')
    setMessage('')
    try {
      const updated = await updateFormation(formation.id, { status: 'published' })
      setFormations((current) => current.map((item) => item.id === formation.id ? updated : item))
      setMessage('Formation publiée. Pour qu’elle apparaisse aux visiteurs, vérifiez aussi la publication du site public.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Publication impossible.')
    } finally {
      setPublishingId(null)
    }
  }

  const totals = useMemo(
    () => ({
      sessions: formations.reduce((sum, item) => sum + item.session_count, 0),
      online: formations.filter((item) => item.format_type === 'ligne').length,
      hasGuided: formations.some((item) => item.format_type !== 'ligne'),
      students: formations.reduce((sum, item) => sum + item.student_count, 0),
      courses: formations.reduce((sum, item) => sum + item.course_count, 0),
    }),
    [formations],
  )

  const categoryOptions = useMemo(
    () => [
      ...suggestedCategories,
      ...formations
        .map((item) => item.category.trim())
        .filter((item) => item && !suggestedCategories.includes(item))
        .filter((item, index, items) => items.indexOf(item) === index),
    ],
    [formations],
  )

  const levelOptions = useMemo(
    () => [
      ...suggestedLevels,
      ...formations
        .map((item) => item.level.trim())
        .filter((item) => item && !suggestedLevels.includes(item))
        .filter((item, index, items) => items.indexOf(item) === index),
    ],
    [formations],
  )
  const setupBlockingStep = setup?.steps.find((step) => step.key !== 'formation' && !step.completed)

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

      {message && <div className="form-success">{message} <Link to="/app/manage/site-public">Vérifier le site public</Link></div>}
      {error && <div className="form-error">{error}</div>}
      {setupBlockingStep && <div className="app-card formation-readiness"><strong>Création verrouillée</strong><p>Terminez d’abord l’étape « {setupBlockingStep.label} ».</p><Link className="secondary-button compact-action" to={setupBlockingStep.path}>Continuer cette étape <ArrowRight size={15} /></Link></div>}

      <section className="formation-metrics">
        <article><GraduationCap size={18} /><div><strong>{formations.length}</strong><span>Formations</span></div></article>
        <article><CalendarDays size={18} /><div><strong>{totals.hasGuided || totals.online === 0 ? totals.sessions : totals.online}</strong><span>{totals.hasGuided || totals.online === 0 ? 'Sessions' : 'Formations en ligne'}</span></div></article>
        <article><Users size={18} /><div><strong>{totals.students}</strong><span>Étudiants inscrits</span></div></article>
        <article><BookOpen size={18} /><div><strong>{totals.courses}</strong><span>Cours</span></div></article>
      </section>

      <section className="formation-layout">
        <form className="app-card formation-create-card" onSubmit={submit} aria-disabled={Boolean(setupBlockingStep)}>
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
              <select value={category} onChange={(e) => setCategory(e.target.value)} required>
                <option value="" disabled>Choisir une catégorie</option>
                {categoryOptions.map((item) => <option key={item} value={item}>{item}</option>)}
                <option value={otherCategoryValue}>Autre catégorie…</option>
              </select>
            </label>
            <label>
              Niveau
              <select value={level} onChange={(e) => setLevel(e.target.value)} required>
                <option value="" disabled>Choisir un niveau</option>
                {levelOptions.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            {category === otherCategoryValue && (
              <label className="formation-custom-category">
                Nouvelle catégorie
                <input
                  value={customCategory}
                  onChange={(e) => setCustomCategory(e.target.value)}
                  maxLength={120}
                  required
                  placeholder="Nom de la catégorie"
                />
              </label>
            )}
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

          <button className="primary-button" disabled={creating || !setup || Boolean(setupBlockingStep)}>
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
                <span className={`formation-status ${formation.status}`}>{formation.status === 'published' ? 'Publiée' : 'Brouillon'}</span>
              </div>

              <div className="formation-card-meta">
                <span><CalendarDays size={14} /> {formation.format_type === 'ligne' ? 'Formation en ligne' : `${formation.session_count} session(s)`}</span>
                <span><Users size={14} /> {formation.student_count} étudiant(s)</span>
                <span><GraduationCap size={14} /> {formation.teacher_count} prof(s)</span>
                <span><BookOpen size={14} /> {formation.course_count} cours</span>
              </div>
              {formation.publication_issues.length > 0 && <div className="formation-card-issues"><strong>À compléter</strong><ul>{formation.publication_issues.map((issue) => <li key={issue}>{issue}</li>)}</ul></div>}

              <div className="formation-card-actions">
                <Link className="secondary-button" to={`/app/manage/formations/${formation.id}`}>
                  Ouvrir la formation <ArrowRight size={15} />
                </Link>
                {formation.status === 'draft' && <button className="primary-button" type="button" disabled={publishingId !== null || formation.publication_issues.length > 0} onClick={() => void publish(formation)}><Send size={15} /> {publishingId === formation.id ? 'Publication…' : 'Publier la formation'}</button>}
              </div>
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
