import { useMemo, useState, type FormEvent } from 'react'
import { ArrowLeft, ArrowRight, BookOpen, MapPin, Plus, Radio } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ApiError, createFormation, type FormationSummary } from '../lib/api'
import { CharacterCounter } from '../components/CharacterCounter'
import { characterCount, exceedsCharacterLimit, FORMATION_CHARACTER_LIMITS } from '../lib/characterLimits'
import { getProgramCharacterLimitIssues, parseProgram, PublicProgramBuilder, serializeProgram, type ProgramDocument } from '../components/PublicProgramEditorModal'
import '../public-program-editor.css'
import './new-formation-page.css'

// Online formations (recorded videos) wait for their own editor and protected video hosting:
// schools create live and onsite formations; those already online keep working.
type Format = 'live' | 'presentiel'

const FORMATS: Array<{ value: Format; label: string; text: string; icon: typeof Radio }> = [
  { value: 'live', label: 'En live', text: 'Des cours en direct dans la plateforme, par session.', icon: Radio },
  { value: 'presentiel', label: 'En présentiel', text: 'Des séances en salle, avec planning et présences.', icon: MapPin },
]

const SUGGESTED_CATEGORIES = [
  'Design & graphisme', 'Photo & vidéo', 'Animation & motion design', 'Communication & marketing',
  'Développement & numérique', 'Musique & audio', 'Mode & artisanat', 'Entrepreneuriat', 'Langues',
]
const SUGGESTED_LEVELS = ['Tous niveaux', 'Initiation', 'Débutant', 'Intermédiaire', 'Avancé', 'Expert']
const OTHER = '__other__'

function slugify(value: string) {
  return value.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
}

function unique(values: string[]) {
  return values.map((value) => value.trim()).filter((value, index, items) => value && items.indexOf(value) === index)
}

export function NewFormationPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const existing = (location.state as { existing?: FormationSummary[] } | null)?.existing ?? []
  const [step, setStep] = useState<1 | 2>(1)
  const [title, setTitle] = useState('')
  const [format, setFormat] = useState<Format>('live')
  const [category, setCategory] = useState('')
  const [customCategory, setCustomCategory] = useState('')
  const [level, setLevel] = useState('')
  const [hours, setHours] = useState('')
  const [summary, setSummary] = useState('')
  const [program, setProgram] = useState<ProgramDocument>(() => parseProgram(''))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const categories = useMemo(() => unique([...SUGGESTED_CATEGORIES, ...existing.map((item) => item.category)])
    .filter((item) => characterCount(item) <= FORMATION_CHARACTER_LIMITS.category), [existing])
  const levels = useMemo(() => unique([...SUGGESTED_LEVELS, ...existing.map((item) => item.level)])
    .filter((item) => characterCount(item) <= FORMATION_CHARACTER_LIMITS.level), [existing])

  const chosenCategory = category === OTHER ? customCategory.trim() : category
  const programLimitIssues = getProgramCharacterLimitIssues(program)
  const serializedProgram = serializeProgram(program)
  const serializedProgramTooLong = characterCount(serializedProgram) > FORMATION_CHARACTER_LIMITS.serializedProgram
  const lessons = program.modules.reduce(
    (sum, module) => sum + module.chapters.reduce((chapterSum, chapter) => chapterSum + chapter.lessons.length, 0), 0,
  )

  function next(event: FormEvent) {
    event.preventDefault()
    if (
      exceedsCharacterLimit(title, FORMATION_CHARACTER_LIMITS.title)
      || (category === OTHER && exceedsCharacterLimit(customCategory, FORMATION_CHARACTER_LIMITS.category))
      || exceedsCharacterLimit(summary, FORMATION_CHARACTER_LIMITS.shortDescription)
    ) {
      setError('Raccourcissez les champs signalés avant de continuer.')
      return
    }
    if (!slugify(title)) {
      setError('Donnez un nom à la formation.')
      return
    }
    setError('')
    setStep(2)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function create(withProgram: boolean) {
    const programValue = withProgram ? serializeProgram(program) : ''
    if (withProgram && programLimitIssues.length > 0) {
      setError(programLimitIssues[0])
      return
    }
    if (withProgram && characterCount(programValue) > FORMATION_CHARACTER_LIMITS.serializedProgram) {
      setError('Le programme est trop volumineux. Réduisez-le avant de créer la formation.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const formation = await createFormation({
        slug: slugify(title),
        title: title.trim(),
        format_type: format,
        category: chosenCategory,
        level,
        training_hours: hours ? Number(hours) : null,
        short_description: summary.trim(),
        public_program: programValue,
      })
      navigate(`/app/manage/formations/${formation.id}?nouvelle=1`, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Création impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="app-page new-formation-page">
      <Link className="new-formation-back" to="/app/manage/formations">
        <ArrowLeft size={17} aria-hidden="true" /> Retour aux formations
      </Link>

      <section className="new-formation-panel" aria-labelledby="new-formation-title">
        <header className="new-formation-header">
          <div>
            <span className="page-kicker">Nouvelle formation</span>
            <h1 id="new-formation-title">{step === 1 ? 'L’essentiel' : 'Le programme'}</h1>
            <p>
              {step === 1
                ? 'Posez les bases de votre formation. Vous pourrez compléter les autres détails ensuite.'
                : 'Organisez vos modules, chapitres et leçons. Vous pourrez modifier ce programme à tout moment.'}
            </p>
          </div>
          <span className="new-formation-step-count">Étape {step} sur 2</span>
        </header>

        <nav className="new-formation-progress" aria-label="Étapes de création">
          <ol className="new-formation-steps">
            <li className={step === 1 ? 'is-current' : 'is-done'}>
              <span>1</span><div><strong>L’essentiel</strong><small>Nom et format</small></div>
            </li>
            <li className={step === 2 ? 'is-current' : ''}>
              <span>2</span><div><strong>Le programme</strong><small>Modules et leçons</small></div>
            </li>
          </ol>
          <div className="new-formation-progress-track" role="progressbar" aria-valuemin={1} aria-valuemax={2} aria-valuenow={step} aria-label={`Étape ${step} sur 2`}>
            <span style={{ width: step === 1 ? '50%' : '100%' }} />
          </div>
        </nav>

        {step === 1 ? (
          <form className="new-formation-form" onSubmit={next}>
            <div className="new-formation-page-content">
              <div className="new-formation-section-heading">
                <span className="new-formation-section-icon"><BookOpen size={19} /></span>
                <div><h2>Définissez votre formation</h2><p>Ces informations serviront à organiser et présenter votre offre.</p></div>
              </div>

              <label>
                <span>Nom de la formation</span>
                <input value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={FORMATION_CHARACTER_LIMITS.title} placeholder="Ex. Motion design avec After Effects" autoFocus />
                <CharacterCounter value={title} limit={FORMATION_CHARACTER_LIMITS.title} />
              </label>

              <fieldset className="new-formation-formats">
                <legend>Format</legend>
                {FORMATS.map(({ value, label, text, icon: Icon }) => (
                  <label key={value} className={format === value ? 'is-selected' : undefined}>
                    <input type="radio" name="format" value={value} checked={format === value} onChange={() => setFormat(value)} />
                    <Icon size={21} aria-hidden="true" />
                    <strong>{label}</strong>
                    <small>{text}</small>
                  </label>
                ))}
              </fieldset>

              <div className="new-formation-grid">
                <label>
                  <span>Catégorie</span>
                  <select value={category} onChange={(event) => setCategory(event.target.value)} required>
                    <option value="" disabled>Choisir une catégorie</option>
                    {categories.map((item) => <option key={item} value={item}>{item}</option>)}
                    <option value={OTHER}>Autre catégorie…</option>
                  </select>
                </label>
                <label>
                  <span>Niveau</span>
                  <select value={level} onChange={(event) => setLevel(event.target.value)} required>
                    <option value="" disabled>Choisir un niveau</option>
                    {levels.map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                </label>
                {category === OTHER && (
                  <label>
                    <span>Nouvelle catégorie</span>
                    <input value={customCategory} onChange={(event) => setCustomCategory(event.target.value)} required placeholder="Nom de la catégorie" />
                    <CharacterCounter value={customCategory} limit={FORMATION_CHARACTER_LIMITS.category} />
                  </label>
                )}
                <label>
                  <span>Volume horaire <small>(facultatif)</small></span>
                  <input type="number" min={1} max={10000} value={hours} onChange={(event) => setHours(event.target.value)} placeholder="Ex. 40" />
                </label>
              </div>

              <label>
                <span>Résumé court <small>(facultatif)</small></span>
                <textarea value={summary} onChange={(event) => setSummary(event.target.value)} rows={3} placeholder="Ex. En 6 semaines, apprenez à animer logos et textes pour les réseaux sociaux." />
                <CharacterCounter value={summary} limit={FORMATION_CHARACTER_LIMITS.shortDescription} />
                <small>Ce texte apparaîtra sur la carte du catalogue et en tête de la page publique.</small>
              </label>
              {error && <div className="form-error" role="alert">{error}</div>}
            </div>

            <footer className="new-formation-page-footer">
              <Link className="secondary-button" to="/app/manage/formations">Annuler</Link>
              <button type="submit" className="primary-button">Continuer vers le programme <ArrowRight size={16} /></button>
            </footer>
          </form>
        ) : (
          <>
            <div className="new-formation-page-content new-formation-program-content">
              <div className="new-formation-program-summary">
                <div className="new-formation-section-heading">
                  <span className="new-formation-section-icon"><BookOpen size={19} /></span>
                  <div><h2>Construisez un parcours clair</h2><p>La structure aide vos étudiants à suivre leur progression.</p></div>
                </div>
                <div className="new-formation-program-stats">
                  <span><strong>{program.modules.length}</strong> modules</span>
                  <span><strong>{lessons}</strong> leçons</span>
                  <span className="new-formation-program-title">{title.trim()}</span>
                </div>
              </div>
              <PublicProgramBuilder document={program} setDocument={setProgram} />
              {(programLimitIssues[0] || serializedProgramTooLong) && (
                <div className="form-error" role="alert">{programLimitIssues[0] || 'Le programme dépasse la taille maximale autorisée.'}</div>
              )}
              {error && <div className="form-error" role="alert">{error}</div>}
            </div>
            <footer className="new-formation-page-footer is-program-step">
              <button type="button" className="secondary-button" onClick={() => { setError(''); setStep(1); window.scrollTo({ top: 0, behavior: 'smooth' }) }} disabled={saving}>
                <ArrowLeft size={16} /> Retour à l’essentiel
              </button>
              <span className="new-formation-footer-spacer" />
              <button type="button" className="secondary-button" onClick={() => void create(false)} disabled={saving}>
                {saving ? 'Création…' : 'Créer sans programme'}
              </button>
              <button type="button" className="primary-button" onClick={() => void create(true)} disabled={saving || program.modules.length === 0 || programLimitIssues.length > 0 || serializedProgramTooLong}>
                <Plus size={16} /> {saving ? 'Création…' : 'Créer la formation'}
              </button>
            </footer>
          </>
        )}
      </section>
    </main>
  )
}
