import { useEffect, useState } from 'react'
import { CalendarCheck2, LockKeyhole } from 'lucide-react'
import {
  ApiError,
  getTeacherAttendance,
  getTeacherWorkspace,
  markTeacherAttendance,
  ATTENDANCE_LABELS,
  type AttendanceCourseDay,
  type AttendanceStatus,
  type TeacherWorkspace,
} from '../lib/api'

const DELIVERY_LABELS: Record<string, string> = {
  held: 'séance tenue',
  partial: 'séance partielle',
  not_held: 'séance non tenue',
  interrupted: 'séance interrompue',
}

function dateTime(value: string) {
  return new Date(value).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}

function dayNote(day: AttendanceCourseDay) {
  if (day.report_submitted_at) {
    const delivery = DELIVERY_LABELS[day.delivery_status ?? ''] ?? 'rapport remis'
    if (day.can_edit && day.locks_at) return `Rapport remis · ${delivery} · corrections possibles jusqu'au ${dateTime(day.locks_at)}`
    return `Rapport remis · ${delivery}`
  }
  return null
}
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

  async function mark(day: AttendanceCourseDay, enrollmentId: number, value: AttendanceStatus) {
    try {
      const updated = await markTeacherAttendance(day.course_day_id, enrollmentId, value)
      setDays((current) => current.map((item) => item.course_day_id === updated.course_day_id ? updated : item))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Enregistrement impossible.')
    }
  }

  return <main className="app-page academic-page">
    <header className="app-page-header"><div><span className="page-kicker">Espace professeur</span><h1>Présences</h1><p>La saisie ouvre au début de la séance. Au rapport, les étudiants non marqués sont enregistrés absents ; vous pouvez corriger pendant 24 h. Un étudiant en retard compte comme présent.</p></div></header>
    {error && <div className="form-error">{error}</div>}
    <label className="academic-session-select">Session<select value={sessionId ?? ''} onChange={(event)=>setSessionId(Number(event.target.value))}>{workspace?.sessions.map((item)=><option key={item.session_id} value={item.session_id}>{item.formation_title} · {item.session_label}</option>)}</select></label>
    <section className="attendance-day-list">
      {days.map((day)=><article className="app-card attendance-day-card" key={day.course_day_id}>
        <header><div><span className="section-label">{new Date(day.scheduled_at).toLocaleString('fr-FR')}</span><h2>{day.title}</h2><p>Prof. {day.teacher_name || '—'}</p>{dayNote(day) && <small>{dayNote(day)}</small>}{!day.can_edit && day.edit_blocked_reason && <small>{day.edit_blocked_reason}</small>}</div>{day.can_edit?<CalendarCheck2 size={20}/>:<LockKeyhole size={18}/>}</header>
        <div className="attendance-table">
          {day.rows.map((row)=><div className="attendance-row" key={row.enrollment_id}><span className="attendance-row__who"><strong>{row.student_name}</strong>{row.live_minutes != null && <small>{row.live_minutes} min en salle{day.live_roll_calls ? ` · appel ${row.live_roll_calls_answered ?? 0}/${day.live_roll_calls}` : ''}</small>}</span><select value={row.status ?? ''} disabled={!day.can_edit} onChange={(event)=>void mark(day,row.enrollment_id,event.target.value as AttendanceStatus)}><option value="" disabled>Non marqué</option>{(Object.keys(ATTENDANCE_LABELS) as AttendanceStatus[]).map((value)=><option key={value} value={value}>{ATTENDANCE_LABELS[value]}</option>)}</select></div>)}
        </div>
      </article>)}
      {days.length===0&&<div className="app-card formation-empty"><CalendarCheck2 size={26}/><strong>Aucun créneau</strong><p>Le planning de la session est encore vide.</p></div>}
    </section>
  </main>
}
