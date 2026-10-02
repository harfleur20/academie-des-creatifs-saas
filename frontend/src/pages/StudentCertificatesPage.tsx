import { useEffect, useState } from 'react'
import { Award, CheckCircle2, ShieldCheck } from 'lucide-react'
import {
  ApiError,
  getCertificateEligibility,
  issueStudentCertificate,
  listStudentProgress,
  type CertificateEligibility,
  type StudentProgress,
} from '../lib/api'

export function StudentCertificatesPage() {
  const [progress,setProgress]=useState<StudentProgress[]>([])
  const [eligibility,setEligibility]=useState<Record<number,CertificateEligibility>>({})
  const [error,setError]=useState('')
  useEffect(()=>{listStudentProgress().then(async(rows)=>{setProgress(rows);const pairs=await Promise.all(rows.map(async(row)=>[row.enrollment_id,await getCertificateEligibility(row.enrollment_id)] as const));setEligibility(Object.fromEntries(pairs))}).catch((err)=>setError(err instanceof ApiError?err.message:'Chargement impossible.'))},[])
  async function issue(enrollmentId:number){try{const certificate=await issueStudentCertificate(enrollmentId);setEligibility((current)=>({...current,[enrollmentId]:{enrollment_id:enrollmentId,eligible:true,reason:null,certificate}}))}catch(err){setError(err instanceof ApiError?err.message:'Émission impossible.')}}
  return <main className="app-page academic-page">
    <header className="app-page-header"><div><span className="page-kicker">Validation</span><h1>Certificats & badges</h1><p>Vos badges évoluent avec votre activité. Le certificat est émis uniquement après validation du parcours.</p></div></header>
    {error&&<div className="form-error">{error}</div>}
    <section className="certificate-list">{progress.map((item)=>{const state=eligibility[item.enrollment_id];return <article className="app-card certificate-card" key={item.enrollment_id}><div className="certificate-badge"><Award size={24}/><strong>{item.badge.label}</strong><span>{item.badge.score_pct}%</span></div><div className="certificate-body"><span className="section-label">{item.session_label}</span><h2>{item.formation_title}</h2>{state?.certificate?<div className="certificate-issued"><CheckCircle2 size={17}/><div><strong>{state.certificate.certificate_number}</strong><small>Émis le {new Date(state.certificate.issued_at).toLocaleDateString('fr-FR')}</small></div></div>:state?.eligible?<button className="primary-button" type="button" onClick={()=>void issue(item.enrollment_id)}><ShieldCheck size={15}/> Générer mon certificat</button>:<p>{state?.reason||'Vérification du parcours…'}</p>}</div></article>})}</section>
  </main>
}
