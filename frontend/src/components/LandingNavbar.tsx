import { ArrowRight } from 'lucide-react'
import { BrandLogo } from '../brand/BrandLogo'
import '../landing.css'

const REGISTER_URL = '/login?mode=register'

export function LandingNavbar() {
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
          <a className="lp-link" href="/login">Se connecter</a>
          <a className="lp-btn lp-btn--primary lp-btn--small" href={REGISTER_URL}>
            Créer mon école <ArrowRight size={16} />
          </a>
        </div>
      </div>
    </header>
  )
}
