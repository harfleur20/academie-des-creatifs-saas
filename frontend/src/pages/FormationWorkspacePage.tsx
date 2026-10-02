import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  ArrowLeft,
  BookOpen,
  CalendarPlus,
  GraduationCap,
  Plus,
  UserPlus,
  Users,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import {
  ApiError,
  assignSessionTeacher,
  createChapterLesson,
  createCourseChapter,
  createFormationSession,
  createSessionCourse,
  enrollSessionStudent,
  getFormation,
  listMembers,
  type FormationDetail,
  type Member,
} from '../lib/api'

export function FormationWorkspacePage() {
  const params = useParams()
  const formationId = Number(params.formationId)
  const [formation, setFormation] = useState<FormationDetail | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [sessionLabel, setSessionLabel] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [capacity, setCapacity] = useState('0')
  const [campus, setCampus] = useState('')
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')

  async function refresh() {
    try {
      const [detail, team] = await Promise.all([
        getFormation(formationId),
        listMembers(),
      ])
      setFormation(detail)
      setMembers(team)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de charger la formation.')
    }
  }

  useEffect(() => {
    if (Number.isInteger(formationId)) void refresh()
  }, [formationId])

  const teachers = useMemo(
    () => members.filter((item) => item.status === 'active' && item.role === 'teacher'),
    [members],
  )
  const students = useMemo(
    () => members.filter((item) => item.status === 'active' && item.role === 'student'),
    [members],
  )

  async function createSession(event: FormEvent) {
    event.preventDefault()
    if (!formation) return
    setWorking(true)
    setError('')
    try {
      setFormation(await createFormationSession(formation.id, {
        label: sessionLabel.trim(),
        start_date: startDate,
        end_date: endDate,
        campus_label: campus.trim() || null,
        seat_capacity: Number(capacity || 0),
      }))
      setSessionLabel('')
      setStartDate('')
      setEndDate('')
      setCapacity('0')
      setCampus('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Création de session impossible.')
    } finally {
      setWorking(false)
    }
  }

  if (!formation && !error) return <div className="page-state">Chargement de la formation…</div>
  if (!formation) return <main className="app-page"><div className="form-error">{error}</div></main>

  return (
    <main className="app-page formation-workspace-page">
      <Link className="admin-back-link" to="/app/manage/formations">
        <ArrowLeft size={15} /> Toutes les formations
      </Link>

      <header className="app-page-header">
        <div>
          <span className="page-kicker">{formation.format_type}</span>
          <h1>{formation.title}</h1>
          <p>{formation.description || 'Aucune description.'}</p>
        </div>
        <span className="status-chip">{formation.session_count} session(s)</span>
      </header>

      {error && <div className="form-error">{error}</div>}

      <section className="app-card session-create-card">
        <div className="settings-section-heading">
          <div>
            <span className="section-label">Cohorte / session</span>
            <h2>Ouvrir une nouvelle session</h2>
          </div>
          <CalendarPlus size={20} />
        </div>

        <form className="session-create-grid" onSubmit={createSession}>
          <label>
            Nom de session
            <input value={sessionLabel} onChange={(e) => setSessionLabel(e.target.value)} required placeholder="Cohorte Octobre 2026" />
          </label>
          <label>
            Début
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
          </label>
          <label>
            Fin
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} required />
          </label>
          <label>
            Capacité
            <input type="number" min={0} value={capacity} onChange={(e) => setCapacity(e.target.value)} />
          </label>
          {formation.format_type === 'presentiel' && (
            <label>
              Campus
              <input value={campus} onChange={(e) => setCampus(e.target.value)} placeholder="Bonamoussadi" />
            </label>
          )}
          <button className="primary-button" disabled={working}>
            <Plus size={15} /> Créer la session
          </button>
        </form>
      </section>

      <section className="session-list">
        {formation.sessions.map((session) => (
          <SessionWorkspace
            key={session.id}
            formation={formation}
            session={session}
            teachers={teachers}
            students={students}
            onChange={setFormation}
          />
        ))}
        {formation.sessions.length === 0 && (
          <div className="app-card formation-empty">
            <CalendarPlus size={26} />
            <strong>Aucune session</strong>
            <p>Ouvrez une cohorte pour commencer à affecter professeurs et étudiants.</p>
          </div>
        )}
      </section>
    </main>
  )
}

function SessionWorkspace({
  formation,
  session,
  teachers,
  students,
  onChange,
}: {
  formation: FormationDetail
  session: FormationDetail['sessions'][number]
  teachers: Member[]
  students: Member[]
  onChange: (value: FormationDetail) => void
}) {
  const [teacherId, setTeacherId] = useState('')
  const [studentId, setStudentId] = useState('')
  const [courseTitle, setCourseTitle] = useState('')
  const [courseTeacherId, setCourseTeacherId] = useState('')
  const [chapterTitles, setChapterTitles] = useState<Record<number, string>>({})
  const [lessonTitles, setLessonTitles] = useState<Record<number, string>>({})
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')

  const assignedTeacherIds = new Set(session.teachers.map((item) => item.teacher_id))
  const enrolledStudentIds = new Set(
    session.enrollments
      .filter((item) => item.status !== 'cancelled')
      .map((item) => item.student_id),
  )

  async function run(action: () => Promise<FormationDetail>) {
    setWorking(true)
    setError('')
    try {
      onChange(await action())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Action impossible.')
    } finally {
      setWorking(false)
    }
  }

  return (
    <article className="app-card session-workspace-card">
      <header className="session-workspace-heading">
        <div>
          <span className="section-label">{session.status}</span>
          <h2>{session.label}</h2>
          <p>
            {new Date(session.start_date).toLocaleDateString('fr-FR')}
            {' → '}
            {new Date(session.end_date).toLocaleDateString('fr-FR')}
            {session.seat_capacity > 0 ? ` · ${session.enrollments.length}/${session.seat_capacity} places` : ''}
          </p>
        </div>
        <div className="session-workspace-stats">
          <span><GraduationCap size={14} /> {session.teachers.length}</span>
          <span><Users size={14} /> {session.enrollments.filter((item) => item.status === 'active').length}</span>
          <span><BookOpen size={14} /> {session.courses.length}</span>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}

      <div className="session-management-grid">
        <section>
          <h3>Professeurs</h3>
          <div className="inline-management-form">
            <select value={teacherId} onChange={(e) => setTeacherId(e.target.value)}>
              <option value="">Choisir un professeur</option>
              {teachers.filter((item) => !assignedTeacherIds.has(item.user_id)).map((item) => (
                <option key={item.id} value={item.user_id}>{item.user.full_name}</option>
              ))}
            </select>
            <button
              className="secondary-button"
              type="button"
              disabled={!teacherId || working}
              onClick={() => void run(() => assignSessionTeacher(
                formation.id,
                session.id,
                Number(teacherId),
                session.teachers.length === 0 ? 'principal' : 'intervenant',
              )).then(() => setTeacherId(''))}
            >
              <UserPlus size={14} /> Affecter
            </button>
          </div>
          <div className="compact-person-list">
            {session.teachers.map((item) => (
              <span key={item.id}>
                <strong>{item.teacher_name}</strong>
                <small>{item.role}</small>
              </span>
            ))}
            {session.teachers.length === 0 && <small>Aucun professeur affecté.</small>}
          </div>
        </section>

        <section>
          <h3>Étudiants</h3>
          <div className="inline-management-form">
            <select value={studentId} onChange={(e) => setStudentId(e.target.value)}>
              <option value="">Choisir un étudiant</option>
              {students.filter((item) => !enrolledStudentIds.has(item.user_id)).map((item) => (
                <option key={item.id} value={item.user_id}>{item.user.full_name}</option>
              ))}
            </select>
            <button
              className="secondary-button"
              type="button"
              disabled={!studentId || working}
              onClick={() => void run(() => enrollSessionStudent(
                formation.id,
                session.id,
                Number(studentId),
              )).then(() => setStudentId(''))}
            >
              <UserPlus size={14} /> Inscrire
            </button>
          </div>
          <div className="compact-person-list">
            {session.enrollments.filter((item) => item.status !== 'cancelled').map((item) => (
              <span key={item.id}>
                <strong>{item.student_name}</strong>
                <small>{item.status}</small>
              </span>
            ))}
            {session.enrollments.length === 0 && <small>Aucun étudiant inscrit.</small>}
          </div>
        </section>
      </div>

      <section className="session-course-section">
        <div className="settings-section-heading">
          <div>
            <span className="section-label">Contenu pédagogique</span>
            <h3>Cours de la session</h3>
          </div>
        </div>

        <div className="course-create-row">
          <input value={courseTitle} onChange={(e) => setCourseTitle(e.target.value)} placeholder="Nom du cours" />
          <select value={courseTeacherId} onChange={(e) => setCourseTeacherId(e.target.value)}>
            <option value="">Professeur non défini</option>
            {session.teachers.map((item) => (
              <option key={item.id} value={item.teacher_id}>{item.teacher_name}</option>
            ))}
          </select>
          <button
            className="primary-button"
            type="button"
            disabled={courseTitle.trim().length < 2 || working}
            onClick={() => void run(() => createSessionCourse(
              formation.id,
              session.id,
              {
                title: courseTitle.trim(),
                teacher_id: courseTeacherId ? Number(courseTeacherId) : null,
              },
            )).then(() => {
              setCourseTitle('')
              setCourseTeacherId('')
            })}
          >
            <Plus size={14} /> Ajouter le cours
          </button>
        </div>

        <div className="course-list">
          {session.courses.map((course) => (
            <article className="course-card" key={course.id}>
              <div className="course-card-heading">
                <div>
                  <strong>{course.title}</strong>
                  <small>{course.teacher_name || 'Professeur non affecté'}</small>
                </div>
                <span>{course.chapters.length} module(s)</span>
              </div>

              <div className="module-list">
                {course.chapters.map((chapter) => (
                  <div className="module-item" key={chapter.id}>
                    <strong>{chapter.title}</strong>
                    <small>{chapter.lessons.length} leçon(s)</small>
                    <div className="lesson-list">
                      {chapter.lessons.map((lesson) => (
                        <span key={lesson.id}>{lesson.title} · {lesson.lesson_type}</span>
                      ))}
                    </div>
                    <div className="inline-management-form">
                      <input
                        value={lessonTitles[chapter.id] || ''}
                        onChange={(e) => setLessonTitles((current) => ({ ...current, [chapter.id]: e.target.value }))}
                        placeholder="Nouvelle leçon"
                      />
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={(lessonTitles[chapter.id] || '').trim().length < 2 || working}
                        onClick={() => void run(() => createChapterLesson(
                          formation.id,
                          session.id,
                          course.id,
                          chapter.id,
                          {
                            title: (lessonTitles[chapter.id] || '').trim(),
                            order_index: chapter.lessons.length,
                            lesson_type: 'text',
                            content: '',
                          },
                        )).then(() => setLessonTitles((current) => ({ ...current, [chapter.id]: '' })))}
                      >
                        <Plus size={13} /> Leçon
                      </button>
                    </div>
                  </div>
                ))}

                <div className="inline-management-form">
                  <input
                    value={chapterTitles[course.id] || ''}
                    onChange={(e) => setChapterTitles((current) => ({ ...current, [course.id]: e.target.value }))}
                    placeholder="Nouveau module"
                  />
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={(chapterTitles[course.id] || '').trim().length < 2 || working}
                    onClick={() => void run(() => createCourseChapter(
                      formation.id,
                      session.id,
                      course.id,
                      {
                        title: (chapterTitles[course.id] || '').trim(),
                        order_index: course.chapters.length,
                      },
                    )).then(() => setChapterTitles((current) => ({ ...current, [course.id]: '' })))}
                  >
                    <Plus size={13} /> Module
                  </button>
                </div>
              </div>
            </article>
          ))}
          {session.courses.length === 0 && <div className="empty-row">Aucun cours dans cette session.</div>}
        </div>
      </section>
    </article>
  )
}
