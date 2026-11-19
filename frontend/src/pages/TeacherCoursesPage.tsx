import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BookOpen,
  CalendarDays,
  ChevronLeft,
  ChevronDown,
  ChevronRight,
  FilePlus2,
  History,
  LoaderCircle,
  Plus,
  Sparkles,
  WandSparkles,
  X,
} from 'lucide-react'
import {
  ApiError,
  createChapterLesson,
  createCourseChapter,
  createSessionCourse,
  getFormation,
  getSessionPlanning,
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
  type SessionPlanning,
  type TeacherQuiz,
  type TeacherWorkspace,
} from '../lib/api'
import {
  generateTeacherCourseDraft,
  getTeacherAIStatus,
  type AiCourseDraft,
} from '../lib/tenantIntegrationApi'
import { initialTeacherSessionId } from '../lib/teacherSession'
import { formatDuration } from '../lib/formatDuration'

function startOfWeek(value: Date) {
  const date = new Date(value)
  date.setHours(0, 0, 0, 0)
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7))
  return date
}

function addDays(value: Date, count: number) {
  const date = new Date(value)
  date.setDate(date.getDate() + count)
  return date
}

function localDateKey(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function courseDayTimeRange(scheduledAt: string, durationMinutes: number) {
  const start = new Date(scheduledAt)
  const end = new Date(start.getTime() + durationMinutes * 60_000)
  const time = (value: Date) => value.toLocaleTimeString(activeSchoolLocale(), { hour: '2-digit', minute: '2-digit' })
  return `${time(start)} – ${time(end)}`
}

type LessonDraft = {
  title: string
  lesson_type: Lesson['lesson_type']
  content: string
  linked_id?: string
  linked_kind?: '' | 'quiz' | 'assignment' | 'resource'
  available_at?: string
}

// A video lesson can carry one complementary activity, as on the mother site.
function linkedKind(draft: LessonDraft): '' | 'quiz' | 'assignment' | 'resource' {
  if (draft.lesson_type === 'video') return draft.linked_kind || ''
  if (['quiz', 'pdf', 'text'].includes(draft.lesson_type)) return 'quiz'
  if (draft.lesson_type === 'assignment') return 'assignment'
  if (draft.lesson_type === 'resource') return 'resource'
  return ''
}

function payloadForLesson(draft: LessonDraft, orderIndex: number): LessonPayload {
  const value = draft.content.trim()
  return {
    title: draft.title.trim(), order_index: orderIndex, lesson_type: draft.lesson_type,
    content: draft.lesson_type === 'text' ? value : null,
    video_url: draft.lesson_type === 'video' ? value : null,
    file_url: ['pdf', 'resource'].includes(draft.lesson_type) ? value : null,
    quiz_id: linkedKind(draft) === 'quiz' && draft.linked_id ? Number(draft.linked_id) : null,
    assignment_id: linkedKind(draft) === 'assignment' && draft.linked_id ? Number(draft.linked_id) : null,
    resource_id: linkedKind(draft) === 'resource' && draft.linked_id ? Number(draft.linked_id) : null,
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
    linked_kind: lesson.quiz_id ? 'quiz' : lesson.assignment_id ? 'assignment' : lesson.resource_id ? 'resource' : '',
    available_at: localDateTime(lesson.available_at),
  }
}

export function TeacherCoursesPage() {
  const [workspace, setWorkspace] = useState<TeacherWorkspace | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [workspaceTab, setWorkspaceTab] = useState<'courses' | 'schedule'>('courses')
  const [planning, setPlanning] = useState<SessionPlanning | null>(null)
  const [planningError, setPlanningError] = useState('')
  const [planningLoading, setPlanningLoading] = useState(false)
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()))
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
  const [openCourses, setOpenCourses] = useState<Set<number>>(new Set())
  const [openChapters, setOpenChapters] = useState<Set<number>>(new Set())

  const [aiConnected, setAiConnected] = useState<boolean | null>(null)
  const [showAiDesigner, setShowAiDesigner] = useState(false)
  const [aiTopic, setAiTopic] = useState('')
  const [aiLevel, setAiLevel] = useState('')
  const [aiObjectives, setAiObjectives] = useState('')
  const [aiChaptersCount, setAiChaptersCount] = useState(3)
  const [aiLessonsCount, setAiLessonsCount] = useState(3)
  const [aiGenerating, setAiGenerating] = useState(false)
  const [aiApplying, setAiApplying] = useState(false)
  const [aiDraft, setAiDraft] = useState<AiCourseDraft | null>(null)

  useEffect(() => {
    Promise.all([
      getTeacherWorkspace(),
      getTeacherAIStatus().catch(() => null),
    ]).then(([data, aiStatus]) => {
      setWorkspace(data)
      setSessionId(initialTeacherSessionId(data.sessions))
      setAiConnected(aiStatus?.connected ?? false)
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

  useEffect(() => {
    if (!selectedWorkspace) {
      setPlanning(null)
      return
    }
    let cancelled = false
    setPlanningLoading(true)
    setPlanningError('')
    getSessionPlanning(selectedWorkspace.session_id)
      .then((result) => { if (!cancelled) setPlanning(result) })
      .catch((err) => {
        if (!cancelled) setPlanningError(err instanceof ApiError ? err.message : 'Impossible de charger l’emploi du temps.')
      })
      .finally(() => { if (!cancelled) setPlanningLoading(false) })
    return () => { cancelled = true }
  }, [selectedWorkspace?.session_id])

  const session = formation?.sessions.find((item) => item.id === sessionId) ?? null
  const weekEnd = addDays(weekStart, 6)
  const weekRange = `Semaine du ${weekStart.toLocaleDateString(activeSchoolLocale(), { dateStyle: 'medium' })} au ${weekEnd.toLocaleDateString(activeSchoolLocale(), { dateStyle: 'medium' })}`
  const weekDays = Array.from({ length: 7 }, (_, index) => {
    const date = addDays(weekStart, index)
    const key = localDateKey(date)
    const entries = (planning?.course_days ?? [])
      .filter((day) => day.status !== 'cancelled' && localDateKey(new Date(day.scheduled_at)) === key)
      .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
    return { date, entries }
  })

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
    const beforeIds = new Set(session.courses.map((course) => course.id))
    setWorking(true)
    setError('')
    try {
      const detail = await createSessionCourse(formation.id, session.id, { title: courseTitle.trim() })
      setFormation(detail)
      const updatedSession = detail.sessions.find((item) => item.id === session.id)
      const created = updatedSession?.courses.find((course) => !beforeIds.has(course.id))
      if (created) setOpenCourses((current) => new Set(current).add(created.id))
      setCourseTitle('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Création impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function addChapter(courseId: number, count: number) {
    if (!formation || !session) return
    const title = (chapterDrafts[courseId] || '').trim()
    if (title.length < 2) return
    const created = await run(() => createCourseChapter(formation.id, session.id, courseId, { title, order_index: count }))
    if (created) setChapterDrafts((current) => ({ ...current, [courseId]: '' }))
  }

  async function addLesson(courseId: number, chapterId: number, count: number) {
    if (!formation || !session) return
    const draft = lessonDrafts[chapterId] || { title: '', lesson_type: 'text', content: '' }
    if (draft.title.trim().length < 2) return
    const created = await run(() => createChapterLesson(formation.id, session.id, courseId, chapterId, payloadForLesson(draft, count)))
    if (created) setLessonDrafts((current) => ({ ...current, [chapterId]: { title: '', lesson_type: 'text', content: '' } }))
  }

  async function importPdf(chapterId: number, file: File | undefined, editing = false) {
    if (!file) return
    setUploadingPdf(chapterId)
    setError('')
    try {
      const asset = await uploadLessonPdf(file)
      if (editing) setEditingDraft((current) => current && ({ ...current, content: asset.source_url }))
      else setLessonDrafts((current) => ({ ...current, [chapterId]: { ...(current[chapterId] || { title: '', lesson_type: 'pdf', content: '' }), content: asset.source_url } }))
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

  async function generateCourseWithAI() {
    if (!sessionId || !aiTopic.trim()) return
    setAiGenerating(true)
    setError('')
    try {
      setAiDraft(await generateTeacherCourseDraft({
        session_id: sessionId,
        topic: aiTopic.trim(),
        level: aiLevel.trim() || null,
        objectives: aiObjectives.trim() || null,
        chapters_count: aiChaptersCount,
        lessons_per_chapter: aiLessonsCount,
      }))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Impossible de générer le cours.')
    } finally {
      setAiGenerating(false)
    }
  }

  function updateAiChapter(index: number, title: string) {
    setAiDraft((current) => current && ({ ...current, chapters: current.chapters.map((chapter, chapterIndex) => chapterIndex === index ? { ...chapter, title } : chapter) }))
  }

  function updateAiLesson(chapterIndex: number, lessonIndex: number, patch: { title?: string; content?: string }) {
    setAiDraft((current) => current && ({
      ...current,
      chapters: current.chapters.map((chapter, currentChapterIndex) => currentChapterIndex === chapterIndex
        ? { ...chapter, lessons: chapter.lessons.map((lesson, currentLessonIndex) => currentLessonIndex === lessonIndex ? { ...lesson, ...patch } : lesson) }
        : chapter),
    }))
  }

  async function applyAiDraft() {
    if (!formation || !session || !aiDraft || aiDraft.title.trim().length < 2) return
    setAiApplying(true)
    setError('')
    let detail = formation
    try {
      const beforeCourseIds = new Set(session.courses.map((course) => course.id))
      detail = await createSessionCourse(formation.id, session.id, { title: aiDraft.title.trim() })
      let updatedSession = detail.sessions.find((item) => item.id === session.id)
      let createdCourse = updatedSession?.courses.find((course) => !beforeCourseIds.has(course.id))
      if (!createdCourse) throw new Error('Le cours généré n’a pas pu être identifié après sa création.')

      for (let chapterIndex = 0; chapterIndex < aiDraft.chapters.length; chapterIndex += 1) {
        const chapterDraft = aiDraft.chapters[chapterIndex]
        const beforeChapterIds = new Set(createdCourse.chapters.map((chapter) => chapter.id))
        detail = await createCourseChapter(formation.id, session.id, createdCourse.id, {
          title: chapterDraft.title.trim() || `Chapitre ${chapterIndex + 1}`,
          order_index: createdCourse.chapters.length,
        })
        updatedSession = detail.sessions.find((item) => item.id === session.id)
        createdCourse = updatedSession?.courses.find((course) => course.id === createdCourse?.id)
        const createdChapter = createdCourse?.chapters.find((chapter) => !beforeChapterIds.has(chapter.id))
        if (!createdCourse || !createdChapter) throw new Error('Un chapitre du brouillon n’a pas pu être créé.')

        for (let lessonIndex = 0; lessonIndex < chapterDraft.lessons.length; lessonIndex += 1) {
          const lesson = chapterDraft.lessons[lessonIndex]
          detail = await createChapterLesson(
            formation.id,
            session.id,
            createdCourse.id,
            createdChapter.id,
            payloadForLesson({ title: lesson.title, lesson_type: 'text', content: lesson.content }, lessonIndex),
          )
          updatedSession = detail.sessions.find((item) => item.id === session.id)
          createdCourse = updatedSession?.courses.find((course) => course.id === createdCourse?.id)
          if (!createdCourse) throw new Error('Le cours généré est devenu introuvable pendant son enregistrement.')
        }
      }

      setFormation(detail)
      setOpenCourses((current) => new Set(current).add(createdCourse.id))
      setAiDraft(null)
      setAiTopic('')
      setAiLevel('')
      setAiObjectives('')
      setShowAiDesigner(false)
    } catch (cause) {
      setFormation(detail)
      setError(`${cause instanceof Error ? cause.message : 'Application du brouillon impossible.'} Une partie du brouillon peut avoir été enregistrée : vérifiez le cours avant de recommencer.`)
    } finally {
      setAiApplying(false)
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
      {draft.lesson_type === 'video' && <>
        <select aria-label="Activité complémentaire" value={draft.linked_kind || ''} onChange={(event) => change({ ...draft, linked_kind: event.target.value as LessonDraft['linked_kind'], linked_id: '' })}>
          <option value="">Sans activité complémentaire</option><option value="quiz">Quiz</option><option value="assignment">Devoir</option><option value="resource">Ressource</option>
        </select>
        {draft.linked_kind && <select aria-label="Activité liée" value={draft.linked_id || ''} onChange={(event) => change({ ...draft, linked_id: event.target.value })}>
          <option value="">Choisir une activité</option>
          {(draft.linked_kind === 'quiz' ? quizzes : draft.linked_kind === 'assignment' ? assignments : resources).map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
        </select>}
        <small>La vidéo se valide au visionnage ; l’activité complète la leçon sans la conditionner.</small>
      </>}
      <label>Disponible à partir du <input type="datetime-local" value={draft.available_at || ''} onChange={(event) => change({ ...draft, available_at: event.target.value })} /></label>
    </>
  }

  return (
    <main className="app-page teacher-mother-page">
      <div className="dsh-page teacher-dsh-page">
        <div className="teacher-page-head">
          <div><h1>Mes cours</h1><p>Construisez le contenu des sessions auxquelles vous êtes affecté.</p></div>
          <button className="dsh-btn dsh-btn--ai" type="button" disabled={!sessionId} onClick={() => setShowAiDesigner(true)}><WandSparkles size={14} /> Concevoir avec IA</button>
        </div>

        {error && <div className="dsh-error">{error}</div>}

        <label className="teacher-session-select"><span>Session</span><select value={sessionId ?? ''} onChange={(event) => setSessionId(Number(event.target.value))}>{workspace?.sessions.map((item) => <option key={item.session_id} value={item.session_id}>{item.formation_title} · {item.session_label}</option>)}</select></label>

        {selectedWorkspace && <nav className="guided-tabs teacher-course-workspace-tabs" aria-label="Sections de la session">
          <button type="button" className={workspaceTab === 'courses' ? 'is-active' : ''} aria-pressed={workspaceTab === 'courses'} onClick={() => setWorkspaceTab('courses')}>Mes cours</button>
          <button type="button" className={workspaceTab === 'schedule' ? 'is-active' : ''} aria-pressed={workspaceTab === 'schedule'} onClick={() => setWorkspaceTab('schedule')}><CalendarDays size={15} aria-hidden="true" /> Emploi du temps</button>
        </nav>}

        {workspaceTab === 'schedule' && selectedWorkspace && <section className="app-card teacher-timetable-panel">
          <header className="teacher-timetable-panel__header">
            <div><span className="section-label">{selectedWorkspace.formation_title} · {selectedWorkspace.session_label}</span><h2>Emploi du temps</h2></div>
            <Link className="secondary-button" to={`/app/teacher/sessions/${selectedWorkspace.session_id}`}>Gérer les séances</Link>
          </header>
          {planningError && <div className="dsh-error">{planningError}</div>}
          {planningLoading ? <div className="page-state">Chargement de l’emploi du temps…</div> : <>
            <div className="guided-week-toolbar">
              <div className="guided-week-navigation">
                <button type="button" className="guided-week-button" aria-label="Semaine précédente" onClick={() => setWeekStart((current) => addDays(current, -7))}><ChevronLeft size={17} aria-hidden="true" /></button>
                <strong>{weekRange}</strong>
                <button type="button" className="guided-week-button" aria-label="Semaine suivante" onClick={() => setWeekStart((current) => addDays(current, 7))}><ChevronRight size={17} aria-hidden="true" /></button>
                <button type="button" className="guided-week-button guided-week-today" onClick={() => setWeekStart(startOfWeek(new Date()))}>Cette semaine</button>
              </div>
            </div>
            <div className="guided-week-scroll" role="region" aria-label="Emploi du temps de la semaine sur sept jours" tabIndex={0}>
              <div className="guided-week-grid">
                {weekDays.map(({ date, entries }) => {
                  const weekday = date.toLocaleDateString(activeSchoolLocale(), { weekday: 'long' })
                  const isToday = localDateKey(date) === localDateKey(new Date())
                  return <article className={`guided-week-day${isToday ? ' is-today' : ''}`} key={localDateKey(date)}>
                    <header className="guided-week-day__heading"><span>{weekday.charAt(0).toLocaleUpperCase(activeSchoolLocale())}{weekday.slice(1)}</span><strong>{date.getDate()}</strong></header>
                    <div className="guided-week-day__events">
                      {entries.map((day) => <article className="guided-week-event" key={day.id}>
                        <time dateTime={day.scheduled_at}>{courseDayTimeRange(day.scheduled_at, day.duration_minutes)}</time>
                        <strong>{day.title}</strong>
                        <small>{formatDuration(day.duration_minutes)} · {planning?.format_type === 'presentiel' ? 'Présentiel' : planning?.format_type === 'live' ? 'En direct' : 'En ligne'}</small>
                        <small>{day.teacher_name || 'Professeur non défini'}</small>
                      </article>)}
                      {entries.length === 0 && <p className="guided-week-empty">Aucun cours</p>}
                    </div>
                  </article>
                })}
              </div>
            </div>
          </>}
        </section>}

        {workspaceTab === 'courses' && session && formation && <>
          <section className="teacher-course-create-mother"><div><strong>Ajouter un cours manuellement</strong><span>Créez la structure puis ajoutez chapitres et leçons.</span></div><div><input value={courseTitle} onChange={(event) => setCourseTitle(event.target.value)} placeholder="Nom du nouveau cours" /><button className="dsh-btn dsh-btn--primary" type="button" disabled={working || courseTitle.trim().length < 2} onClick={() => void addCourse()}><Plus size={14} /> Ajouter</button></div></section>

          <section className="teacher-course-list-mother">
            {session.courses.map((course, courseIndex) => {
              const courseOpen = openCourses.has(course.id)
              return <article className="teacher-course-block" key={course.id}>
                <header className="teacher-course-block-head">
                  <button type="button" className="teacher-course-toggle" onClick={() => setOpenCourses((current) => { const next = new Set(current); if (next.has(course.id)) next.delete(course.id); else next.add(course.id); return next })}>
                    {courseOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    <span><small>Module {courseIndex + 1}</small><strong>{course.title}</strong><em>{course.teacher_name || 'Professeur non défini'} · {course.chapters.length} chapitre(s)</em></span>
                  </button>
                  <span className={`dsh-badge ${course.status === 'published' ? 'dsh-badge--green' : 'dsh-badge--yellow'}`}>{course.status === 'published' ? 'Publié' : 'Brouillon'}</span>
                  <button className="dsh-btn dsh-btn--outline dsh-btn--sm" type="button" disabled={working || course.status === 'published'} onClick={() => void run(() => updateSessionCourse(formation.id, session.id, course.id, { status: 'published' }))}>{course.status === 'published' ? 'Cours publié' : 'Publier le cours'}</button>
                </header>

                {courseOpen && <div className="teacher-course-block-body">
                  {course.chapters.map((chapter, chapterIndex) => {
                    const draft = lessonDrafts[chapter.id] || { title: '', lesson_type: 'text', content: '' }
                    const chapterOpen = openChapters.has(chapter.id)
                    return <section className="teacher-chapter-block" key={chapter.id}>
                      <button type="button" className="teacher-chapter-toggle" onClick={() => setOpenChapters((current) => { const next = new Set(current); if (next.has(chapter.id)) next.delete(chapter.id); else next.add(chapter.id); return next })}>{chapterOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}<span><strong>Chapitre {chapterIndex + 1} : {chapter.title}</strong><small>{chapter.lessons.length} leçon(s)</small></span></button>

                      {chapterOpen && <div className="teacher-chapter-content">
                        <div className="teacher-lesson-list-mother">
                          {chapter.lessons.map((lesson, lessonIndex) => <div className={`teacher-lesson-row-mother${historyLessonId === lesson.id ? ' is-history-open' : ''}`} key={lesson.id}>
                            <div className="teacher-lesson-main"><span className="teacher-lesson-index">{lessonIndex + 1}</span><span><strong>{lesson.title}</strong><small>{lesson.lesson_type} · {lesson.publication_status === 'published' ? 'Publiée' : 'Brouillon'} · v{lesson.version_number}</small></span></div>
                            <div className="teacher-lesson-actions"><button className="dsh-btn dsh-btn--ghost dsh-btn--sm" type="button" disabled={working} onClick={() => { setEditingLessonId(lesson.id); setEditingDraft(draftForLesson(lesson)) }}>Modifier</button><button className="dsh-btn dsh-btn--ghost dsh-btn--sm" type="button" disabled={working} onClick={() => void showHistory(course.id, chapter.id, lesson.id)}><History size={13} /> Historique</button>{course.status === 'published' && lesson.publication_status !== 'published' && <button className="dsh-btn dsh-btn--outline dsh-btn--sm" type="button" disabled={working} onClick={() => void run(() => publishChapterLesson(formation.id, session.id, course.id, chapter.id, lesson.id))}>Publier</button>}</div>
                            {historyLessonId === lesson.id && <div className="teacher-lesson-history-mother"><strong>Versions de la leçon</strong>{versions.map((version) => <div key={version.id}><span>v{version.version_number} · {version.snapshot.title} · {new Date(version.created_at).toLocaleString(activeSchoolLocale())} · {version.reason}</span>{version.version_number !== lesson.version_number && <button className="dsh-btn dsh-btn--outline dsh-btn--sm" type="button" disabled={working} onClick={() => void restoreVersion(course.id, chapter.id, lesson.id, version.version_number)}>Restaurer</button>}</div>)}</div>}
                            {editingLessonId === lesson.id && editingDraft && <div className="teacher-lesson-editor">{renderLessonFields(editingDraft, setEditingDraft, chapter.id, true)}<div><button className="dsh-btn dsh-btn--primary" type="button" disabled={working || uploadingPdf === chapter.id || editingDraft.title.trim().length < 2} onClick={() => void saveLesson(course.id, chapter.id, lesson)}>Enregistrer</button><button className="dsh-btn dsh-btn--ghost" type="button" onClick={() => { setEditingLessonId(null); setEditingDraft(null) }}>Annuler</button></div></div>}
                          </div>)}
                        </div>
                        <div className="teacher-add-lesson"><div className="teacher-add-lesson-title"><FilePlus2 size={14} /><strong>Ajouter une leçon</strong></div><div className="teacher-lesson-form-grid">{renderLessonFields(draft, (value) => setLessonDrafts((current) => ({ ...current, [chapter.id]: value })), chapter.id)}<button className="dsh-btn dsh-btn--outline" type="button" disabled={working || uploadingPdf === chapter.id || draft.title.trim().length < 2 || (['quiz', 'assignment', 'pdf'].includes(draft.lesson_type) && !draft.linked_id) || (draft.lesson_type === 'pdf' && !draft.content.startsWith('school-pdf:'))} onClick={() => void addLesson(course.id, chapter.id, chapter.lessons.length)}><Plus size={13} /> Ajouter la leçon</button></div></div>
                      </div>}
                    </section>
                  })}

                  <div className="teacher-add-chapter"><input value={chapterDrafts[course.id] || ''} onChange={(event) => setChapterDrafts((current) => ({ ...current, [course.id]: event.target.value }))} placeholder="Titre du nouveau chapitre" /><button className="dsh-btn dsh-btn--outline" type="button" disabled={working || (chapterDrafts[course.id] || '').trim().length < 2} onClick={() => void addChapter(course.id, course.chapters.length)}><Plus size={13} /> Chapitre</button></div>
                </div>}
              </article>
            })}
            {session.courses.length === 0 && <div className="dsh-empty"><BookOpen size={26} /><strong>Aucun cours</strong><p>Ajoutez le premier cours de cette session ou concevez-le avec l’IA.</p></div>}
          </section>
        </>}
      </div>

      {showAiDesigner && session && (
        <div className="dsh-modal-overlay" onClick={() => !aiGenerating && !aiApplying && setShowAiDesigner(false)}>
          <div className="dsh-modal dsh-modal--xlarge teacher-ai-course-modal" onClick={(event) => event.stopPropagation()}>
            <div className="dsh-modal__header"><div><span className="section-label">Conception de cours</span><h3>Créer avec l’IA</h3><p>{selectedWorkspace?.formation_title} · {selectedWorkspace?.session_label}</p></div><button className="dsh-icon-btn" type="button" disabled={aiGenerating || aiApplying} onClick={() => setShowAiDesigner(false)}><X size={16} /></button></div>

            <div className="teacher-ai-course-body">
              {aiConnected === false ? <div className="teacher-ai-unavailable">OpenAI n’est pas connecté pour cette école. Demandez à un administrateur de l’activer dans Connect.</div> : <>
                <section className="teacher-ai-panel">
                  <div className="teacher-ai-title"><Sparkles size={17} /><div><strong>Décrire le cours à concevoir</strong><span>L’IA génère un brouillon complet que vous modifiez avant de l’enregistrer.</span></div></div>
                  <label>Sujet / brief<textarea value={aiTopic} onChange={(event) => setAiTopic(event.target.value)} placeholder="Ex. Initiation complète au motion design par la pratique" /></label>
                  <div className="teacher-form-grid two-columns"><label>Niveau<input value={aiLevel} onChange={(event) => setAiLevel(event.target.value)} placeholder="Débutant" /></label><label>Objectifs<input value={aiObjectives} onChange={(event) => setAiObjectives(event.target.value)} placeholder="Compétences visées" /></label></div>
                  <div className="teacher-form-grid two-columns"><label>Chapitres<select value={aiChaptersCount} onChange={(event) => setAiChaptersCount(Number(event.target.value))}>{[2,3,4,5,6,8,10,12].map((value) => <option key={value} value={value}>{value}</option>)}</select></label><label>Leçons / chapitre<select value={aiLessonsCount} onChange={(event) => setAiLessonsCount(Number(event.target.value))}>{[2,3,4,5,6,8,10,12].map((value) => <option key={value} value={value}>{value}</option>)}</select></label></div>
                  <button className="dsh-btn dsh-btn--ai" type="button" disabled={aiGenerating || !aiTopic.trim()} onClick={() => void generateCourseWithAI()}>{aiGenerating ? <LoaderCircle className="openai-spin" size={14} /> : <WandSparkles size={14} />} {aiGenerating ? 'Conception…' : aiDraft ? 'Régénérer le brouillon' : 'Générer le brouillon'}</button>
                </section>

                {aiDraft && <section className="teacher-ai-course-preview">
                  <div className="teacher-ai-preview-head"><div><strong>Brouillon généré</strong><span>Relisez et modifiez tout avant de l’appliquer.</span></div><span>{aiDraft.chapters.length} chapitre(s)</span></div>
                  <label>Titre du cours<input value={aiDraft.title} onChange={(event) => setAiDraft((current) => current && ({ ...current, title: event.target.value }))} /></label>
                  <label>Description<textarea value={aiDraft.description} onChange={(event) => setAiDraft((current) => current && ({ ...current, description: event.target.value }))} /></label>
                  <div className="teacher-ai-chapter-preview">{aiDraft.chapters.map((chapter, chapterIndex) => <article key={chapterIndex}><div className="teacher-ai-chapter-head"><span>{chapterIndex + 1}</span><input value={chapter.title} onChange={(event) => updateAiChapter(chapterIndex, event.target.value)} /></div><div className="teacher-ai-lesson-preview">{chapter.lessons.map((lesson, lessonIndex) => <div key={lessonIndex}><strong>Leçon {lessonIndex + 1}</strong><input value={lesson.title} onChange={(event) => updateAiLesson(chapterIndex, lessonIndex, { title: event.target.value })} /><textarea value={lesson.content} onChange={(event) => updateAiLesson(chapterIndex, lessonIndex, { content: event.target.value })} /></div>)}</div></article>)}</div>
                </section>}
              </>}
            </div>

            <div className="dsh-modal__footer"><button className="dsh-btn dsh-btn--ghost" type="button" disabled={aiGenerating || aiApplying} onClick={() => setShowAiDesigner(false)}>Fermer</button>{aiDraft && <button className="dsh-btn dsh-btn--primary" type="button" disabled={aiApplying || aiGenerating} onClick={() => void applyAiDraft()}>{aiApplying ? <LoaderCircle className="openai-spin" size={14} /> : <Plus size={14} />} {aiApplying ? 'Création du cours…' : 'Appliquer en brouillon'}</button>}</div>
          </div>
        </div>
      )}
    </main>
  )
}
