import { CalendarDays, CheckCircle2, Clock3, MapPin, ShoppingBag, Users } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getPublicSchoolFormation, type PublicFormationDetail, type PublicSession } from '../lib/api'
import { setSchoolCart } from '../public/schoolCart'
import { formatSchoolDate, formatSchoolMoney } from '../public/publicHelpers'
import { usePublicSchool } from '../public/SchoolPublicLayout'
import { SchoolFavoriteButton } from '../public/SchoolFavoriteButton'

export function SchoolFormationDetailPage() {
  const { schoolSlug = '', formationSlug = '' } = useParams()
  const { school, openCart } = usePublicSchool()
  const [formation,setFormation]=useState<PublicFormationDetail|null>(null)
  const [sessionId,setSessionId]=useState<number|null>(null)
  const [toast,setToast]=useState('')
  const [error,setError]=useState('')
  const [retry,setRetry]=useState(0)
  useEffect(()=>{
    let active=true
    setFormation(null);setError('')
    getPublicSchoolFormation(schoolSlug,formationSlug).then((data)=>{if(!active)return;setFormation(data);const available=data.sessions.filter((s)=>s.can_purchase);setSessionId(available.length===1?available[0].id:null)}).catch(()=>{if(active)setError('Impossible de charger cette formation.')})
    return ()=>{active=false}
  },[schoolSlug,formationSlug,retry])
  const selected=useMemo(()=>formation?.sessions.find((s)=>s.id===sessionId)??null,[formation,sessionId])
  function add(){
    if(!formation) return
    const target=formation.format_type==='ligne'?formation.next_session:(selected || (formation.sessions.filter((s)=>s.can_purchase).length===1?formation.sessions.find((s)=>s.can_purchase)??null:null))
    if(!target || !target.can_purchase){setToast(formation.format_type==='ligne'?'Cette formation n’est pas disponible à l’achat.':'Aucune nouvelle session disponible pour cette formation.');setTimeout(()=>setToast(''),3200);return}
    setSchoolCart(schoolSlug,{organization_id:school.organization_id,formation_id:formation.id,formation_slug:formation.slug,formation_title:formation.title,session_id:target.id,session_label:target.label,format_type:formation.format_type,price_cents:target.current_price_cents,currency:target.currency,cover_image_url:formation.cover_image_url})
    openCart()
  }
  if(!formation)return <main className="school-section"><div className="school-empty">{error?<>{error} <button type="button" onClick={()=>setRetry((value)=>value+1)}>Réessayer</button></>:'Chargement…'}</div></main>
  const available=formation.sessions.filter((s)=>s.can_purchase)
  return <main className="school-detail-page">
    {toast&&<div className="school-toast">{toast}</div>}
    <section className="school-detail-hero"><div className="school-detail-cover">{formation.cover_image_url?<img src={formation.cover_image_url} alt={formation.title}/>:<div/>}</div><div className="school-detail-intro"><span className="school-kicker">{formation.category} · {formation.level}</span><h1>{formation.title}</h1><SchoolFavoriteButton slug={formation.slug} title={formation.title}/><p>{formation.short_description||formation.description}</p><div className="school-detail-meta"><span><Clock3 size={15}/>{formation.training_hours?formation.training_hours+' h':formation.format_type==='ligne'?'À votre rythme':'Durée selon session'}</span><span>{formation.format_type}</span>{formation.teacher_names.length>0&&<span><Users size={15}/>{formation.teacher_names.join(', ')}</span>}</div><div className="school-detail-price">{formation.promotion_discount_cents>0&&<del>{formatSchoolMoney(formation.price_cents,formation.currency)}</del>}<strong>{formatSchoolMoney(formation.current_price_cents,formation.currency)}</strong>{formation.allow_installments&&<small>Paiement jusqu'en {formation.installment_count} tranches.</small>}</div></div></section>

    <section className="school-detail-layout">
      <article className="school-detail-content">
        <div><h2>Présentation</h2><p>{formation.description}</p></div>
        {formation.objectives&&<div><h2>Objectifs</h2><p className="school-preline">{formation.objectives}</p></div>}
        {formation.public_program&&<div><h2>Programme</h2><p className="school-preline">{formation.public_program}</p></div>}
        {formation.modules.length>0&&<div><h2>Modules</h2><div className="school-program-modules">{formation.modules.map((module,index)=><article key={module.title+'-'+index}><strong>Module {index+1} : {module.title}</strong>{module.chapters.length>0&&<ul>{module.chapters.map((chapter,chapterIndex)=><li key={chapter+'-'+chapterIndex}>{chapter}</li>)}</ul>}</article>)}</div></div>}
        {formation.prerequisites&&<div><h2>Prérequis</h2><p className="school-preline">{formation.prerequisites}</p></div>}
      </article>
      <aside className="school-session-panel">{formation.format_type==='ligne'?<><h2>Formation en ligne</h2><p>Accédez au parcours dès la confirmation de votre achat et progressez à votre rythme.</p><button className={'school-buy-button '+(!formation.can_purchase?'is-locked':'')} type="button" onClick={add}><ShoppingBag size={16}/>{formation.can_purchase?'Ajouter au panier':'Formation indisponible'}</button></>:<><h2>Choisissez votre session</h2><div className="school-session-list">{formation.sessions.length?formation.sessions.map((session)=><SessionChoice key={session.id} session={session} selected={session.id===sessionId} onSelect={()=>session.can_purchase&&setSessionId(session.id)}/>):<div className="school-no-session">Aucune session programmée.</div>}</div><button className={'school-buy-button '+(!formation.can_purchase?'is-locked':'')} type="button" onClick={add}><ShoppingBag size={16}/>{formation.can_purchase?'Ajouter au panier':'Pas de nouvelle session disponible'}</button>{available.length===0&&<small>Achat verrouillé jusqu'à l'ouverture d'une nouvelle session.</small>}</>}</aside>
    </section>
  </main>
}

function SessionChoice({session,selected,onSelect}:{session:PublicSession;selected:boolean;onSelect:()=>void}){
 return <button type="button" className={'school-session-choice '+(selected?'is-selected ':'')+(!session.can_purchase?'is-disabled':'')} onClick={onSelect}><span className="school-session-radio"/><div><strong>{session.label}</strong><span><CalendarDays size={13}/>{formatSchoolDate(session.start_date)} → {formatSchoolDate(session.end_date)}</span>{session.campus_label&&<span><MapPin size={13}/>{session.campus_label}</span>}{session.seats_remaining!==null&&<span><Users size={13}/>{session.seats_remaining} place(s) restante(s)</span>}{!session.can_purchase&&<small>{session.unavailable_reason}</small>}</div><div className="school-session-price">{session.promotion_discount_cents>0&&<del>{formatSchoolMoney(session.price_cents,session.currency)}</del>}<strong>{formatSchoolMoney(session.current_price_cents,session.currency)}</strong>{session.can_purchase&&<CheckCircle2 size={15}/>}</div></button>
}
