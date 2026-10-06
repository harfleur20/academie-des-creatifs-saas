import { BookOpen, CheckCircle2, ChevronDown, FileText, Layers3 } from 'lucide-react'
import type { PublicFormationDetail } from '../lib/api'
import '../public-program-accordion.css'

type ProgramChapterView = {
  title: string
  lessons: string[]
}

type ProgramModuleView = {
  title: string
  chapters: ProgramChapterView[]
}

type StoredProgram = {
  version?: number
  intro?: unknown
  modules?: unknown
}

function cleanText(value: unknown) {
  return typeof value === 'string' ? value.trim() : ''
}

function parseStructuredProgram(raw: string): { intro: string; modules: ProgramModuleView[] } | null {
  const value = raw.trim()
  if (!value) return null

  try {
    const parsed = JSON.parse(value) as StoredProgram
    if (parsed?.version !== 1 || !Array.isArray(parsed.modules)) return null

    const modules: ProgramModuleView[] = parsed.modules.flatMap((moduleValue) => {
      if (!moduleValue || typeof moduleValue !== 'object') return []
      const module = moduleValue as { title?: unknown; chapters?: unknown }
      const title = cleanText(module.title)
      if (!title) return []

      const chapters: ProgramChapterView[] = Array.isArray(module.chapters)
        ? module.chapters.flatMap((chapterValue) => {
            if (typeof chapterValue === 'string') {
              const chapterTitle = chapterValue.trim()
              return chapterTitle ? [{ title: chapterTitle, lessons: [] }] : []
            }
            if (!chapterValue || typeof chapterValue !== 'object') return []
            const chapter = chapterValue as { title?: unknown; lessons?: unknown }
            const chapterTitle = cleanText(chapter.title)
            if (!chapterTitle) return []
            const lessons = Array.isArray(chapter.lessons)
              ? chapter.lessons
                  .map((lessonValue) => {
                    if (typeof lessonValue === 'string') return lessonValue.trim()
                    if (!lessonValue || typeof lessonValue !== 'object') return ''
                    return cleanText((lessonValue as { title?: unknown }).title)
                  })
                  .filter(Boolean)
              : []
            return [{ title: chapterTitle, lessons }]
          })
        : []

      return [{ title, chapters }]
    })

    return {
      intro: cleanText(parsed.intro),
      modules,
    }
  } catch {
    return null
  }
}

function normalizeFallbackModules(modules: PublicFormationDetail['modules']): ProgramModuleView[] {
  return (modules as unknown as Array<{
    title?: string
    chapters?: Array<string | { title?: string; lessons?: Array<string | { title?: string }> }>
  }>).flatMap((module) => {
    const title = cleanText(module.title)
    if (!title) return []
    const chapters: ProgramChapterView[] = Array.isArray(module.chapters)
      ? module.chapters.flatMap((chapter) => {
          if (typeof chapter === 'string') {
            const chapterTitle = chapter.trim()
            return chapterTitle ? [{ title: chapterTitle, lessons: [] }] : []
          }
          const chapterTitle = cleanText(chapter?.title)
          if (!chapterTitle) return []
          const lessons = Array.isArray(chapter?.lessons)
            ? chapter.lessons.map((lesson) => typeof lesson === 'string' ? lesson.trim() : cleanText(lesson?.title)).filter(Boolean)
            : []
          return [{ title: chapterTitle, lessons }]
        })
      : []
    return [{ title, chapters }]
  })
}

export function PublicProgramSection({
  rawProgram,
  fallbackModules,
}: {
  rawProgram: string
  fallbackModules: PublicFormationDetail['modules']
}) {
  const structured = parseStructuredProgram(rawProgram)
  const intro = structured ? structured.intro : rawProgram.trim()
  const modules = structured ? structured.modules : normalizeFallbackModules(fallbackModules)

  if (!intro && modules.length === 0) return null

  return (
    <section className="school-detail-section-block school-public-program-section">
      <div className="school-detail-section-heading-v2">
        <span className="school-detail-section-icon"><Layers3 size={19} /></span>
        <div>
          <span className="school-detail-section-kicker">Votre parcours</span>
          <h2>Programme de la formation</h2>
        </div>
      </div>

      {intro && <p className="school-preline school-detail-program-intro">{intro}</p>}

      {modules.length > 0 && (
        <div className="school-public-program-accordion">
          {modules.map((module, moduleIndex) => {
            const lessonCount = module.chapters.reduce((sum, chapter) => sum + chapter.lessons.length, 0)
            return (
              <details className="school-public-program-module" key={`${module.title}-${moduleIndex}`} open={moduleIndex === 0}>
                <summary>
                  <span className="school-public-program-module-number">Module {moduleIndex + 1}</span>
                  <span className="school-public-program-module-title">
                    <strong>{module.title}</strong>
                    <small>{module.chapters.length} chapitre(s){lessonCount > 0 ? ` · ${lessonCount} leçon(s)` : ''}</small>
                  </span>
                  <ChevronDown className="school-public-program-chevron" size={18} />
                </summary>

                <div className="school-public-program-module-body">
                  {module.chapters.map((chapter, chapterIndex) => (
                    <details className="school-public-program-chapter" key={`${chapter.title}-${chapterIndex}`} open={moduleIndex === 0 && chapterIndex === 0}>
                      <summary>
                        <span className="school-public-program-chapter-icon"><BookOpen size={15} /></span>
                        <span>
                          <small>Chapitre {chapterIndex + 1}</small>
                          <strong>{chapter.title}</strong>
                        </span>
                        <span className="school-public-program-chapter-meta">{chapter.lessons.length} leçon(s)</span>
                        <ChevronDown className="school-public-program-chevron" size={16} />
                      </summary>

                      {chapter.lessons.length > 0 ? (
                        <ul className="school-public-program-lessons">
                          {chapter.lessons.map((lesson, lessonIndex) => (
                            <li key={`${lesson}-${lessonIndex}`}>
                              <span className="school-public-program-lesson-icon"><FileText size={13} /></span>
                              <span><small>Leçon {lessonIndex + 1}</small>{lesson}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <div className="school-public-program-no-lessons"><CheckCircle2 size={14} /> Contenu détaillé communiqué pendant la formation.</div>
                      )}
                    </details>
                  ))}
                  {module.chapters.length === 0 && (
                    <div className="school-public-program-no-lessons">Les chapitres de ce module seront bientôt détaillés.</div>
                  )}
                </div>
              </details>
            )
          })}
        </div>
      )}
    </section>
  )
}
