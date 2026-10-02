import { useEffect, useMemo, useState } from 'react'
import { BookOpen, FilePlus2, Plus } from 'lucide-react'
import {
  ApiError,
  createChapterLesson,
  createCourseChapter,
  createSessionCourse,
  getFormation,
  getTeacherWorkspace,
  type FormationDetail,
  type Lesson,
  type TeacherWorkspace,
} from '../lib/api'

type LessonDraft = {
  title: string
  lesson_type: Lesson['lesson_type']
  content: string
}

export function TeacherCoursesPage() {
  const [workspace, setWorkspace] = useState<TeacherWorkspace | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [formation, setFormation] = useState<FormationDetail | null>(null)
  const [courseTitle, setCourseTitle] = useState('')
  const [chapterDrafts, setChapterDrafts] = useState<Record<number, string>>({})
  const [lessonDrafts, setLessonDrafts] = useState<Record<number, LessonDraft>>({})
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)

  useEffect(() => {
    getTeacherWorkspace().then((data) => {
      setWorkspace(data)
      setSessionId(data.sessions[0]?.session_id ?? null)
    }).catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [])

  const selectedWorkspace = useMemo(
    () => workspace?.sessions.find((item) => item.session_id === sessionId) ?? null,
    [workspace, sessionId],
  )

  async function refresh() {
    if (!selectedWorkspace) return
    setFormation(await getFormation(selectedWorkspace.formation_id))
  }

  useEffect(() => {
    if (selectedWorkspace) {
      void refresh().catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
    }
  }, [selectedWorkspace?.formation_id, selectedWorkspace?.session_id])

  const session = formation?.sessions.find((item) => item.id === sessionId) ?? null

  async function run(action: () => Promise<FormationDetail>) {
    setWorking(true)
    setError('')
    try {
      setFormation(await action())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Action impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function addCourse() {
    if (!formation || !session || courseTitle.trim().length < 2) return
    await run(() => createSessionCourse(formation.id, session.id, {
      title: courseTitle.trim(),
    }))
    setCourseTitle('')
  }

  async function addChapter(courseId: number, count: number) {
    if (!formation || !session) return
    const title = (chapterDrafts[courseId] || '').trim()
    if (title.length < 2) return
    await run(() => createCourseChapter(formation.id, session.id, courseId, {
      title,
      order_index: count,
    }))
    setChapterDrafts((current) => ({ ...current, [courseId]: '' }))
  }

  async function addLesson(courseId: number, chapterId: number, count: number) {
    if (!formation || !session) return
    const draft = lessonDrafts[chapterId] || { title: '', lesson_type: 'text', content: '' }
    if (draft.title.trim().length < 2) return
    const value = draft.content.trim()
    await run(() => createChapterLesson(
      formation.id,
      session.id,
      courseId,
      chapterId,
      {
        title: draft.title.trim(),
        order_index: count,
        lesson_type: draft.lesson_type,
        content: draft.lesson_type === 'text' ? value : null,
        video_url: draft.lesson_type === 'video' ? value : null,
        file_url: ['pdf', 'resource'].includes(draft.lesson_type) ? value : null,
      },
    ))
    setLessonDrafts((current) => ({
      ...current,
      [chapterId]: { title: '', lesson_type: 'text', content: '' },
    }))
  }

  return (
    <main className="app-page academic-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Espace professeur</span>
          <h1>Mes cours</h1>
          <p>Construisez le contenu des sessions auxquelles vous êtes affecté.</p>
        </div>
      </header>
      {error && <div className="form-error">{error}</div>}

      <label className="academic-session-select">
        Session
        <select value={sessionId ?? ''} onChange={(event) => setSessionId(Number(event.target.value))}>
          {workspace?.sessions.map((item) => (
            <option key={item.session_id} value={item.session_id}>
              {item.formation_title} · {item.session_label}
            </option>
          ))}
        </select>
      </label>

      {session && formation && (
        <>
          <section className="app-card teacher-course-create">
            <input value={courseTitle} onChange={(event) => setCourseTitle(event.target.value)} placeholder="Nom du nouveau cours" />
            <button className="primary-button" type="button" disabled={working || courseTitle.trim().length < 2} onClick={() => void addCourse()}>
              <Plus size={14}/> Ajouter le cours
            </button>
          </section>

          <section className="teacher-course-list">
            {session.courses.map((course) => (
              <article className="app-card teacher-course-card" key={course.id}>
                <header>
                  <div><span className="section-label">{course.status}</span><h2>{course.title}</h2><p>{course.teacher_name || 'Professeur non défini'}</p></div>
                  <BookOpen size={20}/>
                </header>

                {course.chapters.map((chapter) => {
                  const draft = lessonDrafts[chapter.id] || { title: '', lesson_type: 'text', content: '' }
                  return (
                    <section className="teacher-module" key={chapter.id}>
                      <div className="teacher-module-head"><strong>Module {chapter.order_index + 1} : {chapter.title}</strong><span>{chapter.lessons.length} leçon(s)</span></div>
                      <div className="teacher-lesson-list">
                        {chapter.lessons.map((lesson) => (
                          <span key={lesson.id}><FilePlus2 size={13}/>{lesson.title}<small>{lesson.lesson_type}</small></span>
                        ))}
                      </div>
                      <div className="lesson-create-grid">
                        <input value={draft.title} onChange={(event) => setLessonDrafts((current) => ({ ...current, [chapter.id]: { ...draft, title: event.target.value } }))} placeholder="Titre de la leçon" />
                        <select value={draft.lesson_type} onChange={(event) => setLessonDrafts((current) => ({ ...current, [chapter.id]: { ...draft, lesson_type: event.target.value as Lesson['lesson_type'] } }))}>
                          <option value="text">Texte</option>
                          <option value="video">Vidéo</option>
                          <option value="pdf">PDF</option>
                          <option value="resource">Ressource</option>
                        </select>
                        <input value={draft.content} onChange={(event) => setLessonDrafts((current) => ({ ...current, [chapter.id]: { ...draft, content: event.target.value } }))} placeholder={draft.lesson_type === 'text' ? 'Contenu de la leçon' : 'URL du contenu'} />
                        <button className="secondary-button" type="button" disabled={working || draft.title.trim().length < 2} onClick={() => void addLesson(course.id, chapter.id, chapter.lessons.length)}><Plus size={13}/> Leçon</button>
                      </div>
                    </section>
                  )
                })}

                <div className="teacher-chapter-create">
                  <input value={chapterDrafts[course.id] || ''} onChange={(event) => setChapterDrafts((current) => ({ ...current, [course.id]: event.target.value }))} placeholder="Nouveau module" />
                  <button className="secondary-button" type="button" disabled={working || (chapterDrafts[course.id] || '').trim().length < 2} onClick={() => void addChapter(course.id, course.chapters.length)}><Plus size={13}/> Module</button>
                </div>
              </article>
            ))}
            {session.courses.length === 0 && <div className="app-card formation-empty"><BookOpen size={26}/><strong>Aucun cours</strong><p>Ajoutez le premier cours de cette session.</p></div>}
          </section>
        </>
      )}
    </main>
  )
}
