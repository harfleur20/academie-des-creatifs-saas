import { useEffect, useState } from 'react'
import { ArrowRight, Eye, X } from 'lucide-react'
import { DEMO_PLACES, enterDemo, exitDemo } from '../lib/demo'
import { readDemoState } from '../lib/demoState'
import '../demo.css'

const SHORT_LABELS: Record<string, string> = { site: 'Site', manage: 'Direction', teacher: 'Professeur', student: 'Étudiant' }

/** While visiting the demo: where you are, the other places, and the way out. */
export function DemoBar() {
  const [state] = useState(readDemoState)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!state) return
    document.body.classList.add('has-demo-bar')
    return () => document.body.classList.remove('has-demo-bar')
  }, [state])

  if (!state) return null

  return (
    <aside className="demo-bar" aria-label="Démonstration">
      <span className="demo-bar__label"><Eye size={15} /> Démo · {state.school_name} <small>lecture seule</small></span>
      <nav className="demo-bar__places" aria-label="Changer d’espace">
        {DEMO_PLACES.map(({ place }) => (
          <button
            key={place}
            type="button"
            className={place === state.place ? 'is-active' : undefined}
            aria-current={place === state.place ? 'page' : undefined}
            disabled={busy}
            onClick={() => {
              if (place === state.place) return
              setBusy(true)
              void enterDemo(place, state).catch(() => setBusy(false))
            }}
          >
            {SHORT_LABELS[place]}
          </button>
        ))}
      </nav>
      <button type="button" className="demo-bar__cta" onClick={() => exitDemo('/login?mode=register')}>
        Créer mon école <ArrowRight size={14} />
      </button>
      <button type="button" className="demo-bar__close" onClick={() => exitDemo('/')} aria-label="Quitter la démo" title="Quitter la démo">
        <X size={16} />
      </button>
    </aside>
  )
}
