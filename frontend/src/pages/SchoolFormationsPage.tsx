import { useEffect, useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { useOutletContext } from 'react-router-dom'
import { ApiError, getPublicCatalog, type PublicFormation } from '../lib/api'
import type { PublicOutletContext } from '../public/SchoolPublicLayout'
import { PublicFormationCard } from '../public/PublicFormationCard'

export function SchoolFormationsPage(){
 const {school}=useOutletContext<PublicOutletContext>()
 const [items,setItems]=useState<PublicFormation[]>([])
 const [query,setQuery]=useState('')
 const [error,setError]=useState('')
 useEffect(()=>{getPublicCatalog(school.slug).then((x)=>setItems(x.formations)).catch((err)=>setError(err instanceof ApiError?err.message:'Catalogue indisponible.'))},[school.slug])
 const filtered=useMemo(()=>{const q=query.trim().toLowerCase();return q?items.filter((x)=>(x.title+' '+x.category+' '+x.description).toLowerCase().includes(q)):items},[items,query])
 return <main className="public-page"><header className="public-page-hero"><span className="public-kicker">Catalogue</span><h1>Toutes nos formations</h1><p>Choisissez votre programme puis la session qui correspond à votre disponibilité.</p></header>{error&&<div className="public-error">{error}</div>}<div className="public-search"><Search size={17}/><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Rechercher une formation..."/></div><div className="public-formation-grid">{filtered.map((formation)=><PublicFormationCard key={formation.id} schoolSlug={school.slug} formation={formation}/>)}</div></main>
}
