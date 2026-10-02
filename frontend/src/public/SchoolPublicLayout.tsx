import { useEffect, useState, type CSSProperties } from 'react'
import { Menu, ShoppingBag, X } from 'lucide-react'
import { Link, NavLink, Outlet, useOutletContext, useParams } from 'react-router-dom'
import { BrandLogo } from '../brand/BrandLogo'
import { getPublicSchoolIdentity, type PublicSchool } from '../lib/api'
import { getSchoolCart } from './schoolCart'

export type SchoolPublicOutlet = {
  school: PublicSchool
}

export function usePublicSchool() {
  return useOutletContext<SchoolPublicOutlet>()
}

export function SchoolPublicLayout() {
  const { schoolSlug = '' } = useParams()
  const [school, setSchool] = useState<PublicSchool | null>(null)
  const [error, setError] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [hasCart, setHasCart] = useState(Boolean(getSchoolCart(schoolSlug)))

  useEffect(() => {
    getPublicSchoolIdentity(schoolSlug)
      .then((value) => {
        setSchool(value)
        if (value.favicon_url) {
          let link = document.querySelector<HTMLLinkElement>("link[rel~='icon']")
          if (!link) {
            link = document.createElement('link')
            link.rel = 'icon'
            document.head.appendChild(link)
          }
          link.href = value.favicon_url
        }
        document.title = value.site_name || value.name
      })
      .catch(() => setError("Ce site d'école n'est pas disponible."))
  }, [schoolSlug])

  useEffect(() => {
    const handler = () => setHasCart(Boolean(getSchoolCart(schoolSlug)))
    window.addEventListener('school-cart-changed', handler)
    return () => window.removeEventListener('school-cart-changed', handler)
  }, [schoolSlug])

  if (error) return <main className="public-school-state"><h1>Site indisponible</h1><p>{error}</p></main>
  if (!school) return <main className="public-school-state">Chargement…</main>

  const style = {
    '--school-primary': school.primary_color,
    '--school-secondary': school.secondary_color,
    '--school-accent': school.accent_color,
    '--school-heading-font': school.font_heading,
    '--school-body-font': school.font_body,
  } as CSSProperties

  return (
    <div className="public-school-shell" style={style}>
      <header className="public-school-header">
        <Link className="public-school-brand" to={'/school/' + schoolSlug}>
          <BrandLogo logoUrl={school.logo_url || '/logo_academie_hd.png'} alt={school.site_name} />
          <strong>{school.site_name || school.name}</strong>
        </Link>
        <button className="public-school-mobile-menu" type="button" onClick={() => setMenuOpen((v) => !v)}>
          {menuOpen ? <X size={20}/> : <Menu size={20}/>}
        </button>
        <nav className={menuOpen ? 'is-open' : ''}>
          <NavLink end to={'/school/' + schoolSlug}>Accueil</NavLink>
          <NavLink to={'/school/' + schoolSlug + '/formations'}>Formations</NavLink>
          <NavLink to={'/school/' + schoolSlug + '/contact'}>Nous contacter</NavLink>
        </nav>
        <div className="public-school-actions">
          <Link className="public-school-login" to={'/login?school=' + encodeURIComponent(schoolSlug) + '&return=' + encodeURIComponent('/school/' + schoolSlug)}>Connexion</Link>
          <Link className="public-school-cart" to={'/school/' + schoolSlug + '/panier'}>
            <ShoppingBag size={18}/>{hasCart && <i/>}
          </Link>
        </div>
      </header>

      <Outlet context={{ school }} />

      <footer className="public-school-footer">
        <div className="public-school-footer-grid">
          <div>
            <div className="public-school-footer-brand">
              <BrandLogo logoUrl={school.logo_url || '/logo_academie_hd.png'} alt={school.site_name} />
              <strong>{school.site_name || school.name}</strong>
            </div>
            <p>{school.footer_text || school.tagline}</p>
            {school.contact_address && <span>{school.contact_address}</span>}
            {school.contact_phone && <span>{school.contact_phone}</span>}
            {school.contact_email && <span>{school.contact_email}</span>}
          </div>
          <div><strong>Navigation</strong><Link to={'/school/' + schoolSlug}>Accueil</Link><Link to={'/school/' + schoolSlug + '/formations'}>Formations</Link><Link to={'/school/' + schoolSlug + '/contact'}>Nous contacter</Link></div>
          <div><strong>Informations</strong><Link to={'/school/' + schoolSlug + '/mentions-legales'}>Mentions légales</Link><Link to={'/school/' + schoolSlug + '/cgv'}>Conditions générales de vente</Link><Link to={'/school/' + schoolSlug + '/confidentialite'}>Confidentialité</Link><Link to={'/school/' + schoolSlug + '/remboursement'}>Remboursement / annulation</Link></div>
        </div>
        <div className="public-school-footer-bottom">
          <span>© {new Date().getFullYear()} {school.site_name || school.name}</span>
          <span className="public-school-powered">Powered by <BrandLogo logoUrl="/logo_ico_hd.png" alt="Académie des Créatifs"/> <strong>Académie des Créatifs</strong></span>
        </div>
      </footer>
    </div>
  )
}
