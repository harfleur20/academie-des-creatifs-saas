import { ArrowRight } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { BrandLogo } from '../brand/BrandLogo'
import { readDemoState } from '../lib/demoState'
import '../landing.css'

const REGISTER_URL = '/login?mode=register'

function initials(name: string) {
  return name.split(' ').filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || '?'
}

export function LandingNavbar() {
  const { user, loading } = useAuth()
  // A demo visitor holds the demo school's read-only token: they are not signed in for real.
  const signedIn = Boolean(user && !loading && !readDemoState())
  const firstName = user?.full_name.trim().split(' ')[0] || ''

  return (
    <header className="lp-header">
      <div className="lp-container lp-header__inner">
        <a className="lp-brand" href="/" aria-label="Académie des Créatifs, accueil">
          <BrandLogo className="lp-brand__logo" />
          <span>
            <strong>Académie des Créatifs</strong>
            <small>pour les écoles</small>
          </span>
        </a>
        <nav className="lp-nav" aria-label="Navigation principale">
          <a href="/#fonctionnalites">Fonctionnalités</a>
          <a href="/#fonctionnement">Comment ça marche</a>
          <a href="/#tarifs">Tarifs</a>
          <a href="/#faq">Questions</a>
        </nav>
        <div className="lp-header__actions">
          {signedIn && user ? (
            <>
              <span className="lp-account">
                <span className="lp-account__avatar" aria-hidden="true">
                  {user.avatar_url ? <img src={user.avatar_url} alt="" /> : initials(user.full_name)}
                </span>
                <span className="lp-account__hello">Bonjour, <strong>{firstName}</strong></span>
              </span>
              <a className="lp-btn lp-btn--primary lp-btn--small" href="/app">
                Mon espace <ArrowRight size={16} />
              </a>
            </>
          ) : (
            <>
              <a className="lp-link" href="/login">Se connecter</a>
              <a className="lp-btn lp-btn--primary lp-btn--small" href={REGISTER_URL}>
                Créer mon école <ArrowRight size={16} />
              </a>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
