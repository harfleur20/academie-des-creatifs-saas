import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { ArrowLeft, ArrowRight, MapPin, MonitorPlay, Plus, Radio, X } from 'lucide-react'
import { ApiError, createFormation, type FormationSummary } from '../lib/api'
import { CharacterCounter } from './CharacterCounter'
import { characterCount, exceedsCharacterLimit, FORMATION_CHARACTER_LIMITS } from '../lib/characterLimits'
import { getProgramCharacterLimitIssues, parseProgram, PublicProgramBuilder, serializeProgram, type ProgramDocument } from './PublicProgramEditorModal'
import '../public-program-editor.css'
import '../new-formation-dialog.css'

type Format = 'ligne' | 'live' | 'presentiel'

const FORMATS: Array<{ value: Format; label: string; text: string; icon: typeof Radio }> = [
  { value: 'ligne', label: 'En ligne', text: 'Un parcours que l’étudiant suit à son rythme.', icon: MonitorPlay },
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

/**
 * A new formation in two steps: what it is, then the modules and lessons of its public page.
 * Everything else (photo, price, sessions…) is filled in on the formation's own page.
 */
export function NewFormationDialog({
  open,
  existing,
  onClose,
  onCreated,
}: {
  open: boolean
  existing: FormationSummary[]
  onClose: () => void
  onCreated: (formation: FormationSummary) => void
}) {
  const [step, setStep] = useState<1 | 2>(1)
  const [title, setTitle] = useState('')
  const [format, setFormat] = useState<Format>('ligne')
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

  useEffect(() => {
    if (!open) return
    setStep(1)
    setTitle('')
    setFormat('ligne')
    setCategory('')
    setCustomCategory('')
    setLevel('')
    setHours('')
    setSummary('')
    setProgram(parseProgram(''))
    setError('')
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape' && !saving) onClose() }
    window.document.body.classList.add('public-program-modal-open')
    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.document.body.classList.remove('public-program-modal-open')
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [open, onClose, saving])

  if (!open) return null

  const chosenCategory = category === OTHER ? customCategory.trim() : category
  const programLimitIssues = getProgramCharacterLimitIssues(program)
  const serializedProgram = serializeProgram(program)
  const serializedProgramTooLong = characterCount(serializedProgram) > FORMATION_CHARACTER_LIMITS.serializedProgram

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
  }

  async function create(withProgram: boolean) {
    const program_value = withProgram ? serializeProgram(program) : ''
    if (withProgram && programLimitIssues.length > 0) {
      setError(programLimitIssues[0])
      return
    }
    if (withProgram && characterCount(program_value) > FORMATION_CHARACTER_LIMITS.serializedProgram) {
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
        public_program: program_value,
      })
      onCreated(formation)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Création impossible.')
    } finally {
      setSaving(false)
    }
  }

  const lessons = program.modules.reduce(
    (sum, module) => sum + module.chapters.reduce((chapterSum, chapter) => chapterSum + chapter.lessons.length, 0), 0,
  )

  return (
    <div className="public-program-modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !saving) onClose()
    }}>
      <section className="public-program-modal new-formation-dialog" role="dialog" aria-modal="true" aria-labelledby="new-formation-title">
        <header className="public-program-modal-header">
          <div>
            <span className="section-label">Nouvelle formation</span>
            <h2 id="new-formation-title">{step === 1 ? 'L’essentiel' : 'Le programme'}</h2>
            <p>
              {step === 1
                ? 'Le nom et le format suffisent pour commencer. Le reste se complète ensuite, sur la page de la formation.'
                : 'Les modules et les leçons apparaîtront en accordéon sur la page publique. Vous pourrez les modifier à tout moment.'}
            </p>
          </div>
          <button type="button" className="public-program-icon-button" onClick={onClose} disabled={saving} aria-label="Fermer">
            <X size={20} />
          </button>
        </header>

        <ol className="new-formation-steps" aria-label="Étapes">
          <li className={step === 1 ? 'is-current' : 'is-done'}><span>1</span> L’essentiel</li>
          <li className={step === 2 ? 'is-current' : ''}><span>2</span> Le programme</li>
        </ol>

        {step === 1 ? (
          <form className="new-formation-form" onSubmit={next}>
            <div className="public-program-modal-body">
              <label>
                <span>Nom de la formation</span>
                <input value={title} onChange={(event) => setTitle(event.target.value)} required placeholder="Ex. Motion design avec After Effects" autoFocus />
                <CharacterCounter value={title} limit={FORMATION_CHARACTER_LIMITS.title} />
              </label>

              <fieldset className="new-formation-formats">
                <legend>Format</legend>
                {FORMATS.map(({ value, label, text, icon: Icon }) => (
                  <label key={value} className={format === value ? 'is-selected' : undefined}>
                    <input type="radio" name="format" value={value} checked={format === value} onChange={() => setFormat(value)} />
                    <Icon size={20} />
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
                <small>Affiché sur les cartes du catalogue et en tête de la page publique.</small>
              </label>

              {error && <div className="form-error">{error}</div>}
            </div>
            <footer className="public-program-modal-footer">
              <button type="button" className="secondary-button" onClick={onClose}>Annuler</button>
              <button type="submit" className="primary-button">Suivant : le programme <ArrowRight size={15} /></button>
            </footer>
          </form>
        ) : (
          <>
            <div className="public-program-modal-summary" aria-label="Résumé du programme">
              <span><strong>{program.modules.length}</strong> module(s)</span>
              <span><strong>{lessons}</strong> leçon(s)</span>
            </div>
            <div className="public-program-modal-body">
              <PublicProgramBuilder document={program} setDocument={setProgram} />
              {(programLimitIssues[0] || serializedProgramTooLong) && (
                <div className="form-error">{programLimitIssues[0] || 'Le programme dépasse la taille maximale autorisée.'}</div>
              )}
              {error && <div className="form-error">{error}</div>}
            </div>
            <footer className="public-program-modal-footer">
              <button type="button" className="secondary-button" onClick={() => setStep(1)} disabled={saving}><ArrowLeft size={15} /> Retour</button>
              <span className="new-formation-footer-spacer" />
              <button type="button" className="secondary-button" onClick={() => void create(false)} disabled={saving}>Créer sans programme</button>
              <button type="button" className="primary-button" onClick={() => void create(true)} disabled={saving || program.modules.length === 0 || programLimitIssues.length > 0 || serializedProgramTooLong}>
                <Plus size={15} /> {saving ? 'Création…' : 'Créer la formation'}
              </button>
            </footer>
          </>
        )}
      </section>
    </div>
  )
}
