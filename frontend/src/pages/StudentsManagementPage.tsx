import { useEffect, useMemo, useState } from 'react'
import { activeSchoolLocale } from '../app/schoolLocale'
import { BookOpen, CalendarDays, Clock3, Eye, GraduationCap, Search, ShieldCheck, ShieldOff, UserRoundCheck, Users, X } from 'lucide-react'
import { ApiError, listManagedStudents, updateMember, type ManagedStudent } from '../lib/api'
import { formatSchoolMoney } from '../public/publicHelpers'
import { toast } from '../ui/toast'
import '../management-profiles.css'

function formatDateTime(value: string | null | undefined) {
  if (!value) return 'Non renseigné'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Non renseigné' : new Intl.DateTimeFormat(activeSchoolLocale(), { dateStyle: 'long', timeStyle: 'short' }).format(date)
}

function enrollmentStatus(status: string) {
  if (status === 'active') return 'En cours'
  if (status === 'completed') return 'Terminée'
  if (status === 'cancelled') return 'Annulée'
  return status
}

function StudentAvatar({ student, large = false }: { student: ManagedStudent; large?: boolean }) {
  const initials = student.full_name.split(' ').filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
  return <span className={`management-avatar${large ? ' management-avatar--large' : ''}`}>
    {student.avatar_url ? <img src={student.avatar_url} alt="" /> : <span>{initials || '?'}</span>}
  </span>
}

export function StudentsManagementPage() {
  const [items, setItems] = useState<ManagedStudent[]>([])
  const [query, setQuery] = useState(() => new URLSearchParams(window.location.search).get('q') ?? '')
  const [error, setError] = useState('')
  const [selectedStudent, setSelectedStudent] = useState<ManagedStudent | null>(null)
  const [workingId, setWorkingId] = useState<number | null>(null)

  async function load() {
    setItems(await listManagedStudents())
  }

  useEffect(() => {
    void load().catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? items.filter((item) => [item.full_name, item.email, item.student_code].some((value) => value.toLowerCase().includes(q))) : items
  }, [items, query])

  async function toggleAccess(student: ManagedStudent) {
    if (!student.member_id || workingId !== null) return
    const nextStatus = student.membership_status === 'suspended' ? 'active' : 'suspended'
    setWorkingId(student.user_id)
    setError('')
    try {
      await updateMember(student.member_id, { status: nextStatus })
      const updated: ManagedStudent = { ...student, membership_status: nextStatus }
      setItems((current) => current.map((item) => item.user_id === student.user_id ? updated : item))
      setSelectedStudent((current) => current?.user_id === student.user_id ? updated : current)
      toast.success(nextStatus === 'suspended' ? 'Accès de l’étudiant suspendu pour cette école.' : 'Accès de l’étudiant rétabli.')
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Modification de l’accès impossible.'
      setError(message)
      toast.error(message)
    } finally {
      setWorkingId(null)
    }
  }

  const selectedAccessSuspended = selectedStudent?.membership_status === 'suspended'

  return <main className="app-page">
    <header className="app-page-header"><div><span className="page-kicker">Gestion des étudiants</span><h1>{items.length} étudiant(s)</h1><p>Les étudiants apparaissent ici après leur première inscription à une formation.</p></div></header>
    {error && <div className="form-error">{error}</div>}
    <div className="admin-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nom, email ou matricule…" /></div>
    <section className="app-card managed-student-table">
      <div className="managed-student-row is-head"><span>Étudiant</span><span>Matricule</span><span>Formations</span><span>Payé</span><span>Reste</span><span>Accès</span><span>Actions</span></div>
      {filtered.map((student) => <div className="managed-student-row" key={student.user_id}>
        <div className="member-person"><StudentAvatar student={student} /><span><strong>{student.full_name}</strong><small>{student.email}</small></span></div>
        <strong>{student.student_code}</strong>
        <span>{student.active_enrollments} en cours · {student.completed_enrollments} terminée(s)</span>
        <span>{student.totals_by_currency.length ? student.totals_by_currency.map((row) => formatSchoolMoney(row.collected_cents, row.currency)).join(' · ') : '—'}</span>
        <span>{student.totals_by_currency.length ? student.totals_by_currency.map((row) => formatSchoolMoney(row.outstanding_cents, row.currency)).join(' · ') : '—'}</span>
        <span className={`student-access-status ${student.membership_status === 'suspended' ? 'suspended' : student.status}`}><UserRoundCheck size={13} />{student.membership_status === 'suspended' ? 'Suspendu' : student.status === 'suspended_payment' ? 'Impayé' : 'Actif'}</span>
        <span className="management-row-actions">
          <button className="secondary-button compact-action" type="button" onClick={() => setSelectedStudent(student)}><Eye size={14} /> Fiche</button>
          <button className="text-danger-button" type="button" disabled={!student.member_id || workingId !== null} onClick={() => void toggleAccess(student)} title={student.membership_status === 'suspended' ? 'Rétablir l’accès dans cette école' : 'Suspendre l’accès dans cette école'}>
            {student.membership_status === 'suspended' ? <><ShieldCheck size={14} /> Rétablir</> : <><ShieldOff size={14} /> Suspendre</>}
          </button>
        </span>
      </div>)}
      {filtered.length === 0 && <div className="formation-empty"><Users size={28} /><strong>Aucun étudiant</strong><p>Ils apparaîtront après leur première inscription à une formation.</p></div>}
    </section>

    {selectedStudent && <div className="management-profile-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) setSelectedStudent(null) }}>
      <section className="management-profile-dialog" role="dialog" aria-modal="true" aria-label={`Fiche de ${selectedStudent.full_name}`}>
        <button className="management-profile-close" type="button" aria-label="Fermer" onClick={() => setSelectedStudent(null)}><X size={19} /></button>
        <header className="management-profile-header">
          <StudentAvatar student={selectedStudent} large />
          <div><span className="page-kicker">Fiche étudiant</span><h2>{selectedStudent.full_name}</h2><p>{selectedStudent.email}</p></div>
          <span className={`student-access-status ${selectedAccessSuspended ? 'suspended' : 'active'}`}><UserRoundCheck size={14} />{selectedAccessSuspended ? 'Accès suspendu' : 'Accès actif'}</span>
        </header>

        <div className="management-profile-facts">
          <article><GraduationCap size={17} /><div><small>Matricule</small><strong>{selectedStudent.student_code}</strong></div></article>
          <article><CalendarDays size={17} /><div><small>Inscription à l’école</small><strong>{formatDateTime(selectedStudent.registered_at)}</strong></div></article>
          <article><Clock3 size={17} /><div><small>Création du compte</small><strong>{formatDateTime(selectedStudent.user_created_at)}</strong></div></article>
          <article><BookOpen size={17} /><div><small>Premier achat</small><strong>{formatDateTime(selectedStudent.first_purchase_at)}</strong></div></article>
          <article><Clock3 size={17} /><div><small>Dernier achat</small><strong>{formatDateTime(selectedStudent.last_purchase_at)}</strong></div></article>
          <article><Users size={17} /><div><small>Téléphone</small><strong>{selectedStudent.phone || 'Non renseigné'}</strong></div></article>
        </div>

        <section className="management-profile-section">
          <div className="management-profile-section-heading"><div><span className="page-kicker">Parcours</span><h3>Formations souscrites</h3></div><span>{selectedStudent.enrollments.length} inscription(s)</span></div>
          {selectedStudent.enrollments.length ? <div className="management-enrollment-list">{selectedStudent.enrollments.map((enrollment, index) => <article key={`${enrollment.formation_title}-${enrollment.session_label}-${index}`}>
            {enrollment.formation_image_url ? <img className="management-enrollment-thumbnail" src={enrollment.formation_image_url} alt="" /> : <span className="management-enrollment-thumbnail management-enrollment-thumbnail--empty"><BookOpen size={18} /></span>}<div><strong>{enrollment.formation_title}</strong><small>{enrollment.session_label} · {new Intl.DateTimeFormat(activeSchoolLocale(), { dateStyle: 'medium' }).format(new Date(`${enrollment.start_date}T00:00:00`))} – {new Intl.DateTimeFormat(activeSchoolLocale(), { dateStyle: 'medium' }).format(new Date(`${enrollment.end_date}T00:00:00`))}</small><small>Inscription : {formatDateTime(enrollment.enrolled_at)}</small></div><span className={`enrollment-status enrollment-status--${enrollment.status}`}>{enrollmentStatus(enrollment.status)}</span>
          </article>)}</div> : <p className="management-profile-empty">Aucune inscription de formation n’est enregistrée.</p>}
        </section>

        <footer className="management-profile-footer">
          {!selectedStudent.member_id && <p>Cette fiche n’a pas de lien d’accès membre à modifier.</p>}
          <button className={selectedAccessSuspended ? 'primary-button' : 'text-danger-button'} type="button" disabled={!selectedStudent.member_id || workingId !== null} onClick={() => void toggleAccess(selectedStudent)}>
            {selectedAccessSuspended ? <><ShieldCheck size={16} /> Rétablir l’accès à l’école</> : <><ShieldOff size={16} /> Suspendre l’accès à l’école</>}
          </button>
        </footer>
      </section>
    </div>}
  </main>
}
