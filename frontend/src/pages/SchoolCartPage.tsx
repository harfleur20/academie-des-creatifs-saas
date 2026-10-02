import { ArrowRight, ShoppingBag, Trash2 } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { clearSchoolCart, getSchoolCart } from '../public/schoolCart'
import { formatSchoolMoney } from '../public/publicHelpers'
import { useState } from 'react'
import { usePublicSchool } from '../public/SchoolPublicLayout'

export function SchoolCartPage(){
 const {schoolSlug=''}=useParams();const {school}=usePublicSchool();const [item,setItem]=useState(()=>{const candidate=getSchoolCart(schoolSlug);return candidate?.organization_id===school.organization_id?candidate:null})
 if(!item)return <main className="school-section school-cart-page"><div className="school-empty"><ShoppingBag size={30}/><h2>Votre panier est vide</h2><Link className="school-primary-link" to={'/school/'+schoolSlug+'/formations'}>Voir les formations</Link></div></main>
 return <main className="school-section school-cart-page"><header className="school-page-heading"><span className="school-kicker">Panier</span><h1>Votre inscription</h1></header><div className="school-cart-layout"><article className="school-cart-item">{item.cover_image_url?<img src={item.cover_image_url} alt={item.formation_title}/>:<div className="school-cart-placeholder"/>}<div><h2>{item.formation_title}</h2><p>Session : {item.session_label}</p><strong>{formatSchoolMoney(item.price_cents,item.currency)}</strong></div><button type="button" onClick={()=>{clearSchoolCart(schoolSlug);setItem(null)}}><Trash2 size={16}/></button></article><aside className="school-cart-summary"><span>Total</span><strong>{formatSchoolMoney(item.price_cents,item.currency)}</strong><Link to={'/school/'+schoolSlug+'/checkout'}>Passer au paiement <ArrowRight size={15}/></Link></aside></div></main>
}
