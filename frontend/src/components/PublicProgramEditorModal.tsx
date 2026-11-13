import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react'
import { ArrowDown, ArrowUp, BookOpen, FileText, Layers3, Plus, Save, Trash2, X } from 'lucide-react'
import '../public-program-editor.css'

type ProgramLesson = {
  id: string
  title: string
}

type ProgramChapter = {
  id: string
  title: string
  lessons: ProgramLesson[]
}

type ProgramModule = {
  id: string
  title: string
  chapters: ProgramChapter[]
}

export type ProgramDocument = {
  version: 1
  intro: string
  modules: ProgramModule[]
}

type StoredProgram = {
  version: 1
  intro?: string
  modules?: Array<{
    title?: string
    chapters?: Array<{
      title?: string
      lessons?: Array<string | { title?: string }>
    } | string>
  }>
}

function uid() {
  return crypto.randomUUID()
}

function emptyModule(index: number): ProgramModule {
  return {
    id: uid(),
    title: `Module ${index + 1}`,
    chapters: [],
  }
}

export function parseProgram(value: string): ProgramDocument {
  const raw = value.trim()
  if (!raw) return { version: 1, intro: '', modules: [] }

  try {
    const parsed = JSON.parse(raw) as StoredProgram
    if (parsed?.version === 1 && Array.isArray(parsed.modules)) {
      return {
        version: 1,
        intro: typeof parsed.intro === 'string' ? parsed.intro : '',
        modules: parsed.modules.map((module, moduleIndex) => ({
          id: uid(),
          title: typeof module?.title === 'string' && module.title.trim()
            ? module.title
            : `Module ${moduleIndex + 1}`,
          chapters: Array.isArray(module?.chapters)
            ? module.chapters.map((chapter, chapterIndex) => {
                if (typeof chapter === 'string') {
                  return {
                    id: uid(),
                    title: chapter,
                    lessons: [],
                  }
                }
                return {
                  id: uid(),
                  title: typeof chapter?.title === 'string' && chapter.title.trim()
                    ? chapter.title
                    : `Chapitre ${chapterIndex + 1}`,
                  lessons: Array.isArray(chapter?.lessons)
                    ? chapter.lessons.map((lesson, lessonIndex) => ({
                        id: uid(),
                        title: typeof lesson === 'string'
                          ? lesson
                          : typeof lesson?.title === 'string' && lesson.title.trim()
                            ? lesson.title
                            : `Leçon ${lessonIndex + 1}`,
                      }))
                    : [],
                }
              })
            : [],
        })),
      }
    }
  } catch {
    // Legacy plain text becomes the optional public introduction.
  }

  return { version: 1, intro: raw, modules: [] }
}

export function serializeProgram(document: ProgramDocument) {
  const modules = document.modules
    .map((module) => ({
      title: module.title.trim(),
      chapters: module.chapters
        .map((chapter) => ({
          title: chapter.title.trim(),
          lessons: chapter.lessons
            .map((lesson) => ({ title: lesson.title.trim() }))
            .filter((lesson) => lesson.title.length > 0),
        }))
        .filter((chapter) => chapter.title.length > 0),
    }))
    .filter((module) => module.title.length > 0)

  return JSON.stringify({
    version: 1,
    intro: document.intro.trim(),
    modules,
  })
}

export function summarizePublicProgram(value: string) {
  const document = parseProgram(value)
  const chapterCount = document.modules.reduce((sum, module) => sum + module.chapters.length, 0)
  const lessonCount = document.modules.reduce(
    (sum, module) => sum + module.chapters.reduce((chapterSum, chapter) => chapterSum + chapter.lessons.length, 0),
    0,
  )
  return {
    moduleCount: document.modules.length,
    chapterCount,
    lessonCount,
    hasLegacyIntroOnly: document.modules.length === 0 && document.intro.trim().length > 0,
  }
}

function moveItem<T>(items: T[], index: number, direction: -1 | 1) {
  const target = index + direction
  if (target < 0 || target >= items.length) return items
  const next = [...items]
  ;[next[index], next[target]] = [next[target], next[index]]
  return next
}

export function PublicProgramEditorModal({
  open,
  value,
  onClose,
  onSave,
}: {
  open: boolean
  value: string
  onClose: () => void
  onSave: (value: string) => Promise<void>
}) {
  const [document, setDocument] = useState<ProgramDocument>(() => parseProgram(value))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setDocument(parseProgram(value))
    setError('')
  }, [open, value])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !saving) onClose()
    }
    window.document.body.classList.add('public-program-modal-open')
    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.document.body.classList.remove('public-program-modal-open')
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [open, onClose, saving])

  const totals = useMemo(() => ({
    modules: document.modules.length,
    chapters: document.modules.reduce((sum, module) => sum + module.chapters.length, 0),
    lessons: document.modules.reduce(
      (sum, module) => sum + module.chapters.reduce((chapterSum, chapter) => chapterSum + chapter.lessons.length, 0),
      0,
    ),
  }), [document])

  if (!open) return null

  async function save() {
    const serialized = serializeProgram(document)
    if (serialized.length > 30_000) {
      setError('Le programme est trop volumineux. Réduisez certains intitulés avant d’enregistrer.')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onSave(serialized)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible d’enregistrer le programme public.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="public-program-modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !saving) onClose()
    }}>
      <section className="public-program-modal" role="dialog" aria-modal="true" aria-labelledby="public-program-title">
        <header className="public-program-modal-header">
          <div>
            <span className="section-label">Programme visible sur le site</span>
            <h2 id="public-program-title">Structurer le programme public</h2>
            <p>Présentez clairement le parcours au visiteur. Ceci ne remplace pas le contenu pédagogique créé par les enseignants.</p>
          </div>
          <button type="button" className="public-program-icon-button" onClick={onClose} disabled={saving} aria-label="Fermer">
            <X size={20} />
          </button>
        </header>

        <div className="public-program-modal-summary" aria-label="Résumé du programme">
          <span><Layers3 size={16} /><strong>{totals.modules}</strong> module(s)</span>
          <span><BookOpen size={16} /><strong>{totals.chapters}</strong> chapitre(s)</span>
          <span><FileText size={16} /><strong>{totals.lessons}</strong> leçon(s)</span>
        </div>

        <div className="public-program-modal-body">
          <PublicProgramBuilder document={document} setDocument={setDocument} />

          {error && <div className="form-error">{error}</div>}
        </div>

        <footer className="public-program-modal-footer">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Annuler</button>
          <button type="button" className="primary-button" onClick={() => void save()} disabled={saving}>
            <Save size={15} /> {saving ? 'Enregistrement…' : 'Enregistrer le programme'}
          </button>
        </footer>
      </section>
    </div>
  )
}


/** The intro and the Module > Chapitre > Leçon accordion of a formation's public page, to edit. */
export function PublicProgramBuilder({
  document,
  setDocument,
}: {
  document: ProgramDocument
  setDocument: Dispatch<SetStateAction<ProgramDocument>>
}) {
  const updateModule = (moduleId: string, updater: (module: ProgramModule) => ProgramModule) => {
    setDocument((current) => ({
      ...current,
      modules: current.modules.map((module) => module.id === moduleId ? updater(module) : module),
    }))
  }

  return (
    <>
    <label className="public-program-intro-field">
      <span>Introduction du programme <small>(facultatif)</small></span>
      <textarea
        rows={3}
        value={document.intro}
        onChange={(event) => setDocument((current) => ({ ...current, intro: event.target.value }))}
        placeholder="Ex. Un parcours progressif de la découverte des fondamentaux jusqu’au projet final."
        maxLength={3000}
      />
      <small>Ce texte apparaît juste avant l’accordéon sur la fiche publique.</small>
    </label>

    <div className="public-program-builder">
      {document.modules.map((module, moduleIndex) => (
        <article className="public-program-module" key={module.id}>
          <header className="public-program-module-header">
            <span className="public-program-index">Module {moduleIndex + 1}</span>
            <input
              value={module.title}
              onChange={(event) => updateModule(module.id, (current) => ({ ...current, title: event.target.value }))}
              placeholder="Titre du module"
              maxLength={180}
              aria-label={`Titre du module ${moduleIndex + 1}`}
            />
            <div className="public-program-row-actions">
              <button type="button" title="Monter" disabled={moduleIndex === 0} onClick={() => setDocument((current) => ({ ...current, modules: moveItem(current.modules, moduleIndex, -1) }))}><ArrowUp size={15} /></button>
              <button type="button" title="Descendre" disabled={moduleIndex === document.modules.length - 1} onClick={() => setDocument((current) => ({ ...current, modules: moveItem(current.modules, moduleIndex, 1) }))}><ArrowDown size={15} /></button>
              <button type="button" className="is-danger" title="Supprimer le module" onClick={() => setDocument((current) => ({ ...current, modules: current.modules.filter((item) => item.id !== module.id) }))}><Trash2 size={15} /></button>
            </div>
          </header>

          <div className="public-program-chapters">
            {module.chapters.map((chapter, chapterIndex) => (
              <section className="public-program-chapter" key={chapter.id}>
                <div className="public-program-chapter-header">
                  <span>Chapitre {chapterIndex + 1}</span>
                  <input
                    value={chapter.title}
                    onChange={(event) => updateModule(module.id, (current) => ({
                      ...current,
                      chapters: current.chapters.map((item) => item.id === chapter.id ? { ...item, title: event.target.value } : item),
                    }))}
                    placeholder="Titre du chapitre"
                    maxLength={180}
                    aria-label={`Titre du chapitre ${chapterIndex + 1}`}
                  />
                  <div className="public-program-row-actions">
                    <button type="button" title="Monter" disabled={chapterIndex === 0} onClick={() => updateModule(module.id, (current) => ({ ...current, chapters: moveItem(current.chapters, chapterIndex, -1) }))}><ArrowUp size={14} /></button>
                    <button type="button" title="Descendre" disabled={chapterIndex === module.chapters.length - 1} onClick={() => updateModule(module.id, (current) => ({ ...current, chapters: moveItem(current.chapters, chapterIndex, 1) }))}><ArrowDown size={14} /></button>
                    <button type="button" className="is-danger" title="Supprimer le chapitre" onClick={() => updateModule(module.id, (current) => ({ ...current, chapters: current.chapters.filter((item) => item.id !== chapter.id) }))}><Trash2 size={14} /></button>
                  </div>
                </div>

                <div className="public-program-lessons">
                  {chapter.lessons.map((lesson, lessonIndex) => (
                    <div className="public-program-lesson" key={lesson.id}>
                      <span>Leçon {lessonIndex + 1}</span>
                      <input
                        value={lesson.title}
                        onChange={(event) => updateModule(module.id, (current) => ({
                          ...current,
                          chapters: current.chapters.map((item) => item.id === chapter.id
                            ? {
                                ...item,
                                lessons: item.lessons.map((currentLesson) => currentLesson.id === lesson.id
                                  ? { ...currentLesson, title: event.target.value }
                                  : currentLesson),
                              }
                            : item),
                        }))}
                        placeholder="Titre de la leçon"
                        maxLength={180}
                        aria-label={`Titre de la leçon ${lessonIndex + 1}`}
                      />
                      <div className="public-program-row-actions">
                        <button type="button" title="Monter" disabled={lessonIndex === 0} onClick={() => updateModule(module.id, (current) => ({
                          ...current,
                          chapters: current.chapters.map((item) => item.id === chapter.id ? { ...item, lessons: moveItem(item.lessons, lessonIndex, -1) } : item),
                        }))}><ArrowUp size={13} /></button>
                        <button type="button" title="Descendre" disabled={lessonIndex === chapter.lessons.length - 1} onClick={() => updateModule(module.id, (current) => ({
                          ...current,
                          chapters: current.chapters.map((item) => item.id === chapter.id ? { ...item, lessons: moveItem(item.lessons, lessonIndex, 1) } : item),
                        }))}><ArrowDown size={13} /></button>
                        <button type="button" className="is-danger" title="Supprimer la leçon" onClick={() => updateModule(module.id, (current) => ({
                          ...current,
                          chapters: current.chapters.map((item) => item.id === chapter.id ? { ...item, lessons: item.lessons.filter((currentLesson) => currentLesson.id !== lesson.id) } : item),
                        }))}><Trash2 size={13} /></button>
                      </div>
                    </div>
                  ))}

                  <button type="button" className="public-program-add-inline" onClick={() => updateModule(module.id, (current) => ({
                    ...current,
                    chapters: current.chapters.map((item) => item.id === chapter.id
                      ? { ...item, lessons: [...item.lessons, { id: uid(), title: `Leçon ${item.lessons.length + 1}` }] }
                      : item),
                  }))}>
                    <Plus size={14} /> Ajouter une leçon
                  </button>
                </div>
              </section>
            ))}

            <button type="button" className="public-program-add-chapter" onClick={() => updateModule(module.id, (current) => ({
              ...current,
              chapters: [...current.chapters, {
                id: uid(),
                title: `Chapitre ${current.chapters.length + 1}`,
                lessons: [],
              }],
            }))}>
              <Plus size={15} /> Ajouter un chapitre
            </button>
          </div>
        </article>
      ))}

      <button type="button" className="public-program-add-module" onClick={() => setDocument((current) => ({ ...current, modules: [...current.modules, emptyModule(current.modules.length)] }))}>
        <Plus size={16} /> Ajouter un module
      </button>
    </div>

    {document.modules.length === 0 && (
      <div className="public-program-empty">
        <Layers3 size={26} />
        <strong>Aucun module public</strong>
        <p>Ajoutez votre premier module pour construire l’accordéon présenté aux futurs apprenants.</p>
      </div>
    )}
    </>
  )
}
