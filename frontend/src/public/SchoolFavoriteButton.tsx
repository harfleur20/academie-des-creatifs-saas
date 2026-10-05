import { Heart } from 'lucide-react'
import { useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { usePublicSchool } from './SchoolPublicLayout'
import './SchoolFavoriteButton.css'

export function SchoolFavoriteButton({ slug, title }: { slug: string; title: string }) {
  const { schoolSlug = '' } = useParams()
  const { user } = useAuth()
  const { favorites, toggleFavorite } = usePublicSchool()
  const location = useLocation()
  const navigate = useNavigate()
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')
  const isFavorite = favorites.some((item) => item.slug === slug)

  async function toggle() {
    if (!user) {
      navigate('/login?school=' + encodeURIComponent(schoolSlug) + '&return=' + encodeURIComponent(location.pathname))
      return
    }
    setWorking(true)
    setError('')
    try { await toggleFavorite(slug) }
    catch { setError('Impossible de modifier les favoris.') }
    finally { setWorking(false) }
  }

  return <div className="school-favorite-control">
    <button type="button" className={'school-favorite-button' + (isFavorite ? ' is-active' : '')} aria-label={(isFavorite ? 'Retirer ' : 'Ajouter ') + title + (isFavorite ? ' des favoris' : ' aux favoris')} aria-pressed={isFavorite} disabled={working} onClick={() => void toggle()}><Heart size={18} fill={isFavorite ? 'currentColor' : 'none'}/></button>
    {error && <span role="alert">{error}</span>}
  </div>
}
