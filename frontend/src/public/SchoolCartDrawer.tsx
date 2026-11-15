import { useEffect, useRef, useState } from 'react'
import { ArrowRight, ShoppingBag, Trash2, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { SchoolCartItem } from './schoolCart'
import { formatSchoolDate, formatSchoolMoney, hasSchoolCurrencyRate } from './publicHelpers'
import type { SchoolCurrencyRates } from './currencyRates'

type SchoolCartDrawerProps = {
  open: boolean
  item: SchoolCartItem | null
  schoolSlug: string
  displayCurrency: string
  currencyRates: SchoolCurrencyRates | null
  onClose: () => void
  onClear: () => void
}

const CART_ANIMATION_MS = 420

export function SchoolCartDrawer({ open, item, schoolSlug, displayCurrency, currencyRates, onClose, onClear }: SchoolCartDrawerProps) {
  const closeButton = useRef<HTMLButtonElement>(null)
  const [rendered, setRendered] = useState(open)
  const [active, setActive] = useState(false)

  useEffect(() => {
    let firstFrame = 0
    let secondFrame = 0
    let timeout = 0
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (open) {
      setRendered(true)
      firstFrame = window.requestAnimationFrame(() => {
        secondFrame = window.requestAnimationFrame(() => setActive(true))
      })
    } else {
      setActive(false)
      if (rendered) {
        timeout = window.setTimeout(() => setRendered(false), reducedMotion ? 0 : CART_ANIMATION_MS + 80)
      }
    }

    return () => {
      window.cancelAnimationFrame(firstFrame)
      window.cancelAnimationFrame(secondFrame)
      window.clearTimeout(timeout)
    }
  }, [open])

  useEffect(() => {
    if (!rendered) return
    const previousOverflow = document.body.style.overflow
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    document.body.style.overflow = 'hidden'
    if (open) closeButton.current?.focus()

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && open) onClose()
      if (event.key === 'Tab' && open) {
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
  }, [rendered, open, onClose])

  if (!rendered) return null

  return (
    <div className={`school-cart-overlay ${active ? 'is-open' : 'is-closing'}`} aria-hidden={!open}>
      <button
        className="school-cart-backdrop"
        type="button"
        aria-label="Fermer le panier"
        onClick={onClose}
        tabIndex={open ? 0 : -1}
        style={{ opacity: active ? 1 : 0, transition: 'opacity 360ms ease' }}
      />
      <aside
        className="school-cart-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="school-cart-title"
        onTransitionEnd={(event) => {
          if (!open && event.target === event.currentTarget && event.propertyName === 'transform') setRendered(false)
        }}
        style={{
          transform: active ? 'translate3d(0, 0, 0)' : 'translate3d(100%, 0, 0)',
        }}
      >
        <header className="school-cart-drawer-header">
          <div><span className="school-kicker">Panier</span><h2 id="school-cart-title">Votre inscription</h2></div>
          <button ref={closeButton} className="school-cart-close" type="button" aria-label="Fermer le panier" onClick={onClose}><X size={20} /></button>
        </header>
        {item ? (
          <>
            <div className="school-cart-drawer-content">
              <article className="school-cart-drawer-item">
                {item.cover_image_url ? <img src={item.cover_image_url} alt="" /> : <div className="school-cart-placeholder" />}
                <div>
                  <h3>{item.formation_title}</h3>
                  <p>{item.format_type === 'ligne' || item.session_label === 'Accès en ligne' ? 'Formation en ligne' : `Session : ${item.session_label}`}</p>
                  <strong>{formatSchoolMoney(item.price_cents, item.currency, displayCurrency, currencyRates)}</strong>
                  {item.payment_mode === 'installments' ? (
                    <small className="school-cart-mode">Paiement en plusieurs fois</small>
                  ) : item.deposit_cents != null && item.balance_cents != null ? (
                    <small className="school-cart-mode">
                      Acompte de {formatSchoolMoney(item.deposit_cents, item.currency, displayCurrency, currencyRates)} à la réservation, puis solde de {formatSchoolMoney(item.balance_cents, item.currency, displayCurrency, currencyRates)}{item.balance_due_date ? ` avant le ${formatSchoolDate(item.balance_due_date)}` : ''}.
                    </small>
                  ) : null}
                </div>
                <button type="button" aria-label="Retirer du panier" onClick={onClear}><Trash2 size={17} /></button>
              </article>
            </div>
            <footer className="school-cart-drawer-footer">
              <div>
                <span>Total</span>
                <strong>{formatSchoolMoney(item.price_cents, item.currency, displayCurrency, currencyRates)}</strong>
              </div>
              {displayCurrency.toUpperCase() !== item.currency.toUpperCase() && <small className="school-currency-conversion-note">{hasSchoolCurrencyRate(item.currency, displayCurrency, currencyRates) ? `Équivalent indicatif · paiement en ${formatSchoolMoney(item.price_cents, item.currency)}.` : `Conversion momentanément indisponible · paiement en ${formatSchoolMoney(item.price_cents, item.currency)}.`}</small>}
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
