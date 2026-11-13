import { useEffect, useRef, useState } from 'react'
import { ArrowRight, ChevronDown } from 'lucide-react'
import { ApiError, type DemoInfo } from '../lib/api'
import { DEMO_PLACES, enterDemo } from '../lib/demo'
import type { DemoPlace } from '../lib/demoState'

/** "Voir la démo": choose a read-only area of the demo school to visit. */
export function DemoMenu({ info }: { info: DemoInfo }) {
  const [isOpen, setIsOpen] = useState(false)
  const [busy, setBusy] = useState<DemoPlace | null>(null)
  const [error, setError] = useState('')
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!isOpen) return undefined

    const onPointerDown = (event: PointerEvent) => {
      if (event.target instanceof Node && !rootRef.current?.contains(event.target)) setIsOpen(false)
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false)
        triggerRef.current?.focus()
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [isOpen])

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
    <div className="demo-menu" ref={rootRef}>
      <button
        ref={triggerRef}
        className="lp-btn lp-btn--ghost demo-menu__trigger"
        type="button"
        aria-expanded={isOpen}
        aria-controls={isOpen ? 'demo-menu-panel' : undefined}
        onClick={() => {
          setError('')
          setIsOpen((open) => !open)
        }}
      >
        Voir la démo <ChevronDown size={16} aria-hidden="true" />
      </button>
      {isOpen && (
        <div
          className="demo-menu__panel"
          id="demo-menu-panel"
          role="region"
          aria-labelledby="demo-menu-title"
        >
          <div className="demo-menu__header">
            <strong id="demo-menu-title">Visitez {info.school_name}</strong>
            <p>Choisissez un espace à explorer.</p>
          </div>
          <ul className="demo-menu__places">
            {DEMO_PLACES.map(({ place, label, text }) => (
              <li key={place}>
                <button type="button" disabled={busy !== null} onClick={() => void open(place)}>
                  <strong>{label} <ArrowRight size={17} aria-hidden="true" /></strong>
                  <span>{busy === place ? 'Ouverture…' : text}</span>
                </button>
              </li>
            ))}
          </ul>
          {error && <div className="form-error" role="alert">{error}</div>}
          <p className="demo-menu__note">Sans compte et en lecture seule : rien n’est enregistré.</p>
        </div>
      )}
    </div>
  )
}
