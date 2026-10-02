import { useEffect, useState } from 'react'
import { Award, BookOpen, CheckCircle2, ClipboardCheck } from 'lucide-react'
import { ApiError, listStudentProgress, type StudentProgress } from '../lib/api'

function meter(value:number|null){return value===null?'—':value.toFixed(0)+'%'}

export function StudentProgressPage() {
  const [items,setItems]=useState<StudentProgress[]>([])
  const [error,setError]=useState('')
  useEffect(()=>{listStudentProgress().then(setItems).catch((err)=>setError(err instanceof ApiError?err.message:'Chargement impossible.'))},[])
  return <main className="app-page academic-page">
    <header className="app-page-header"><div><span className="page-kicker">Espace étudiant</span><h1>Ma progression</h1><p>Progression calculée à partir des cours, devoirs, évaluations et présences.</p></div></header>
    {error&&<div className="form-error">{error}</div>}
    <section className="progress-card-list">{items.map((item)=><article className="app-card progress-card" key={item.enrollment_id}>
      <header><div><span className="section-label">{item.session_label}</span><h2>{item.formation_title}</h2></div><div className="badge-orb"><Award size={20}/><span>{item.badge.label}</span><strong>{item.badge.score_pct}%</strong></div></header>
      <div className="progress-main-meter"><div><strong>Progression globale</strong><span>{item.badge.score_pct}%</span></div><div><i style={{width:item.badge.score_pct+'%'}}/></div></div>
      <div className="progress-detail-grid">
        <div><BookOpen size={16}/><strong>{item.completed_lessons}/{item.total_lessons}</strong><span>Leçons · {meter(item.lesson_progress_pct)}</span></div>
        <div><ClipboardCheck size={16}/><strong>{item.submitted_assignments}/{item.total_assignments}</strong><span>Devoirs · {meter(item.badge.assignment_progress_pct)}</span></div>
        <div><CheckCircle2 size={16}/><strong>{item.attempted_quizzes}/{item.total_quizzes}</strong><span>Quiz · {meter(item.badge.quiz_progress_pct)}</span></div>
        <div><Award size={16}/><strong>{item.attendance_present}/{item.attendance_total}</strong><span>Présences · {meter(item.badge.attendance_pct)}</span></div>
      </div>
      {item.badge.next_level&&<p className="progress-next">Prochain niveau : <strong>{item.badge.next_level.replace('_',' ')}</strong></p>}
    </article>)}{items.length===0&&<div className="app-card formation-empty"><Award size={28}/><strong>Aucune progression</strong><p>Commencez une formation pour alimenter votre parcours.</p></div>}</section>
  </main>
}
