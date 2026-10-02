import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, ChevronDown, ChevronRight, ExternalLink, PlayCircle } from 'lucide-react'
import {
  ApiError,
  completeStudentLesson,
  listStudentLearning,
  type LearningLesson,
  type LearningSession,
} from '../lib/api'

export function StudentCoursesPage() {
  const [sessions, setSessions] = useState<LearningSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null)
  const [activeLesson, setActiveLesson] = useState<LearningLesson | null>(null)
  const [openChapters, setOpenChapters] = useState<Set<number>>(new Set())
  const [error, setError] = useState('')

  useEffect(() => {
    listStudentLearning().then((rows) => {
      setSessions(rows)
      setActiveSessionId(rows[0]?.session_id ?? null)
      const firstLesson = rows[0]?.courses[0]?.chapters[0]?.lessons[0] ?? null
      setActiveLesson(firstLesson)
      if (rows[0]?.courses[0]?.chapters[0]) setOpenChapters(new Set([rows[0].courses[0].chapters[0].id]))
    }).catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [])

  const session = useMemo(() => sessions.find((item) => item.session_id === activeSessionId) ?? null,[sessions,activeSessionId])

  async function complete() {
    if (!activeLesson) return
    try {
      const updated = await completeStudentLesson(activeLesson.id)
      setSessions((current) => current.map((item) => item.session_id === updated.session_id ? updated : item))
      setActiveLesson((current) => current ? { ...current, completed: true } : current)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Validation impossible.')
    }
  }

  function renderLesson(lesson: LearningLesson) {
    if (lesson.lesson_type === 'video' && lesson.video_url) {
      return <video className="student-reader-video" src={lesson.video_url} controls preload="metadata" />
    }
    if (lesson.file_url) {
      return <a className="primary-button" href={lesson.file_url} target="_blank" rel="noreferrer"><ExternalLink size={14}/> Ouvrir le document</a>
    }
    return <div className="student-reader-text">{lesson.content || 'Aucun contenu textuel.'}</div>
  }

  return (
    <main className="app-page student-reader-page">
      <header className="app-page-header">
        <div><span className="page-kicker">Espace étudiant</span><h1>Mes cours</h1><p>Avancez module par module et validez les leçons terminées.</p></div>
      </header>
      {error && <div className="form-error">{error}</div>}
      <label className="academic-session-select">Formation<select value={activeSessionId ?? ''} onChange={(event) => { const id=Number(event.target.value);setActiveSessionId(id);const target=sessions.find((item)=>item.session_id===id);setActiveLesson(target?.courses[0]?.chapters[0]?.lessons[0] ?? null) }}>{sessions.map((item)=><option key={item.session_id} value={item.session_id}>{item.formation_title} · {item.session_label}</option>)}</select></label>

      {session && (
        <section className="student-reader-layout">
          <aside className="app-card student-reader-nav">
            {session.courses.map((course) => (
              <div key={course.id}>
                <h3>{course.title}</h3>
                {course.chapters.map((chapter) => {
                  const open=openChapters.has(chapter.id)
                  return <div className="student-reader-chapter" key={chapter.id}>
                    <button type="button" onClick={()=>setOpenChapters((current)=>{const next=new Set(current);if(next.has(chapter.id))next.delete(chapter.id);else next.add(chapter.id);return next})}>{open?<ChevronDown size={14}/>:<ChevronRight size={14}/>} Module {chapter.order_index+1} · {chapter.title}</button>
                    {open && <div>{chapter.lessons.map((lesson)=><button type="button" className={activeLesson?.id===lesson.id?'is-active':''} key={lesson.id} onClick={()=>setActiveLesson(lesson)}>{lesson.completed?<CheckCircle2 size={13}/>:<PlayCircle size={13}/>}<span>{lesson.title}</span></button>)}</div>}
                  </div>
                })}
              </div>
            ))}
          </aside>

          <article className="app-card student-reader-content">
            {activeLesson ? <>
              <div className="student-reader-heading"><div><span className="section-label">{activeLesson.lesson_type}</span><h2>{activeLesson.title}</h2></div>{activeLesson.completed&&<span className="assignment-status reviewed"><CheckCircle2 size={13}/>Terminée</span>}</div>
              {renderLesson(activeLesson)}
              {!activeLesson.completed && <button type="button" className="primary-button student-complete-button" onClick={()=>void complete()}><CheckCircle2 size={14}/> Marquer comme terminée</button>}
            </> : <div className="formation-empty">Sélectionnez une leçon.</div>}
          </article>
        </section>
      )}
    </main>
  )
}
