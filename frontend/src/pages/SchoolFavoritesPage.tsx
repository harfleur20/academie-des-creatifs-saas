import { Heart } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { FormationCard } from './SchoolHomePage'
import { usePublicSchool } from '../public/SchoolPublicLayout'
import { useAuth } from '../auth/AuthContext'

export function SchoolFavoritesPage() {
  const { schoolSlug = '' } = useParams()
  const { user, loading } = useAuth()
  const { favorites, favoritesLoading } = usePublicSchool()
  if (!loading && !user) return <Navigate to={'/login?school=' + encodeURIComponent(schoolSlug) + '&return=' + encodeURIComponent('/school/' + schoolSlug + '/favoris')} replace />
  return <main className="school-section school-catalog-page">
    <header className="school-page-heading"><span className="school-kicker">Votre sélection</span><h1>Mes favoris</h1><p>Retrouvez les formations que vous souhaitez suivre.</p></header>
    {loading || favoritesLoading ? <div className="school-empty">Chargement des favoris…</div> : favorites.length > 0 ? <div className="school-formation-grid">{favorites.map((formation) => <FormationCard key={formation.id} schoolSlug={schoolSlug} formation={formation}/>)}</div> : <div className="school-empty"><Heart size={30}/><p>Aucune formation favorite pour le moment.</p><Link className="school-primary-link" to={'/school/' + schoolSlug + '/formations'}>Découvrir les formations</Link></div>}
  </main>
}
