import { ArrowRight, CalendarDays, LockKeyhole } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { PublicFormation } from '../lib/api'

export function PublicFormationCard({schoolSlug,formation}:{schoolSlug:string;formation:PublicFormation}){
 const format=(value:number,currency:string)=>new Intl.NumberFormat('fr-FR',{style:'currency',currency,maximumFractionDigits:0}).format(value/100)
 return <article className="public-formation-card">
   <div className="public-formation-cover">{formation.cover_url?<img src={formation.cover_url} alt={formation.title}/>:<div>{formation.title.slice(0,1)}</div>}{formation.direct_discount_cents>0&&<span>Promo</span>}</div>
   <div className="public-formation-card-body"><span>{formation.category||formation.format_type}</span><h3>{formation.title}</h3><p>{formation.short_description||formation.description}</p><div className="public-formation-meta"><span><CalendarDays size={14}/>{formation.sessions.filter((x)=>x.is_available).length} session(s) disponible(s)</span><strong>{format(formation.display_price_cents,formation.currency)}</strong></div><Link to={'/schools/'+schoolSlug+'/formations/'+formation.slug}>{formation.can_buy?'Voir la formation':'Voir les détails'} {formation.can_buy?<ArrowRight size={14}/>:<LockKeyhole size={14}/>}</Link></div>
 </article>
}
