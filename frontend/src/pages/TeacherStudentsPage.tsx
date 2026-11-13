import { useEffect, useMemo, useState } from 'react'
import { FileText, Users } from 'lucide-react'
import {
  ApiError,
  getFormation,
  getTeacherWorkspace,
  type FormationDetail,
  type TeacherWorkspace,
} from '../lib/api'
import { initialTeacherSessionId } from '../lib/teacherSession'
import { TranscriptDialog } from '../components/TranscriptView'

// The enrollments that have a transcript (backend app/services/transcripts.py).
const WITH_TRANSCRIPT = new Set(['active', 'completed', 'suspended_payment'])
const STATUS_LABELS: Record<string, string> = { active: 'Inscription active', completed: 'Formation terminée', suspended_payment: 'Accès suspendu (paiement)', pending: 'En attente' }

export function TeacherStudentsPage() {
  const [workspace,setWorkspace]=useState<TeacherWorkspace|null>(null)
  const [sessionId,setSessionId]=useState<number|null>(null)
  const [formation,setFormation]=useState<FormationDetail|null>(null)
  const [error,setError]=useState('')
  const [transcriptId,setTranscriptId]=useState<number|null>(null)
  useEffect(()=>{getTeacherWorkspace().then((data)=>{setWorkspace(data);setSessionId(initialTeacherSessionId(data.sessions))}).catch((err)=>setError(err instanceof ApiError?err.message:'Chargement impossible.'))},[])
  const selected=useMemo(()=>workspace?.sessions.find((item)=>item.session_id===sessionId)??null,[workspace,sessionId])
  useEffect(()=>{if(selected)getFormation(selected.formation_id).then(setFormation).catch((err)=>setError(err instanceof ApiError?err.message:'Chargement impossible.'))},[selected?.formation_id,selected?.session_id])
  const session=formation?.sessions.find((item)=>item.id===sessionId)
  return <main className="app-page academic-page">
    <header className="app-page-header"><div><span className="page-kicker">Espace professeur</span><h1>Étudiants</h1><p>Liste des étudiants de vos sessions affectées.</p></div></header>
    {error&&<div className="form-error">{error}</div>}
    <label className="academic-session-select">Session<select value={sessionId??''} onChange={(event)=>setSessionId(Number(event.target.value))}>{workspace?.sessions.map((item)=><option key={item.session_id} value={item.session_id}>{item.formation_title} · {item.session_label}</option>)}</select></label>
    <section className="student-roster-grid">{session?.enrollments.filter((item)=>item.status!=='cancelled').map((item)=><article className="app-card roster-card" key={item.id}>{item.student_avatar_url?<img className="roster-avatar roster-avatar--photo" src={item.student_avatar_url} alt=""/>:<div className="roster-avatar">{item.student_name.split(' ').slice(0,2).map((part)=>part[0]).join('').toUpperCase()}</div>}<div className="roster-card__body"><h3>{item.student_name}</h3><p>{item.student_email}</p><span className="section-label">{STATUS_LABELS[item.status]??item.status}</span>{WITH_TRANSCRIPT.has(item.status)&&<button type="button" className="secondary-button compact-action roster-transcript" onClick={()=>setTranscriptId(item.id)}><FileText size={14}/> Relevé de notes</button>}</div></article>)}{session&&session.enrollments.length===0&&<div className="app-card formation-empty"><Users size={26}/><strong>Aucun étudiant</strong><p>La cohorte ne contient encore aucun étudiant.</p></div>}</section>
  {transcriptId!==null&&<TranscriptDialog enrollmentId={transcriptId} onClose={()=>setTranscriptId(null)}/>}
  </main>
}
