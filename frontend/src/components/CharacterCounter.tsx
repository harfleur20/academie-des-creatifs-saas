import '../character-counter.css'
import { characterCount } from '../lib/characterLimits'

export function CharacterCounter({
  value,
  count,
  limit,
  label,
}: {
  value?: string
  count?: number
  limit: number
  label?: string
}) {
  const current = count ?? characterCount(value ?? '')
  const exceeded = current > limit
  const warning = !exceeded && current >= Math.ceil(limit * 0.8)

  return (
    <small className={`character-counter${warning ? ' is-warning' : ''}${exceeded ? ' is-exceeded' : ''}`}>
      {label ? `${label} · ` : ''}{current}/{limit} caractères{warning ? ' · Approche de la limite' : ''}{exceeded ? ' · Limite dépassée' : ''}
    </small>
  )
}
