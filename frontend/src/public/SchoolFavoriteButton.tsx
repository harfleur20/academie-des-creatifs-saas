import { Heart } from 'lucide-react'
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { ApiError } from '../lib/api'
import { DEMO_READ_ONLY_MESSAGE, readDemoState } from '../lib/demoState'
import { toast } from '../ui/toast'
import { usePublicSchool } from './SchoolPublicLayout'
import './SchoolFavoriteButton.css'
import { useSchoolSlug } from './useSchoolHost'

export function SchoolFavoriteButton({ slug, title }: { slug: string; title: string }) {
  const schoolSlug = useSchoolSlug()
  const { user } = useAuth()
  const { favorites, hasSchoolAccess, schoolAccessLoading, toggleFavorite } = usePublicSchool()
  const location = useLocation()
  const navigate = useNavigate()
  const [working, setWorking] = useState(false)
  const isFavorite = favorites.some((item) => item.slug === slug)

  async function toggle() {
    // A demo visitor stays in the demo: nothing is saved there, as its toast says.
    if (readDemoState()) {
      toast.info(DEMO_READ_ONLY_MESSAGE)
      return
    }
    if (!user) {
      navigate('/login?school=' + encodeURIComponent(schoolSlug) + '&return=' + encodeURIComponent(location.pathname))
      return
    }
    if (schoolAccessLoading) {
      toast.info('Vérification de votre accès à cette école…')
      return
    }
    if (!hasSchoolAccess) {
      toast.info('Votre compte n’est pas inscrit à cette école. Inscrivez-vous à une formation pour enregistrer vos favoris.')
      return
    }
    setWorking(true)
    try { await toggleFavorite(slug) }
    catch (caught) {
      // The demo has already said, in its own toast, that nothing is saved.
      if (!(caught instanceof ApiError && caught.code === 'demo_read_only')) toast.error('Impossible de modifier les favoris.')
    }
    finally { setWorking(false) }
  }

  return <div className="school-favorite-control">
    <button type="button" className={'school-favorite-button' + (isFavorite ? ' is-active' : '')} aria-label={(isFavorite ? 'Retirer ' : 'Ajouter ') + title + (isFavorite ? ' des favoris' : ' aux favoris')} aria-pressed={isFavorite} disabled={working} onClick={() => void toggle()}><Heart size={18} fill={isFavorite ? 'currentColor' : 'none'}/></button>
  </div>
}
