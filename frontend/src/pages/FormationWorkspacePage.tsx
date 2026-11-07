import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from 'react'
import {
  Archive,
  ArrowLeft,
  BookOpen,
  CalendarPlus,
  GraduationCap,
  ImagePlus,
  Pencil,
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
  updateFormationEnrollment,
  updateFormationSession,
  uploadSchoolAsset,
  type FormationDetail,
  type Member,
} from '../lib/api'
import { PublicProgramField } from '../components/PublicProgramField'

export function FormationWorkspacePage() {
  const params = useParams()
  const formationId = Number(params.formationId)
  const [formation, setFormation] = useState<FormationDetail | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [sessionLabel, setSessionLabel] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [capacity, setCapacity] = useState('')
  const [campus, setCampus] = useState('')
  const [description, setDescription] = useState('')
  const [shortDescription, setShortDescription] = useState('')
  const [objectives, setObjectives] = useState('')
  const [prerequisites, setPrerequisites] = useState('')
  const [coverUrl, setCoverUrl] = useState('')
  const [price, setPrice] = useState('')
  const [allowInstallments, setAllowInstallments] = useState(false)
  const [installmentCount, setInstallmentCount] = useState('3')
  const [depositEnabled, setDepositEnabled] = useState(false)
  const [depositPercent, setDepositPercent] = useState('37.5')
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
      setShortDescription(detail.short_description)
      setObjectives(detail.objectives)
      setPrerequisites(detail.prerequisites)
      setCoverUrl(detail.cover_image_url || '')
      setPrice(detail.price_cents ? String(detail.currency === 'XAF' ? detail.price_cents : detail.price_cents / 100) : '')
      setAllowInstallments(detail.allow_installments)
      setInstallmentCount(String(detail.installment_count))
      setDepositEnabled(detail.reservation_deposit_enabled)
      setDepositPercent(String(detail.reservation_deposit_percent))
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
        seat_capacity: Number(capacity),
      }))
      setSessionLabel('')
      setStartDate('')
      setEndDate('')
      setCapacity('')
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

  async function archiveFormation() {
    if (!formation) return
    const today = new Date().toISOString().slice(0, 10)
    // As on the mother site: warn about future sessions that already have students.
    const upcoming = formation.sessions.filter((session) => session.status !== 'cancelled' && session.status !== 'completed'
      && session.start_date > today && session.enrollments.some((item) => item.status === 'active'))
    const warning = upcoming.length
      ? `Ces sessions à venir ont déjà des inscrits : ${upcoming.map((session) => session.label).join(', ')}. Leurs étudiants gardent leur accès, mais la formation disparaîtra du catalogue.

`
      : ''
    if (!window.confirm(`${warning}Archiver « ${formation.title} » ? L’historique des sessions, des inscriptions et des paiements est conservé.`)) return
    setWorking(true)
    setError('')
    setMessage('')
    try {
      await updateFormation(formation.id, { status: 'archived' })
      setFormation(await getFormation(formation.id))
      setMessage('Formation archivée : elle n’apparaît plus dans le catalogue.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Archivage impossible.')
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
        short_description: shortDescription.trim(),
        objectives: objectives.trim(),
        prerequisites: prerequisites.trim(),
        cover_image_url: coverUrl || null,
        price_cents: price ? Math.round(Number(price) * (formation.currency === 'XAF' ? 1 : 100)) : 0,
        allow_installments: allowInstallments,
        installment_count: Math.min(12, Math.max(2, Number(installmentCount) || 2)),
        reservation_deposit_enabled: depositEnabled,
        reservation_deposit_percent: Math.min(99, Math.max(1, Number(depositPercent) || 37.5)),
        public_program: publicProgram.trim(),
      })
      setFormation(await getFormation(formation.id))
      setMessage('Page publique de la formation enregistrée.')
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
        <div className="formation-workspace-actions"><span className="status-chip">{formation.status === 'published' ? 'Publiée' : formation.status === 'archived' ? 'Archivée' : 'Brouillon'}{formation.format_type !== 'ligne' && ` · ${formation.session_count} session(s)`}</span>{formation.status === 'draft' && <button className="primary-button" type="button" disabled={working || formation.publication_issues.length > 0} onClick={() => void publishFormation()}><Send size={15} /> {working ? 'Publication…' : 'Publier la formation'}</button>}{formation.status !== 'archived' && <button className="secondary-button" type="button" disabled={working} onClick={() => void archiveFormation()}><Archive size={15} /> Archiver</button>}</div>
      </header>

      {error && <div className="form-error">{error}</div>}
      {message && <div className="form-success">{message} {message.startsWith('Formation publiée') && <Link to="/app/manage/site-public">Vérifier le site public</Link>}</div>}

      {formation.publication_issues.length > 0 && <section className="app-card formation-readiness"><strong>À compléter avant publication ou ouverture des inscriptions</strong>{formation.status === 'published' && <p>Les informations manquantes peuvent masquer la fiche publique ou bloquer les inscriptions.</p>}<ul>{formation.publication_issues.map((issue) => <li key={issue}>{issue}</li>)}</ul></section>}

      <form className="app-card formation-presentation" onSubmit={(event) => void savePresentation(event)}>
        <div className="settings-section-heading"><div><span className="section-label">Catalogue public</span><h2>Page de présentation de la formation</h2><p>Renseignez ici les contenus qui apparaissent sur la fiche publique de la formation.</p></div><ImagePlus size={20} /></div>
        <label className="formation-cover-picker">Photo de couverture
          {coverUrl && <img src={coverUrl} alt="Couverture de la formation" />}
          <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={(event) => void uploadCover(event)} disabled={working} />
        </label>
        <label>Prix ({formation.currency})<input type="number" min={formation.currency === 'XAF' ? '1' : '0.01'} step={formation.currency === 'XAF' ? '1' : '0.01'} value={price} onChange={(event) => setPrice(event.target.value)} placeholder={formation.currency === 'XAF' ? 'Ex. 150000' : 'Ex. 250.00'} /></label>
        <fieldset className="formation-payment-options">
          <legend>Modalités de paiement</legend>
          <label className="formation-payment-toggle"><input type="checkbox" checked={allowInstallments} onChange={(event) => setAllowInstallments(event.target.checked)} /> Autoriser le paiement en plusieurs fois</label>
          {allowInstallments && <label>Nombre maximal de paiements<input type="number" min={2} max={12} step={1} value={installmentCount} onChange={(event) => setInstallmentCount(event.target.value)} /></label>}
          {allowInstallments && formation.format_type !== 'ligne' && <small>Comme sur le site mère, la durée de chaque session plafonne ce nombre : un seul paiement sous un mois, 2 pour un mois, 3 au-delà. La dernière échéance tombe 5 jours avant la fin de la session.</small>}
          {allowInstallments && formation.format_type === 'ligne' && <small>Les paiements sont espacés d’un mois.</small>}
          {formation.format_type === 'live' && <>
            <label className="formation-payment-toggle"><input type="checkbox" checked={depositEnabled} onChange={(event) => setDepositEnabled(event.target.checked)} /> Réserver une place avec un acompte</label>
            {depositEnabled && <label>Acompte (% du prix)<input type="number" min={1} max={99} step={0.5} value={depositPercent} onChange={(event) => setDepositPercent(event.target.value)} /></label>}
            {depositEnabled && <small>Comme sur le site mère, l’acompte non remboursable réserve la place quand la session commence dans plus de 10 jours. Le solde est dû 10 jours avant le début : sans lui, l’accès est suspendu mais la place reste gardée. Les montants en XAF sont arrondis à 500 FCFA.</small>}
          </>}
        </fieldset>
        <label>Description générale<textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={5000} rows={5} placeholder="Présentez la formation, sa promesse et son approche pédagogique." /></label>
        <label>Résumé court<textarea value={shortDescription} onChange={(event) => setShortDescription(event.target.value)} maxLength={500} rows={3} placeholder="Texte court affiché dans l’introduction et sur les cartes du catalogue." /><small>{shortDescription.length}/500 caractères</small></label>
        <label>À la fin de cette formation, l’apprenant sera capable de…<textarea value={objectives} onChange={(event) => setObjectives(event.target.value)} maxLength={10000} rows={6} placeholder={'Concevoir une application complète\nAutomatiser des tâches métier\nCréer une interface professionnelle'} /><small>Un acquis par ligne pour un affichage clair sur le site public.</small></label>
        <label>À qui s’adresse cette formation ? / Prérequis<textarea value={prerequisites} onChange={(event) => setPrerequisites(event.target.value)} maxLength={10000} rows={5} placeholder="Décrivez le public cible, le niveau attendu et les éventuels prérequis." /></label>
        <PublicProgramField
          formationId={formation.id}
          value={publicProgram}
          disabled={working}
          onSaved={(detail) => {
            setFormation(detail)
            setPublicProgram(detail.public_program)
            setMessage('Programme public enregistré. L’accordéon de la fiche publique est à jour.')
          }}
        />
        <button className="primary-button" type="submit" disabled={working}><Save size={15} /> Enregistrer la page publique</button>
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
            Places
            <input type="number" min={1} value={capacity} onChange={(e) => setCapacity(e.target.value)} required />
          </label>
          {formation.format_type === 'presentiel' && (
            <label>
              Lieu
              <input value={campus} onChange={(e) => setCampus(e.target.value)} required placeholder="Bonamoussadi" />
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
  const [accessStartDate, setAccessStartDate] = useState(session.start_date)
  const [accessEndDate, setAccessEndDate] = useState(session.end_date)
  const [editLabel, setEditLabel] = useState(session.label)
  const [editCapacity, setEditCapacity] = useState(String(session.seat_capacity))
  const [editCampus, setEditCampus] = useState(session.campus_label ?? '')
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setAccessStartDate(session.start_date)
    setAccessEndDate(session.end_date)
  }, [session.start_date, session.end_date])

  useEffect(() => {
    setEditLabel(session.label)
    setEditCapacity(String(session.seat_capacity))
    setEditCampus(session.campus_label ?? '')
  }, [session.label, session.seat_capacity, session.campus_label])

  const assignedTeacherIds = new Set(session.teachers.map((item) => item.teacher_id))
  const invalidAccessPeriod = !accessStartDate || !accessEndDate || accessEndDate < accessStartDate
  const isOnsite = formation.format_type === 'presentiel'
  const sessionUnchanged = editLabel.trim() === session.label
    && accessStartDate === session.start_date
    && accessEndDate === session.end_date
    && Number(editCapacity) === session.seat_capacity
    && (!isOnsite || editCampus.trim() === (session.campus_label ?? ''))

  function saveSession(event: FormEvent) {
    event.preventDefault()
    void run(() => updateFormationSession(formation.id, session.id, {
      label: editLabel.trim(),
      start_date: accessStartDate,
      end_date: accessEndDate,
      seat_capacity: Number(editCapacity),
      ...(isOnsite ? { campus_label: editCampus.trim() } : {}),
    }))
  }

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
          <p>
            {new Date(session.start_date).toLocaleDateString('fr-FR')}
            {' → '}
            {new Date(session.end_date).toLocaleDateString('fr-FR')}
            {session.seat_capacity > 0 ? ` · ${session.enrollments.length}/${session.seat_capacity} places` : ''}
            {isOnsite && session.campus_label ? ` · ${session.campus_label}` : ''}
          </p>
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

      {formation.format_type !== 'ligne' && <details className="session-edit-panel">
        <summary><Pencil size={14} /> Modifier la session</summary>
        <form className="session-create-grid" onSubmit={saveSession}>
          <label>
            Nom de session
            <input value={editLabel} onChange={(e) => setEditLabel(e.target.value)} required minLength={2} />
          </label>
          <label>
            Début
            <input type="date" value={accessStartDate} onChange={(e) => setAccessStartDate(e.target.value)} required />
          </label>
          <label>
            Fin
            <input type="date" value={accessEndDate} min={accessStartDate || undefined} onChange={(e) => setAccessEndDate(e.target.value)} required />
          </label>
          <label>
            Places
            <input type="number" min={1} value={editCapacity} onChange={(e) => setEditCapacity(e.target.value)} required />
          </label>
          {isOnsite && (
            <label>
              Lieu
              <input value={editCampus} onChange={(e) => setEditCampus(e.target.value)} required placeholder="Bonamoussadi" />
            </label>
          )}
          <button className="secondary-button" disabled={working || invalidAccessPeriod || sessionUnchanged}>
            <Save size={14} /> Enregistrer
          </button>
        </form>
      </details>}

      {formation.format_type === 'ligne' && <section className="online-access-period">
        <div>
          <span className="section-label">Période d’accès</span>
          <h3>Dates d’accès étudiant</h3>
          <p className="muted-note">Ces deux dates sont celles affichées dans « Mes sessions programmées ».</p>
        </div>
        <div className="online-access-period__fields">
          <label>Début<input type="date" value={accessStartDate} onChange={(event) => setAccessStartDate(event.target.value)} /></label>
          <label>Fin<input type="date" value={accessEndDate} min={accessStartDate || undefined} onChange={(event) => setAccessEndDate(event.target.value)} /></label>
          <button
            className="secondary-button"
            type="button"
            disabled={working || invalidAccessPeriod || (accessStartDate === session.start_date && accessEndDate === session.end_date)}
            onClick={() => void run(() => updateFormationSession(formation.id, session.id, {
              start_date: accessStartDate,
              end_date: accessEndDate,
            }))}
          ><Save size={14} /> Enregistrer les dates</button>
        </div>
      </section>}

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
            {formation.format_type === 'ligne' ? 'Les étudiants accèdent automatiquement à la formation après leur achat sur le site public.' : 'Les étudiants sont inscrits après leur achat. Validez leur parcours à la fin de la session pour ouvrir le certificat si les acquis sont remplis.'}
          </p>
          <div className="compact-person-list">
            {session.enrollments.filter((item) => item.status !== 'cancelled').map((item) => (
              <span key={item.id}>
                <strong>{item.student_name}</strong>
                <small>{item.status === 'completed' ? 'Parcours validé' : item.status === 'active' ? 'En cours' : item.status}</small>
                {formation.format_type !== 'ligne' && item.status === 'active' && (
                  <button
                    className="enrollment-complete-button"
                    type="button"
                    disabled={working || session.status === 'cancelled'}
                    onClick={() => void run(() => updateFormationEnrollment(formation.id, session.id, item.id, 'completed'))}
                  >Valider le parcours</button>
                )}
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
