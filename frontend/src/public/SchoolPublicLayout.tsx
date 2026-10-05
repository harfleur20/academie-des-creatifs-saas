import { useCallback, useEffect, useState, type CSSProperties } from 'react'
import { Heart, Menu, ShoppingBag, UserRound, X } from 'lucide-react'
import { Link, NavLink, Outlet, useLocation, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useTenant } from '../app/TenantContext'
import { BrandLogo } from '../brand/BrandLogo'
import { SchoolLogo } from '../brand/SchoolLogo'
import { schoolFontFamily } from '../brand/schoolTypography'
import { addSchoolFavorite, getPublicSchoolIdentity, listSchoolFavorites, removeSchoolFavorite, type PublicFormationCard, type PublicSchool } from '../lib/api'
import { clearSchoolCart, getSchoolCart, type SchoolCartItem } from './schoolCart'
import { SchoolCartDrawer } from './SchoolCartDrawer'
import { SchoolAnnouncementBanner } from './SchoolAnnouncementBanner'

export type SchoolPublicOutlet = {
  school: PublicSchool
  openCart: () => void
  favorites: PublicFormationCard[]
  favoritesLoading: boolean
  toggleFavorite: (formationSlug: string) => Promise<void>
}

export function usePublicSchool() {
  return useOutletContext<SchoolPublicOutlet>()
}

export function SchoolPublicLayout() {
  const { schoolSlug = '' } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { user, signOut } = useAuth()
  const { organizations, selectOrganization } = useTenant()
  const [school, setSchool] = useState<PublicSchool | null>(null)
  const [error, setError] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const [cartOpen, setCartOpen] = useState(false)
  const [cartItem, setCartItem] = useState<SchoolCartItem | null>(() => getSchoolCart(schoolSlug))
  const [favorites, setFavorites] = useState<PublicFormationCard[]>([])
  const [favoritesLoading, setFavoritesLoading] = useState(false)

  useEffect(() => {
    let active = true
    setFavorites([])
    setFavoritesLoading(Boolean(user))
    if (user) listSchoolFavorites(schoolSlug)
      .then((items) => { if (active) setFavorites(items) })
      .catch(() => {})
      .finally(() => { if (active) setFavoritesLoading(false) })
    return () => { active = false }
  }, [schoolSlug, user?.id])

  const toggleFavorite = useCallback(async (formationSlug: string) => {
    const current = favorites.some((item) => item.slug === formationSlug)
    const next = current
      ? await removeSchoolFavorite(schoolSlug, formationSlug)
      : await addSchoolFavorite(schoolSlug, formationSlug)
    setFavorites(next)
  }, [favorites, schoolSlug])

  useEffect(() => {
    let active = true
    const previousTitle = document.title
    const previousIcon = document.querySelector<HTMLLinkElement>("link[rel~='icon']")
    const previousIconHref = previousIcon?.href
    const previousMeta = [
      'meta[name="description"]',
      'meta[property="og:title"]',
      'meta[property="og:description"]',
    ].map((selector) => {
      const element = document.head.querySelector<HTMLMetaElement>(selector)
      return { selector, element, content: element?.content }
    })
    setSchool(null)
    setError('')
    getPublicSchoolIdentity(schoolSlug)
      .then((value) => {
        if (!active) return
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
        const description = value.seo_description || value.tagline || value.site_name
        const setMeta = (selector: string, attribute: 'name' | 'property', key: string, content: string) => {
          let meta = document.head.querySelector<HTMLMetaElement>(selector)
          if (!meta) {
            meta = document.createElement('meta')
            meta.setAttribute(attribute, key)
            document.head.appendChild(meta)
          }
          meta.content = content
        }
        setMeta('meta[name="description"]', 'name', 'description', description)
        setMeta('meta[property="og:title"]', 'property', 'og:title', value.site_name || value.name)
        setMeta('meta[property="og:description"]', 'property', 'og:description', description)
      })
      .catch(() => { if (active) setError("Ce site d'école n'est pas disponible.") })
    return () => {
      active = false
      document.title = previousTitle
      if (previousIcon) previousIcon.href = previousIconHref || ''
      else document.querySelector<HTMLLinkElement>("link[rel~='icon']")?.remove()
      previousMeta.forEach(({ selector, element, content }) => {
        if (element) element.content = content || ''
        else document.head.querySelector<HTMLMetaElement>(selector)?.remove()
      })
    }
  }, [schoolSlug])

  useEffect(() => {
    if (!school) return
    let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
    const previous = canonical?.href
    const existing = Boolean(canonical)
    if (!canonical) {
      canonical = document.createElement('link')
      canonical.rel = 'canonical'
      document.head.appendChild(canonical)
    }
    canonical.href = window.location.origin + location.pathname
    return () => {
      if (existing) canonical.href = previous || ''
      else canonical.remove()
    }
  }, [school, location.pathname])

  useEffect(() => {
    const handler = () => setCartItem(getSchoolCart(schoolSlug))
    handler()
    window.addEventListener('school-cart-changed', handler)
    return () => window.removeEventListener('school-cart-changed', handler)
  }, [schoolSlug])

  useEffect(() => {
    setCartOpen(location.pathname.endsWith('/panier'))
    setMenuOpen(false)
    setAccountOpen(false)
  }, [location.pathname])

  const closeCart = useCallback(() => {
    setCartOpen(false)
    if (location.pathname.endsWith('/panier')) navigate('/school/' + schoolSlug, { replace: true })
  }, [location.pathname, navigate, schoolSlug])

  if (error) return <main className="public-school-state"><h1>Site indisponible</h1><p>{error}</p></main>
  if (!school) return <main className="public-school-state">Chargement…</main>

  const style = {
    '--school-primary': school.primary_color,
    '--school-secondary': school.secondary_color,
    '--school-accent': school.accent_color,
    '--school-heading-font': schoolFontFamily(school.font_heading),
    '--school-body-font': schoolFontFamily(school.font_body),
    '--school-font-scale': String(school.font_size_scale / 100),
  } as CSSProperties
  const validCartItem = cartItem?.organization_id === school.organization_id ? cartItem : null
  const schoolMembership = organizations.find((organization) => organization.id === school.organization_id)
  const hasFooterContact = Boolean(school.contact_address || school.contact_phone || school.contact_email)

  return (
    <div className="public-school-shell" style={style}>
      {school.announcement_enabled && <SchoolAnnouncementBanner text={school.announcement_text} backgroundColor={school.announcement_background_color} textColor={school.announcement_text_color} />}
      <header className="public-school-header">
        <Link className="public-school-brand" to={'/school/' + schoolSlug}>
          <SchoolLogo logoUrl={school.logo_url} alt={school.site_name} />
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
          {user && <Link className="public-school-favorites-link" to={'/school/' + schoolSlug + '/favoris'} aria-label="Mes formations favorites" title="Mes favoris"><Heart size={18}/>{favorites.length > 0 && <span>{favorites.length}</span>}</Link>}
          {user ? (
            <div className="public-school-account">
              <button type="button" className="public-school-login" aria-expanded={accountOpen} onClick={() => setAccountOpen((value) => !value)}><UserRound size={16} /><span>{user.full_name}</span></button>
              {accountOpen && <div className="public-school-account-menu">
                {schoolMembership && <button type="button" onClick={() => { selectOrganization(schoolMembership.id); navigate('/school/' + schoolSlug + '/espace') }}>Mon espace</button>}
                <button type="button" onClick={() => { signOut(); setAccountOpen(false) }}>Déconnexion</button>
              </div>}
            </div>
          ) : <Link className="public-school-login" to={'/login?school=' + encodeURIComponent(schoolSlug) + '&return=' + encodeURIComponent('/school/' + schoolSlug + '/espace')}>Connexion</Link>}
          <button className="public-school-cart" type="button" aria-label="Ouvrir le panier" aria-expanded={cartOpen} onClick={() => setCartOpen(true)}>
            <ShoppingBag size={18}/>{validCartItem && <i/>}
          </button>
        </div>
      </header>

      <Outlet context={{ school, openCart: () => setCartOpen(true), favorites, favoritesLoading, toggleFavorite }} />
      <SchoolCartDrawer open={cartOpen} item={validCartItem} schoolSlug={schoolSlug} onClose={closeCart} onClear={() => clearSchoolCart(schoolSlug)} />

      <footer className="public-school-footer">
        <div className={'public-school-footer-grid' + (hasFooterContact ? ' has-contact' : '')}>
          <div>
            <div className="public-school-footer-brand">
              <SchoolLogo logoUrl={school.logo_url} alt={school.site_name} />
              <strong>{school.site_name || school.name}</strong>
            </div>
            <p>{school.footer_text || school.tagline}</p>
          </div>
          <div><strong>Navigation</strong><Link to={'/school/' + schoolSlug}>Accueil</Link><Link to={'/school/' + schoolSlug + '/formations'}>Formations</Link><Link to={'/school/' + schoolSlug + '/contact'}>Nous contacter</Link></div>
          <div><strong>Informations</strong><Link to={'/school/' + schoolSlug + '/mentions-legales'}>Mentions légales</Link><Link to={'/school/' + schoolSlug + '/cgv'}>Conditions générales de vente</Link><Link to={'/school/' + schoolSlug + '/confidentialite'}>Confidentialité</Link><Link to={'/school/' + schoolSlug + '/remboursement'}>Remboursement / annulation</Link></div>
          {hasFooterContact && (
            <div className="public-school-footer-contact">
              <strong>Contact</strong>
              {school.contact_address && <span>{school.contact_address}</span>}
              {school.contact_phone && <a href={'tel:' + school.contact_phone.replace(/\s+/g, '')}>{school.contact_phone}</a>}
              {school.contact_email && <a href={'mailto:' + school.contact_email}>{school.contact_email}</a>}
            </div>
          )}
        </div>
        <div className="public-school-footer-bottom">
          <span>© {new Date().getFullYear()} {school.site_name || school.name}</span>
          <span className="public-school-powered">Powered by <BrandLogo logoUrl="/logo_ico_hd.png" alt="Académie des Créatifs"/> <strong>Académie des Créatifs</strong></span>
        </div>
      </footer>
    </div>
  )
}
