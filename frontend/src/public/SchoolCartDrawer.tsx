import { useEffect, useRef } from 'react'
import { ArrowRight, ShoppingBag, Trash2, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { SchoolCartItem } from './schoolCart'
import { formatSchoolMoney } from './publicHelpers'

type SchoolCartDrawerProps = {
  open: boolean
  item: SchoolCartItem | null
  schoolSlug: string
  onClose: () => void
  onClear: () => void
}

export function SchoolCartDrawer({ open, item, schoolSlug, onClose, onClear }: SchoolCartDrawerProps) {
  const closeButton = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const previousOverflow = document.body.style.overflow
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    document.body.style.overflow = 'hidden'
    closeButton.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
      if (event.key === 'Tab') {
        const drawer = document.querySelector('.school-cart-drawer')
        const focusables = document.querySelectorAll<HTMLElement>('.school-cart-drawer button, .school-cart-drawer a')
        const first = focusables[0]
        const last = focusables[focusables.length - 1]
        if (!drawer?.contains(document.activeElement)) {
          event.preventDefault()
          first?.focus()
        } else if (event.shiftKey && document.activeElement === first) {
          event.preventDefault()
          last?.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first?.focus()
        }
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', onKeyDown)
      previousFocus?.focus()
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="school-cart-overlay">
      <button className="school-cart-backdrop" type="button" aria-label="Fermer le panier" onClick={onClose} />
      <aside className="school-cart-drawer" role="dialog" aria-modal="true" aria-labelledby="school-cart-title">
        <header className="school-cart-drawer-header">
          <div><span className="school-kicker">Panier</span><h2 id="school-cart-title">Votre inscription</h2></div>
          <button ref={closeButton} className="school-cart-close" type="button" aria-label="Fermer le panier" onClick={onClose}><X size={20} /></button>
        </header>
        {item ? (
          <>
            <div className="school-cart-drawer-content">
              <article className="school-cart-drawer-item">
                {item.cover_image_url ? <img src={item.cover_image_url} alt="" /> : <div className="school-cart-placeholder" />}
                <div><h3>{item.formation_title}</h3><p>{item.format_type === 'ligne' || item.session_label === 'Accès en ligne' ? 'Formation en ligne' : `Session : ${item.session_label}`}</p><strong>{formatSchoolMoney(item.price_cents, item.currency)}</strong></div>
                <button type="button" aria-label="Retirer du panier" onClick={onClear}><Trash2 size={17} /></button>
              </article>
            </div>
            <footer className="school-cart-drawer-footer">
              <div><span>Total</span><strong>{formatSchoolMoney(item.price_cents, item.currency)}</strong></div>
              <Link to={'/school/' + schoolSlug + '/checkout'}>Passer au paiement <ArrowRight size={17} /></Link>
            </footer>
          </>
        ) : (
          <div className="school-cart-drawer-empty">
            <ShoppingBag size={32} />
            <h3>Votre panier est vide</h3>
            <Link to={'/school/' + schoolSlug + '/formations'}>Voir les formations</Link>
          </div>
        )}
      </aside>
    </div>
  )
}
