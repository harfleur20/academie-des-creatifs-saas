import { useEffect, useState } from 'react'
import { CalendarCheck2, LockKeyhole } from 'lucide-react'
import {
  ApiError,
  getTeacherAttendance,
  getTeacherWorkspace,
  markTeacherAttendance,
  type AttendanceCourseDay,
  type TeacherWorkspace,
} from '../lib/api'
import { initialTeacherSessionId } from '../lib/teacherSession'

export function TeacherAttendancePage() {
  const [workspace, setWorkspace] = useState<TeacherWorkspace | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [days, setDays] = useState<AttendanceCourseDay[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    getTeacherWorkspace().then((data) => {
      setWorkspace(data)
      setSessionId(initialTeacherSessionId(data.sessions))
    }).catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [])

  async function refresh(id: number) {
    setDays(await getTeacherAttendance(id))
  }

  useEffect(() => {
    if (sessionId) void refresh(sessionId).catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [sessionId])

  async function mark(day: AttendanceCourseDay, enrollmentId: number, value: 'present' | 'absent' | 'excused') {
    try {
      const updated = await markTeacherAttendance(day.course_day_id, enrollmentId, value)
      setDays((current) => current.map((item) => item.course_day_id === updated.course_day_id ? updated : item))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Enregistrement impossible.')
    }
  }

  return <main className="app-page academic-page">
    <header className="app-page-header"><div><span className="page-kicker">Espace professeur</span><h1>Présences</h1><p>Suivez les présences séance par séance.</p></div></header>
    {error && <div className="form-error">{error}</div>}
    <label className="academic-session-select">Session<select value={sessionId ?? ''} onChange={(event)=>setSessionId(Number(event.target.value))}>{workspace?.sessions.map((item)=><option key={item.session_id} value={item.session_id}>{item.formation_title} · {item.session_label}</option>)}</select></label>
    <section className="attendance-day-list">
      {days.map((day)=><article className="app-card attendance-day-card" key={day.course_day_id}>
        <header><div><span className="section-label">{new Date(day.scheduled_at).toLocaleString('fr-FR')}</span><h2>{day.title}</h2><p>Prof. {day.teacher_name || '—'}</p>{day.report_submitted_at && <small>Présences clôturées · {day.delivery_status === 'held' ? 'séance tenue' : day.delivery_status === 'partial' ? 'partielle' : day.delivery_status === 'not_held' ? 'non tenue' : 'interrompue'}</small>}</div>{day.can_edit?<CalendarCheck2 size={20}/>:<LockKeyhole size={18}/>}</header>
        <div className="attendance-table">
          {day.rows.map((row)=><div className="attendance-row" key={row.enrollment_id}><strong>{row.student_name}</strong><select value={row.status ?? ''} disabled={!day.can_edit} onChange={(event)=>void mark(day,row.enrollment_id,event.target.value as 'present'|'absent'|'excused')}><option value="">Non marqué</option><option value="present">Présent</option><option value="absent">Absent</option><option value="excused">Excusé</option></select></div>)}
        </div>
      </article>)}
      {days.length===0&&<div className="app-card formation-empty"><CalendarCheck2 size={26}/><strong>Aucun créneau</strong><p>Le planning de la session est encore vide.</p></div>}
    </section>
  </main>
}
