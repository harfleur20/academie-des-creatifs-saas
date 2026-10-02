import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Menu, ShoppingBag, X } from 'lucide-react'
import { Link, NavLink, Outlet, useParams } from 'react-router-dom'
import { DEFAULT_PLATFORM_LOGO_URL } from '../brand/branding'
import { BrandLogo } from '../brand/BrandLogo'
import { ApiError, getPublicSchool, type PublicSchool } from '../lib/api'
import { readPublicCart } from './publicCart'

export type PublicOutletContext={school:PublicSchool}

export function SchoolPublicLayout(){
 const {schoolSlug}=useParams()
 const [school,setSchool]=useState<PublicSchool|null>(null)
 const [error,setError]=useState('')
 const [menuOpen,setMenuOpen]=useState(false)
 const [cartCount,setCartCount]=useState(0)
 useEffect(()=>{if(!schoolSlug)return;getPublicSchool(schoolSlug).then(setSchool).catch((err)=>setError(err instanceof ApiError?err.message:'École introuvable.'))},[schoolSlug])
 useEffect(()=>{const refresh=()=>setCartCount(readPublicCart().filter((x)=>x.schoolSlug===schoolSlug).length);refresh();window.addEventListener('school-cart-change',refresh);return()=>window.removeEventListener('school-cart-change',refresh)},[schoolSlug])
 const style=useMemo(()=>school?{'--public-primary':school.primary_color,'--public-secondary':school.secondary_color,'--public-accent':school.accent_color} as CSSProperties:undefined,[school])
 if(error)return <main className="public-state">{error}</main>
 if(!school)return <main className="public-state">Chargement de l’école…</main>
 return <div className="school-public" style={style}>
   <header className="school-public-header">
    <Link className="school-public-brand" to={'/schools/'+school.slug}><BrandLogo logoUrl={school.logo_url||'/logo_academie_hd.png'} alt={school.name}/><strong>{school.name}</strong></Link>
    <button className="school-public-menu" type="button" onClick={()=>setMenuOpen((v)=>!v)}>{menuOpen?<X size={20}/>:<Menu size={20}/>}</button>
    <nav className={menuOpen?'is-open':''}><NavLink to={'/schools/'+school.slug} end>Accueil</NavLink><NavLink to={'/schools/'+school.slug+'/formations'}>Formations</NavLink><NavLink to={'/schools/'+school.slug+'/contact'}>Nous contacter</NavLink><Link to={'/schools/'+school.slug+'/checkout'} className="public-cart-link"><ShoppingBag size={17}/>Panier{cartCount>0&&<span>{cartCount}</span>}</Link><Link className="public-login-link" to={'/login?next='+encodeURIComponent('/schools/'+school.slug)}>Connexion</Link></nav>
   </header>
   <Outlet context={{school} satisfies PublicOutletContext}/>
   <footer className="school-public-footer">
    <div><BrandLogo logoUrl={school.logo_url||'/logo_academie_hd.png'} alt={school.name}/><strong>{school.name}</strong><p>{school.site.footer_text||school.site.about_text||'Votre école en ligne.'}</p></div>
    <div><strong>Navigation</strong><Link to={'/schools/'+school.slug}>Accueil</Link><Link to={'/schools/'+school.slug+'/formations'}>Formations</Link><Link to={'/schools/'+school.slug+'/contact'}>Nous contacter</Link></div>
    <div><strong>Informations</strong><Link to={'/schools/'+school.slug+'/legal/mentions'}>Mentions légales</Link><Link to={'/schools/'+school.slug+'/legal/cgv'}>Conditions générales de vente</Link><Link to={'/schools/'+school.slug+'/legal/confidentialite'}>Politique de confidentialité</Link><Link to={'/schools/'+school.slug+'/legal/remboursement'}>Remboursement / annulation</Link></div>
    <div><strong>Contact</strong>{school.site.contact_email&&<a href={'mailto:'+school.site.contact_email}>{school.site.contact_email}</a>}{school.site.contact_phone&&<a href={'tel:'+school.site.contact_phone}>{school.site.contact_phone}</a>}<span>{school.site.contact_address}</span></div>
    <div className="school-public-footer-bottom"><span>© {new Date().getFullYear()} {school.name}</span><span className="school-public-powered">Powered by <BrandLogo logoUrl={DEFAULT_PLATFORM_LOGO_URL} alt="Académie des Créatifs"/> <strong>Académie des Créatifs</strong></span></div>
   </footer>
 </div>
}
