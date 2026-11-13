import { useEffect, useState } from 'react'
import { ArrowRight, X } from 'lucide-react'
import { ApiError, type DemoInfo } from '../lib/api'
import { DEMO_PLACES, enterDemo } from '../lib/demo'
import type { DemoPlace } from '../lib/demoState'

/** "Voir la démo": pick the place of the demo school to visit, read only, without an account. */
export function DemoDialog({ info, onClose }: { info: DemoInfo; onClose: () => void }) {
  const [busy, setBusy] = useState<DemoPlace | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  async function open(place: DemoPlace) {
    if (!info.school_name || !info.organization_slug) return
    setBusy(place)
    setError('')
    try {
      await enterDemo(place, { school_name: info.school_name, organization_slug: info.organization_slug })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'La démo n’a pas pu s’ouvrir. Réessayez.')
      setBusy(null)
    }
  }

  return (
    <div className="demo-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section className="demo-dialog" role="dialog" aria-modal="true" aria-labelledby="demo-dialog-title">
        <header>
          <div>
            <h2 id="demo-dialog-title">Visitez {info.school_name}</h2>
            <p>Une école de démonstration, avec ses formations, ses professeurs et ses étudiants. Choisissez où entrer : vous pourrez passer d’un espace à l’autre.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Fermer"><X size={18} /></button>
        </header>
        <div className="demo-dialog__places">
          {DEMO_PLACES.map(({ place, label, text }) => (
            <button key={place} type="button" disabled={busy !== null} onClick={() => void open(place)}>
              <strong>{label} <ArrowRight size={17} /></strong>
              <span>{busy === place ? 'Ouverture…' : text}</span>
            </button>
          ))}
        </div>
        {error && <div className="form-error">{error}</div>}
        <p className="demo-dialog__note">Sans compte et en lecture seule : naviguez librement, rien n’est enregistré.</p>
      </section>
    </div>
  )
}
