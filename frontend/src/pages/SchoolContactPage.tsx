import { useEffect, useState } from 'react'
import { Mail, MapPin, MessageCircle, Phone } from 'lucide-react'
import { usePublicSchool } from '../public/SchoolPublicLayout'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export function SchoolContactPage(){
 const {school}=usePublicSchool()
 const [whatsappPhone,setWhatsappPhone]=useState<string|null>(null)

 useEffect(()=>{
  let active=true
  fetch(`${API_BASE}/public/schools/${encodeURIComponent(school.slug)}/contact-channels`)
   .then((response)=>response.ok?response.json():Promise.reject())
   .then((channels:{whatsapp_phone?:string|null})=>{if(active)setWhatsappPhone(channels.whatsapp_phone||null)})
   .catch(()=>{if(active)setWhatsappPhone(null)})
  return()=>{active=false}
 },[school.slug])

 const whatsappHref=whatsappPhone?`https://wa.me/${whatsappPhone.replace(/\D/g,'')}`:''

 return <main className="school-section school-contact-page"><header className="school-page-heading"><span className="school-kicker">Contact</span><h1>Nous contacter</h1><p>Une question sur une formation ou une session ? Contactez directement l'école.</p></header><div className="school-contact-grid">{school.contact_email&&<a href={'mailto:'+school.contact_email}><Mail/><strong>Email</strong><span>{school.contact_email}</span></a>}{school.contact_phone&&<a href={'tel:'+school.contact_phone.replace(/\s+/g,'')}><Phone/><strong>Téléphone</strong><span>{school.contact_phone}</span></a>}{whatsappPhone&&<a href={whatsappHref} target="_blank" rel="noreferrer"><MessageCircle/><strong>WhatsApp</strong><span>{whatsappPhone}</span></a>}{school.contact_address&&<div><MapPin/><strong>Adresse</strong><span>{school.contact_address}</span></div>}</div></main>
}
