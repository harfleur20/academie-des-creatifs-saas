import type { ReactNode } from 'react'
import { ArrowLeft, ArrowRight, Lock } from 'lucide-react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { exitDemo } from '../lib/demo'
import { DEMO_LOCKED_MESSAGE, demoScreenLocked } from '../lib/demoState'
import '../demo.css'

/** A menu link; in the demo, a screen outside the tour shows greyed and does not open. */
export function MenuLink({ to, end, children }: { to: string; end?: boolean; children: ReactNode }) {
  if (demoScreenLocked(to)) {
    return (
      <span className="demo-locked-link" role="link" aria-disabled="true" title={DEMO_LOCKED_MESSAGE}>
        {children}
        <Lock className="demo-locked-link__icon" size={13} aria-hidden="true" />
      </span>
    )
  }
  return <NavLink to={to} end={end}>{children}</NavLink>
}

/** The page of a space; in the demo, a screen outside the tour (typed in the address bar,
 *  or reached from a menu of the top bar) says so instead of loading. */
export function SpaceOutlet() {
  const location = useLocation()
  if (!demoScreenLocked(location.pathname)) return <Outlet />
  const home = location.pathname.match(/^\/app\/(manage|teacher|student)/)?.[0] ?? '/'
  return (
    <main className="app-page demo-locked-screen">
      <section>
        <span className="demo-locked-screen__icon"><Lock size={22} /></span>
        <h1>Cet écran n’est pas ouvert dans la démo</h1>
        <p>Il est disponible dès que vous créez votre école. Dans la démo, les écrans ouverts sont ceux du menu qui ne sont pas grisés.</p>
        <div>
          <Link className="secondary-button" to={home}><ArrowLeft size={15} /> Revenir à l’accueil de l’espace</Link>
          <button type="button" className="primary-button" onClick={() => exitDemo('/login?mode=register')}>Créer mon école <ArrowRight size={15} /></button>
        </div>
      </section>
    </main>
  )
}
