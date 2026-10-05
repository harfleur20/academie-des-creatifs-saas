import { useEffect, useMemo, useState } from 'react'
import { BookOpen, FilePlus2, History, Plus } from 'lucide-react'
import {
  ApiError,
  createChapterLesson,
  createCourseChapter,
  createSessionCourse,
  getFormation,
  getTeacherWorkspace,
  listTeacherAssignments,
  listTeacherQuizzes,
  listTeacherResources,
  listLessonVersions,
  publishChapterLesson,
  restoreLessonVersion,
  updateChapterLesson,
  updateSessionCourse,
  uploadLessonPdf,
  type AcademicResource,
  type Assignment,
  type FormationDetail,
  type Lesson,
  type LessonPayload,
  type LessonVersion,
  type TeacherQuiz,
  type TeacherWorkspace,
} from '../lib/api'

type LessonDraft = {
  title: string
  lesson_type: Lesson['lesson_type']
  content: string
  linked_id?: string
  available_at?: string
}

function payloadForLesson(draft: LessonDraft, orderIndex: number): LessonPayload {
  const value = draft.content.trim()
  return {
    title: draft.title.trim(), order_index: orderIndex, lesson_type: draft.lesson_type,
    content: draft.lesson_type === 'text' ? value : null,
    video_url: draft.lesson_type === 'video' ? value : null,
    file_url: ['pdf', 'resource'].includes(draft.lesson_type) ? value : null,
    quiz_id: ['quiz', 'pdf', 'text'].includes(draft.lesson_type) && draft.linked_id ? Number(draft.linked_id) : null,
    assignment_id: draft.lesson_type === 'assignment' && draft.linked_id ? Number(draft.linked_id) : null,
    resource_id: draft.lesson_type === 'resource' && draft.linked_id ? Number(draft.linked_id) : null,
    available_at: draft.available_at ? new Date(draft.available_at).toISOString() : null,
  }
}

function localDateTime(value: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset())
  return date.toISOString().slice(0, 16)
}

function draftForLesson(lesson: Lesson): LessonDraft {
  return {
    title: lesson.title, lesson_type: lesson.lesson_type,
    content: lesson.lesson_type === 'text' ? lesson.content || '' : lesson.lesson_type === 'video' ? lesson.video_url || '' : lesson.file_url || '',
    linked_id: String(lesson.quiz_id || lesson.assignment_id || lesson.resource_id || ''),
    available_at: localDateTime(lesson.available_at),
  }
}

export function TeacherCoursesPage() {
  const [workspace, setWorkspace] = useState<TeacherWorkspace | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [formation, setFormation] = useState<FormationDetail | null>(null)
  const [courseTitle, setCourseTitle] = useState('')
  const [chapterDrafts, setChapterDrafts] = useState<Record<number, string>>({})
  const [lessonDrafts, setLessonDrafts] = useState<Record<number, LessonDraft>>({})
  const [editingLessonId, setEditingLessonId] = useState<number | null>(null)
  const [editingDraft, setEditingDraft] = useState<LessonDraft | null>(null)
  const [historyLessonId, setHistoryLessonId] = useState<number | null>(null)
  const [versions, setVersions] = useState<LessonVersion[]>([])
  const [quizzes, setQuizzes] = useState<TeacherQuiz[]>([])
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [resources, setResources] = useState<AcademicResource[]>([])
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)
  const [uploadingPdf, setUploadingPdf] = useState<number | null>(null)

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
    const [detail, sessionQuizzes, sessionAssignments, sessionResources] = await Promise.all([
      getFormation(selectedWorkspace.formation_id),
      listTeacherQuizzes(selectedWorkspace.session_id),
      listTeacherAssignments(selectedWorkspace.session_id),
      listTeacherResources(selectedWorkspace.session_id),
    ])
    setFormation(detail)
    setQuizzes(sessionQuizzes)
    setAssignments(sessionAssignments)
    setResources(sessionResources)
  }

  useEffect(() => {
    if (selectedWorkspace) {
      void refresh().catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
    }
  }, [selectedWorkspace?.formation_id, selectedWorkspace?.session_id])

  const session = formation?.sessions.find((item) => item.id === sessionId) ?? null

  async function run(action: () => Promise<FormationDetail>): Promise<boolean> {
    setWorking(true)
    setError('')
    try {
      setFormation(await action())
      return true
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Action impossible.')
      return false
    } finally {
      setWorking(false)
    }
  }

  async function addCourse() {
    if (!formation || !session || courseTitle.trim().length < 2) return
    const created = await run(() => createSessionCourse(formation.id, session.id, {
      title: courseTitle.trim(),
    }))
    if (created) setCourseTitle('')
  }

  async function addChapter(courseId: number, count: number) {
    if (!formation || !session) return
    const title = (chapterDrafts[courseId] || '').trim()
    if (title.length < 2) return
    const created = await run(() => createCourseChapter(formation.id, session.id, courseId, {
      title,
      order_index: count,
    }))
    if (created) setChapterDrafts((current) => ({ ...current, [courseId]: '' }))
  }

  async function addLesson(courseId: number, chapterId: number, count: number) {
    if (!formation || !session) return
    const draft = lessonDrafts[chapterId] || { title: '', lesson_type: 'text', content: '' }
    if (draft.title.trim().length < 2) return
    const created = await run(() => createChapterLesson(
      formation.id,
      session.id,
      courseId,
      chapterId,
      payloadForLesson(draft, count),
    ))
    if (created) setLessonDrafts((current) => ({
      ...current,
      [chapterId]: { title: '', lesson_type: 'text', content: '' },
    }))
  }

  async function importPdf(chapterId: number, file: File | undefined, editing = false) {
    if (!file) return
    setUploadingPdf(chapterId)
    setError('')
    try {
      const asset = await uploadLessonPdf(file)
      if (editing) setEditingDraft((current) => current && ({ ...current, content: asset.source_url }))
      else setLessonDrafts((current) => ({ ...current, [chapterId]: {
        ...(current[chapterId] || { title: '', lesson_type: 'pdf', content: '' }), content: asset.source_url,
      } }))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Import du PDF impossible.')
    } finally {
      setUploadingPdf(null)
    }
  }

  async function saveLesson(courseId: number, chapterId: number, lesson: Lesson) {
    if (!formation || !session || !editingDraft) return
    const saved = await run(() => updateChapterLesson(formation.id, session.id, courseId, chapterId, lesson.id, payloadForLesson(editingDraft, lesson.order_index)))
    if (saved) { setEditingLessonId(null); setEditingDraft(null) }
  }

  async function showHistory(courseId: number, chapterId: number, lessonId: number) {
    if (!formation || !session) return
    if (historyLessonId === lessonId) { setHistoryLessonId(null); return }
    setError('')
    try {
      const rows = await listLessonVersions(formation.id, session.id, courseId, chapterId, lessonId)
      setVersions(rows)
      setHistoryLessonId(lessonId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Historique indisponible.')
    }
  }

  async function restoreVersion(courseId: number, chapterId: number, lessonId: number, versionNumber: number) {
    if (!formation || !session) return
    const restored = await run(() => restoreLessonVersion(formation.id, session.id, courseId, chapterId, lessonId, versionNumber))
    if (restored) {
      setEditingLessonId(null)
      setEditingDraft(null)
      try {
        setVersions(await listLessonVersions(formation.id, session.id, courseId, chapterId, lessonId))
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Historique indisponible.')
      }
    }
  }

  function renderLessonFields(draft: LessonDraft, change: (value: LessonDraft) => void, chapterId: number, editing = false) {
    return <>
      <input value={draft.title} onChange={(event) => change({ ...draft, title: event.target.value })} placeholder="Titre de la leçon" />
      <select value={draft.lesson_type} onChange={(event) => change({ ...draft, lesson_type: event.target.value as Lesson['lesson_type'], linked_id: '', content: '' })}>
        <option value="text">Texte</option><option value="video">Vidéo</option><option value="pdf">PDF</option><option value="resource">Ressource</option><option value="quiz">Quiz</option><option value="assignment">Devoir</option>
      </select>
      {!['quiz', 'assignment', 'pdf'].includes(draft.lesson_type) && <input value={draft.content} onChange={(event) => change({ ...draft, content: event.target.value })} placeholder={draft.lesson_type === 'text' ? 'Contenu de la leçon' : 'URL du contenu'} />}
      {draft.lesson_type === 'pdf' && <label>PDF de la leçon <input type="file" accept="application/pdf,.pdf" disabled={uploadingPdf === chapterId} onChange={(event) => void importPdf(chapterId, event.target.files?.[0], editing)} />{draft.content && <small>PDF importé dans cette école.</small>}</label>}
      {['quiz', 'pdf', 'text', 'assignment', 'resource'].includes(draft.lesson_type) && <select aria-label="Activité liée" value={draft.linked_id || ''} onChange={(event) => change({ ...draft, linked_id: event.target.value })}>
        <option value="">{['quiz', 'assignment'].includes(draft.lesson_type) ? 'Choisir une activité' : 'Aucune activité liée'}</option>
        {(['quiz', 'pdf', 'text'].includes(draft.lesson_type) ? quizzes.filter((quiz) => draft.lesson_type !== 'pdf' || quiz.questions.length === 20) : draft.lesson_type === 'assignment' ? assignments : resources).map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
      </select>}
      <label>Disponible à partir du <input type="datetime-local" value={draft.available_at || ''} onChange={(event) => change({ ...draft, available_at: event.target.value })} /></label>
    </>
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
                  <button className="secondary-button" type="button" disabled={working || course.status === 'published'} onClick={() => void run(() => updateSessionCourse(formation.id, session.id, course.id, { status: 'published' }))}>{course.status === 'published' ? 'Cours publié' : 'Publier le cours'}</button>
                </header>

                {course.chapters.map((chapter) => {
                  const draft = lessonDrafts[chapter.id] || { title: '', lesson_type: 'text', content: '' }
                  return (
                    <section className="teacher-module" key={chapter.id}>
                      <div className="teacher-module-head"><strong>Module {chapter.order_index + 1} : {chapter.title}</strong><span>{chapter.lessons.length} leçon(s)</span></div>
                      <div className="teacher-lesson-list">
                        {chapter.lessons.map((lesson) => (
                          <div className={'teacher-lesson-row' + (historyLessonId === lesson.id ? ' is-history-open' : '')} key={lesson.id}>
                            <span><FilePlus2 size={13}/>{lesson.title} <small>{lesson.lesson_type} · {lesson.publication_status === 'published' ? 'Publiée' : 'Brouillon'} · v{lesson.version_number}</small></span>
                            <button className="secondary-button" type="button" disabled={working} onClick={() => { setEditingLessonId(lesson.id); setEditingDraft(draftForLesson(lesson)) }}>Modifier</button>
                            <button className="secondary-button" type="button" disabled={working} onClick={() => void showHistory(course.id, chapter.id, lesson.id)}><History size={13}/> Historique</button>
                            {course.status === 'published' && lesson.publication_status !== 'published' && <button className="secondary-button" type="button" disabled={working} onClick={() => void run(() => publishChapterLesson(formation.id, session.id, course.id, chapter.id, lesson.id))}>Publier</button>}
                            {historyLessonId === lesson.id && <div className="teacher-lesson-history"><strong>Versions de la leçon</strong>{versions.map((version) => <div key={version.id}><span>v{version.version_number} · {version.snapshot.title} · {new Date(version.created_at).toLocaleString('fr-FR')} · {version.reason}</span>{version.version_number !== lesson.version_number && <button className="secondary-button" type="button" disabled={working} onClick={() => void restoreVersion(course.id, chapter.id, lesson.id, version.version_number)}>Restaurer le contenu</button>}</div>)}</div>}
                            {editingLessonId === lesson.id && editingDraft && <div className="lesson-create-grid teacher-lesson-edit">
                              {renderLessonFields(editingDraft, setEditingDraft, chapter.id, true)}
                              <button className="primary-button" type="button" disabled={working || uploadingPdf === chapter.id || editingDraft.title.trim().length < 2} onClick={() => void saveLesson(course.id, chapter.id, lesson)}>Enregistrer</button>
                              <button className="secondary-button" type="button" onClick={() => { setEditingLessonId(null); setEditingDraft(null) }}>Annuler</button>
                            </div>}
                          </div>
                        ))}
                      </div>
                      <div className="lesson-create-grid">
                        {renderLessonFields(draft, (value) => setLessonDrafts((current) => ({ ...current, [chapter.id]: value })), chapter.id)}
                        <button className="secondary-button" type="button" disabled={working || uploadingPdf === chapter.id || draft.title.trim().length < 2 || (['quiz', 'assignment', 'pdf'].includes(draft.lesson_type) && !draft.linked_id) || (draft.lesson_type === 'pdf' && !draft.content.startsWith('school-pdf:'))} onClick={() => void addLesson(course.id, chapter.id, chapter.lessons.length)}><Plus size={13}/> Leçon</button>
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
