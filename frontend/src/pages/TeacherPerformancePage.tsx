import { useEffect, useState } from 'react'
import { Activity, CalendarDays, ClipboardCheck, Users } from 'lucide-react'
import { ApiError, getTeacherPerformance, type TeacherPerformance } from '../lib/api'

const pct=(value:number|null)=>value===null?'-':value.toFixed(1)+'%'

export function TeacherPerformancePage() {
  const [data,setData]=useState<TeacherPerformance|null>(null)
  const [error,setError]=useState('')
  useEffect(()=>{getTeacherPerformance().then(setData).catch((err)=>setError(err instanceof ApiError?err.message:'Chargement impossible.'))},[])
  return <main className="app-page academic-page">
    <header className="app-page-header"><div><span className="page-kicker">Pilotage enseignant</span><h1>Performance</h1><p>Vue consolidée de vos sessions, progression, présences et corrections.</p></div></header>
    {error&&<div className="form-error">{error}</div>}
    {data&&<>
      <section className="role-metric-grid teacher-performance-kpis"><article><CalendarDays size={19}/><strong>{data.total_sessions}</strong><span>Sessions</span></article><article><Users size={19}/><strong>{data.total_students}</strong><span>Étudiants</span></article><article><Activity size={19}/><strong>{pct(data.attendance_rate_pct)}</strong><span>Présence moyenne</span></article><article><ClipboardCheck size={19}/><strong>{data.pending_reviews_count}</strong><span>Corrections en attente</span></article></section>
      <section className="app-card performance-table-card"><div className="performance-table"><div className="performance-head"><span>Session</span><span>Étudiants</span><span>Progression</span><span>Présence</span><span>Quiz</span><span>Corrections</span></div>{data.sessions.map((row)=><div className="performance-row-group" key={row.session_id}><div className="performance-row"><span><strong>{row.formation_title}</strong><small>{row.session_label}</small></span><span>{row.enrolled_count}</span><span>{pct(row.progress_pct)}</span><span>{pct(row.attendance_rate_pct)}</span><span>{pct(row.quiz_average_score_pct)}</span><span>{row.pending_reviews_count}</span></div>{(row.badge_hint || (row.low_attendance_count ?? 0) > 0) && <div className="performance-hints">{(row.low_attendance_count ?? 0) > 0 && <p>{row.low_attendance_count} étudiant(s) suivent moins de 60 % des séances.</p>}{row.badge_hint && <p>{row.badge_hint}</p>}</div>}</div>)}</div></section>
    </>}
  </main>
}
