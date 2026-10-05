import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from 'react'
import {
  ArrowLeft,
  BookOpen,
  CalendarPlus,
  GraduationCap,
  ImagePlus,
  Plus,
  Save,
  Send,
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
  getFormation,
  listMembers,
  updateFormation,
  updateFormationSession,
  uploadSchoolAsset,
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
  const [description, setDescription] = useState('')
  const [coverUrl, setCoverUrl] = useState('')
  const [price, setPrice] = useState('')
  const [publicProgram, setPublicProgram] = useState('')
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function refresh() {
    try {
      const [detail, team] = await Promise.all([
        getFormation(formationId),
        listMembers(),
      ])
      setFormation(detail)
      setDescription(detail.description)
      setCoverUrl(detail.cover_image_url || '')
      setPrice(detail.price_cents ? String(detail.currency === 'XAF' ? detail.price_cents : detail.price_cents / 100) : '')
      setPublicProgram(detail.public_program)
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

  async function publishFormation() {
    if (!formation) return
    setWorking(true)
    setError('')
    setMessage('')
    try {
      await updateFormation(formation.id, { status: 'published' })
      setFormation(await getFormation(formation.id))
      setMessage('Formation publiée. Vérifiez aussi que le site public de l’école est publié.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Publication impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function savePresentation(event: FormEvent) {
    event.preventDefault()
    if (!formation) return
    setWorking(true)
    setError('')
    setMessage('')
    try {
      await updateFormation(formation.id, {
        description: description.trim(),
        cover_image_url: coverUrl || null,
        price_cents: price ? Math.round(Number(price) * (formation.currency === 'XAF' ? 1 : 100)) : 0,
        public_program: publicProgram.trim(),
      })
      setFormation(await getFormation(formation.id))
      setMessage('Présentation enregistrée.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Enregistrement impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function uploadCover(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setWorking(true)
    setError('')
    try {
      const asset = await uploadSchoolAsset(file)
      setCoverUrl(asset.public_url)
      setMessage('Photo importée. Enregistrez la présentation pour l’utiliser.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Import de la photo impossible.')
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
        <div className="formation-workspace-actions"><span className="status-chip">{formation.status === 'published' ? 'Publiée' : 'Brouillon'}{formation.format_type !== 'ligne' && ` · ${formation.session_count} session(s)`}</span>{formation.status === 'draft' && <button className="primary-button" type="button" disabled={working || formation.publication_issues.length > 0} onClick={() => void publishFormation()}><Send size={15} /> {working ? 'Publication…' : 'Publier la formation'}</button>}</div>
      </header>

      {error && <div className="form-error">{error}</div>}
      {message && <div className="form-success">{message} {message.startsWith('Formation publiée') && <Link to="/app/manage/site-public">Vérifier le site public</Link>}</div>}

      {formation.publication_issues.length > 0 && <section className="app-card formation-readiness"><strong>À compléter avant publication ou ouverture des inscriptions</strong>{formation.status === 'published' && <p>Les informations manquantes peuvent masquer la fiche publique ou bloquer les inscriptions.</p>}<ul>{formation.publication_issues.map((issue) => <li key={issue}>{issue}</li>)}</ul></section>}

      <form className="app-card formation-presentation" onSubmit={(event) => void savePresentation(event)}>
        <div className="settings-section-heading"><div><span className="section-label">Catalogue public</span><h2>Présentation et prix</h2></div><ImagePlus size={20} /></div>
        <label className="formation-cover-picker">Photo de couverture
          {coverUrl && <img src={coverUrl} alt="Couverture de la formation" />}
          <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={(event) => void uploadCover(event)} disabled={working} />
        </label>
        <label>Prix ({formation.currency})<input type="number" min={formation.currency === 'XAF' ? '1' : '0.01'} step={formation.currency === 'XAF' ? '1' : '0.01'} value={price} onChange={(event) => setPrice(event.target.value)} placeholder={formation.currency === 'XAF' ? 'Ex. 150000' : 'Ex. 250.00'} /></label>
        <label>Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={5000} /></label>
        <label>Programme public<textarea value={publicProgram} onChange={(event) => setPublicProgram(event.target.value)} maxLength={30000} placeholder="Contenu et objectifs présentés aux futurs étudiants" /></label>
        <button className="primary-button" type="submit" disabled={working}><Save size={15} /> Enregistrer la présentation</button>
      </form>

      {formation.format_type !== 'ligne' && <section className="app-card session-create-card">
        <div className="settings-section-heading">
          <div>
            <span className="section-label">Cohorte / session</span>
            <h2>Créer une session</h2>
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
      </section>}

      <section className="session-list">
        {formation.sessions.map((session) => (
          <SessionWorkspace
            key={session.id}
            formation={formation}
            session={session}
            teachers={teachers}
            onChange={setFormation}
          />
        ))}
        {formation.sessions.length === 0 && (
          <div className="app-card formation-empty">
            <CalendarPlus size={26} />
            <strong>Aucune session</strong>
            <p>{formation.format_type === 'ligne' ? 'Actualisez la page pour charger le contenu pédagogique.' : 'Ouvrez une cohorte pour commencer à affecter professeurs et étudiants.'}</p>
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
  onChange,
}: {
  formation: FormationDetail
  session: FormationDetail['sessions'][number]
  teachers: Member[]
  onChange: (value: FormationDetail) => void
}) {
  const [teacherId, setTeacherId] = useState('')
  const [courseTitle, setCourseTitle] = useState('')
  const [courseTeacherId, setCourseTeacherId] = useState('')
  const [chapterTitles, setChapterTitles] = useState<Record<number, string>>({})
  const [lessonTitles, setLessonTitles] = useState<Record<number, string>>({})
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')

  const assignedTeacherIds = new Set(session.teachers.map((item) => item.teacher_id))

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
          <span className="section-label">{formation.format_type === 'ligne' ? 'Contenu pédagogique' : session.status === 'open' ? 'Inscriptions ouvertes' : session.status === 'planned' ? 'Inscriptions fermées' : session.status}</span>
          <h2>{formation.format_type === 'ligne' ? formation.title : session.label}</h2>
          {formation.format_type !== 'ligne' && <p>
            {new Date(session.start_date).toLocaleDateString('fr-FR')}
            {' → '}
            {new Date(session.end_date).toLocaleDateString('fr-FR')}
            {session.seat_capacity > 0 ? ` · ${session.enrollments.length}/${session.seat_capacity} places` : ''}
          </p>}
        </div>
        <div className="session-workspace-stats">
          <span><GraduationCap size={14} /> {session.teachers.length}</span>
          <span><Users size={14} /> {session.enrollments.filter((item) => item.status === 'active').length}</span>
          <span><BookOpen size={14} /> {session.courses.length}</span>
        </div>
        {formation.format_type !== 'ligne' && (session.status === 'planned' || session.status === 'open') && <button
          className="secondary-button"
          type="button"
          disabled={working || (session.status === 'planned' && (formation.status !== 'published' || formation.publication_issues.length > 0))}
          onClick={() => void run(() => updateFormationSession(formation.id, session.id, { status: session.status === 'open' ? 'planned' : 'open' }))}
        >{session.status === 'open' ? 'Fermer les inscriptions' : 'Ouvrir les inscriptions'}</button>}
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
          <p className="muted-note">
            {formation.format_type === 'ligne' ? 'Les étudiants accèdent automatiquement à la formation après leur achat sur le site public.' : 'Les étudiants sont inscrits automatiquement dans cette session après leur achat sur le site public.'}
          </p>
          <div className="compact-person-list">
            {session.enrollments.filter((item) => item.status !== 'cancelled').map((item) => (
              <span key={item.id}>
                <strong>{item.student_name}</strong>
                <small>{item.status}</small>
              </span>
            ))}
            {session.enrollments.length === 0 && <small>{formation.format_type === 'ligne' ? 'Aucun achat confirmé pour cette formation.' : 'Aucun achat confirmé pour cette session.'}</small>}
          </div>
          <Link className="secondary-button compact-action" to="/app/manage/students">
            Voir la gestion des étudiants
          </Link>
        </section>
      </div>

      <section className="session-course-section">
        <div className="settings-section-heading">
          <div>
            <span className="section-label">Contenu pédagogique</span>
            <h3>{formation.format_type === 'ligne' ? 'Cours de la formation' : 'Cours de la session'}</h3>
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
          {session.courses.length === 0 && <div className="empty-row">{formation.format_type === 'ligne' ? 'Aucun cours dans cette formation.' : 'Aucun cours dans cette session.'}</div>}
        </div>
      </section>
    </article>
  )
}
