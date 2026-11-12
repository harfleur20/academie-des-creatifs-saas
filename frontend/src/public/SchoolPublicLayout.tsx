import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react'
import { ChevronDown, Heart, LayoutDashboard, LifeBuoy, LogOut, Menu, Settings, ShoppingBag, UserRound, X } from 'lucide-react'
import { Link, NavLink, Outlet, useLocation, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useTenant } from '../app/TenantContext'
import { SchoolMessageBell } from '../app/SchoolMessageBell'
import { SchoolNotificationBell } from '../app/SchoolNotificationBell'
import { BrandLogo } from '../brand/BrandLogo'
import { SchoolLogo } from '../brand/SchoolLogo'
import { schoolFontFamily } from '../brand/schoolTypography'
import { addSchoolFavorite, getPublicSchoolIdentity, listSchoolFavorites, removeSchoolFavorite, type PublicFormationCard, type PublicSchool, type WorkspaceSpace } from '../lib/api'
import { clearSchoolCart, getSchoolCart, type SchoolCartItem } from './schoolCart'
import { SchoolCartDrawer } from './SchoolCartDrawer'
import { SchoolAnnouncementBanner } from './SchoolAnnouncementBanner'
import './PublicSchoolAccountMenu.css'

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

function compactAccountName(name?: string | null) {
  const value = (name || '').trim()
  if (value.length <= 14) return value
  return value.slice(0, 14).trimEnd() + '.'
}

export function SchoolPublicLayout() {
  const { schoolSlug = '' } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { user, signOut } = useAuth()
  const { organizations, activeOrganization, accessProfile, selectOrganization } = useTenant()
  const [school, setSchool] = useState<PublicSchool | null>(null)
  const [error, setError] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const [cartOpen, setCartOpen] = useState(false)
  const [cartItem, setCartItem] = useState<SchoolCartItem | null>(() => getSchoolCart(schoolSlug))
  const [favorites, setFavorites] = useState<PublicFormationCard[]>([])
  const [favoritesLoading, setFavoritesLoading] = useState(false)
  const accountRef = useRef<HTMLDivElement>(null)

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
    if (!school?.slug || !schoolSlug || school.slug.toLowerCase() === schoolSlug.toLowerCase()) return
    const currentPrefix = '/school/' + schoolSlug
    const canonicalPrefix = '/school/' + school.slug
    const nextPath = location.pathname.startsWith(currentPrefix)
      ? canonicalPrefix + location.pathname.slice(currentPrefix.length)
      : canonicalPrefix
    navigate(nextPath + location.search + location.hash, { replace: true })
  }, [school?.slug, schoolSlug, location.pathname, location.search, location.hash, navigate])

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

  useEffect(() => {
    if (!user || !school) return
    const membership = organizations.find((organization) => organization.id === school.organization_id)
    if (membership && activeOrganization?.id !== school.organization_id) {
      selectOrganization(school.organization_id)
    }
  }, [user?.id, school?.organization_id, organizations, activeOrganization?.id, selectOrganization])

  useEffect(() => {
    function closeAccountMenu(event: MouseEvent) {
      if (accountRef.current && !accountRef.current.contains(event.target as Node)) {
        setAccountOpen(false)
      }
    }
    document.addEventListener('mousedown', closeAccountMenu)
    return () => document.removeEventListener('mousedown', closeAccountMenu)
  }, [])

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
  const schoolAccessProfile = accessProfile?.organization_id === school.organization_id ? accessProfile : null
  const accountSpace: WorkspaceSpace | null = schoolAccessProfile?.spaces.includes('manage')
    ? 'manage'
    : schoolAccessProfile?.default_space || schoolAccessProfile?.spaces[0] || null
  const canManageSchool = schoolAccessProfile?.spaces.includes('manage') ?? false
  const hasFooterContact = Boolean(school.contact_address || school.contact_phone || school.contact_email)
  const accountName = compactAccountName(user?.full_name)

  function openAccountPage(path: string) {
    if (schoolMembership) selectOrganization(schoolMembership.id)
    setAccountOpen(false)
    navigate(path)
  }

  const profilePath = accountSpace ? `/app/${accountSpace}/profile` : null
  const supportPath = accountSpace ? `/app/${accountSpace}/support` : null

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
          {/* On phones, the header keeps only the burger and the cart: login lives in the menu. */}
          {!user && <Link className="public-school-nav-login" to={'/login?school=' + encodeURIComponent(schoolSlug) + '&return=' + encodeURIComponent('/school/' + schoolSlug + '/espace')}>Connexion</Link>}
        </nav>
        <div className="public-school-actions">
          {user && <Link className="public-school-favorites-link" to={'/school/' + schoolSlug + '/favoris'} aria-label="Mes formations favorites" title="Mes favoris"><Heart size={18}/>{favorites.length > 0 && <span>{favorites.length}</span>}</Link>}
          {user ? (
            <div className="public-school-account" ref={accountRef}>
              <button
                type="button"
                className="public-school-login public-school-account-trigger"
                aria-expanded={accountOpen}
                aria-label="Ouvrir le menu du compte"
                title={user.full_name}
                onClick={() => setAccountOpen((value) => !value)}
              >
                <UserRound size={17} />
                <span>{accountName}</span>
                <ChevronDown size={14} className={accountOpen ? 'is-open' : ''} />
              </button>
              {accountOpen && <div className="public-school-account-menu">
                <div className="public-school-account-menu-head">
                  <strong>{user.full_name}</strong>
                  <small>{user.email}</small>
                </div>
                {accountSpace && <button type="button" onClick={() => openAccountPage('/school/' + schoolSlug + '/espace')}><LayoutDashboard size={17} /><span>Mon espace</span></button>}
                {accountSpace && <span className="public-school-account-menu-divider is-soft" aria-hidden="true" />}
                {accountSpace && <SchoolNotificationBell space={accountSpace} variant="menu" onNavigate={() => setAccountOpen(false)} />}
                {accountSpace && <SchoolMessageBell space={accountSpace} variant="menu" onNavigate={() => setAccountOpen(false)} />}
                {accountSpace && <span className="public-school-account-menu-divider is-soft" aria-hidden="true" />}
                {profilePath && <button type="button" onClick={() => openAccountPage(profilePath)}><UserRound size={17} /><span>Profil</span></button>}
                {canManageSchool && <button type="button" onClick={() => openAccountPage('/app/manage/settings')}><Settings size={17} /><span>Paramètres de l’école</span></button>}
                {supportPath && <button type="button" onClick={() => openAccountPage(supportPath)}><LifeBuoy size={17} /><span>Support</span></button>}
                <span className="public-school-account-menu-divider" aria-hidden="true" />
                <button type="button" className="is-danger" onClick={() => { setAccountOpen(false); signOut(); navigate('/school/' + schoolSlug) }}><LogOut size={17} /><span>Se déconnecter</span></button>
              </div>}
            </div>
          ) : <Link className="public-school-login public-school-login--visitor" to={'/login?school=' + encodeURIComponent(schoolSlug) + '&return=' + encodeURIComponent('/school/' + schoolSlug + '/espace')}>Connexion</Link>}
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
