import { Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { listPublicSchoolFormations, type PublicFormationCard } from '../lib/api'
import { FormationCard } from './SchoolHomePage'

export function SchoolFormationsPage() {
  const { schoolSlug = '' } = useParams()
  const [items,setItems]=useState<PublicFormationCard[]>([])
  const [query,setQuery]=useState('')
  useEffect(()=>{listPublicSchoolFormations(schoolSlug).then(setItems)},[schoolSlug])
  const filtered=useMemo(()=>{const q=query.trim().toLowerCase();return q?items.filter((item)=>[item.title,item.category,item.level].some((value)=>value.toLowerCase().includes(q))):items},[items,query])
  return <main className="school-section school-catalog-page">
    <header className="school-page-heading"><span className="school-kicker">Catalogue</span><h1>Toutes nos formations</h1><p>Découvrez nos programmes et choisissez la session qui vous convient.</p></header>
    <div className="school-catalog-search"><Search size={17}/><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Rechercher une formation…"/></div>
    <div className="school-formation-grid">{filtered.map((item)=><FormationCard key={item.id} schoolSlug={schoolSlug} formation={item}/>)}</div>
    {filtered.length===0&&<div className="school-empty">Aucune formation ne correspond à votre recherche.</div>}
  </main>
}
