import { useEffect, useState } from 'react'
import { BarChart3, CalendarCheck2 } from 'lucide-react'
import {
  ApiError,
  listStudentAttendance,
  listStudentGrades,
  type StudentAttendance,
  type StudentGrade,
} from '../lib/api'

export function StudentResultsPage() {
  const [grades,setGrades]=useState<StudentGrade[]>([])
  const [attendance,setAttendance]=useState<StudentAttendance[]>([])
  const [error,setError]=useState('')
  useEffect(()=>{Promise.all([listStudentGrades(),listStudentAttendance()]).then(([g,a])=>{setGrades(g);setAttendance(a)}).catch((err)=>setError(err instanceof ApiError?err.message:'Chargement impossible.'))},[])
  const average=grades.length?grades.reduce((sum,row)=>sum+(row.score/row.max_score)*20,0)/grades.length:null
  return <main className="app-page academic-page">
    <header className="app-page-header"><div><span className="page-kicker">Espace étudiant</span><h1>Résultats</h1><p>Vos notes et vos présences au même endroit.</p></div>{average!==null&&<span className="status-chip">Moyenne {average.toFixed(1)}/20</span>}</header>
    {error&&<div className="form-error">{error}</div>}
    <section className="student-results-grid">
      <article className="app-card"><div className="settings-section-heading"><div><span className="section-label">Évaluations</span><h2>Mes notes</h2></div><BarChart3 size={19}/></div><div className="result-list">{grades.map((grade)=><div className="result-row" key={grade.id}><div><strong>{grade.label}</strong><small>{grade.source_type} · {new Date(grade.created_at).toLocaleDateString('fr-FR')}</small></div><span>{grade.score}/{grade.max_score}</span></div>)}{grades.length===0&&<p className="empty-row">Aucune note pour le moment.</p>}</div></article>
      <article className="app-card"><div className="settings-section-heading"><div><span className="section-label">Assiduité</span><h2>Mes présences</h2></div><CalendarCheck2 size={19}/></div><div className="result-list">{attendance.map((row)=><div className="result-row" key={row.course_day_id}><div><strong>{row.title}</strong><small>{new Date(row.scheduled_at).toLocaleString('fr-FR')}</small></div><span className={'attendance-status '+(row.status||'pending')}>{row.status==='present'?'Présent':row.status==='absent'?'Absent':row.status==='excused'?'Excusé':'À confirmer'}</span></div>)}{attendance.length===0&&<p className="empty-row">Aucune séance enregistrée.</p>}</div></article>
    </section>
  </main>
}
