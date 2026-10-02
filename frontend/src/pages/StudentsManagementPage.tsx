import { useEffect, useMemo, useState } from 'react'
import { Search, UserRoundCheck, Users } from 'lucide-react'
import { ApiError, listManagedStudents, type ManagedStudent } from '../lib/api'
import { formatSchoolMoney } from '../public/publicHelpers'

export function StudentsManagementPage(){
 const [items,setItems]=useState<ManagedStudent[]>([]);const [query,setQuery]=useState('');const [error,setError]=useState('')
 useEffect(()=>{listManagedStudents().then(setItems).catch((err)=>setError(err instanceof ApiError?err.message:'Chargement impossible.'))},[])
 const filtered=useMemo(()=>{const q=query.trim().toLowerCase();return q?items.filter((x)=>[x.full_name,x.email,x.student_code].some((v)=>v.toLowerCase().includes(q))):items},[items,query])
 return <main className="app-page">
  <header className="app-page-header"><div><span className="page-kicker">Gestion des étudiants</span><h1>{items.length} étudiant(s)</h1><p>Les étudiants apparaissent ici automatiquement après un achat confirmé.</p></div></header>
  {error&&<div className="form-error">{error}</div>}
  <div className="admin-search"><Search size={16}/><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Nom, email ou matricule…"/></div>
  <section className="app-card managed-student-table">
   <div className="managed-student-row is-head"><span>Étudiant</span><span>Matricule</span><span>Parcours</span><span>Payé</span><span>Reste</span><span>Statut</span></div>
   {filtered.map((item)=><div className="managed-student-row" key={item.user_id}><div className="member-person">{item.avatar_url?<img className="mini-avatar" src={item.avatar_url} alt={item.full_name}/>:<span className="mini-avatar">{item.full_name.split(' ').slice(0,2).map((p)=>p[0]).join('').toUpperCase()}</span>}<span><strong>{item.full_name}</strong><small>{item.email}</small></span></div><strong>{item.student_code}</strong><span>{item.active_enrollments} actif(s) · {item.completed_enrollments} terminé(s)</span><span>{formatSchoolMoney(item.total_paid_cents,'XAF')}</span><span>{formatSchoolMoney(item.outstanding_cents,'XAF')}</span><span className={'student-access-status '+item.status}><UserRoundCheck size={13}/>{item.status==='active'?'Actif':item.status==='suspended_payment'?'Suspendu · impayé':item.status}</span></div>)}
   {filtered.length===0&&<div className="formation-empty"><Users size={28}/><strong>Aucun étudiant</strong><p>Ils apparaîtront après leur première inscription payée.</p></div>}
  </section>
 </main>
}
