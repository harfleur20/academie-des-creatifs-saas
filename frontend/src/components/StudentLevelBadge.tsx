import { useId } from 'react'
import type { StudentBadge } from '../lib/api'

type BadgeLevel = StudentBadge['level']

const LEVELS: BadgeLevel[] = ['aventurier', 'debutant', 'intermediaire', 'semi_pro', 'professionnel']
/** The mother site's badge artwork, one per level. */
const BADGE_ART: Record<BadgeLevel, string> = {
  aventurier: '/student-badges/aventurier.svg',
  debutant: '/student-badges/debutant.svg',
  intermediaire: '/student-badges/intermediaire.svg',
  semi_pro: '/student-badges/semi-pro.svg',
  professionnel: '/student-badges/professionnel.svg',
}

/**
 * The ring colours of the mother site (BadgeRing): the ring previews the badge the student
 * is working toward, in that badge's colour; Professionnel, the last one, keeps its own.
 */
const RING_COLORS: Record<BadgeLevel, string> = {
  aventurier: '#35bbd9',
  debutant: '#264156',
  intermediaire: '#514192',
  semi_pro: '#1cab89',
  professionnel: '#022733',
}

function mixWithWhite(hex: string, amount: number) {
  const value = Number.parseInt(hex.replace('#', ''), 16)
  const mix = (channel: number) => Math.round(channel + (255 - channel) * amount)
  return `rgb(${mix((value >> 16) & 255)}, ${mix((value >> 8) & 255)}, ${mix(value & 255)})`
}

/** The colour of the ring for a student at this level: the next badge's (the mother site's rule). */
export function badgeRingColor(level?: BadgeLevel | null) {
  const current = level || 'aventurier'
  return RING_COLORS[current === 'professionnel' ? current : nextBadgeLevel(current)]
}

/** The same colour for a straight progress bar, lighter at its end like the ring's shine. */
export function badgeProgressFill(level?: BadgeLevel | null) {
  const color = badgeRingColor(level)
  return `linear-gradient(90deg, ${color}, ${mixWithWhite(color, 0.35)})`
}

function withAlpha(hex: string, alpha: number) {
  const value = Number.parseInt(hex.replace('#', ''), 16)
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`
}

const LABELS: Record<BadgeLevel, string> = {
  aventurier: 'Aventurier',
  debutant: 'Débutant',
  intermediaire: 'Intermédiaire',
  semi_pro: 'Semi-pro',
  professionnel: 'Professionnel',
}

export function badgeLevelFromValue(value: string | null | undefined): BadgeLevel | null {
  return LEVELS.find((level) => level === value) ?? null
}

export function badgeLevelNumber(level?: BadgeLevel | null) {
  return LEVELS.indexOf(level || 'aventurier') + 1
}

export function badgeRingPercent(badge: Pick<StudentBadge, 'ring_pct'>) {
  return Math.round(badge.ring_pct)
}

function nextBadgeLevel(level: BadgeLevel) {
  const index = LEVELS.indexOf(level)
  return LEVELS[index + 1] ?? level
}

export function StudentLevelBadge({ level, className = '', locked = false, alt, ringPct = 100 }: {
  level?: BadgeLevel | null
  className?: string
  locked?: boolean
  alt?: string
  ringPct?: number
}) {
  const currentLevel = level || 'aventurier'
  const isMaxLevel = currentLevel === 'professionnel'
  // As on the mother site: the ring previews the next badge, the last one keeps its colour.
  const ringLevel = isMaxLevel || locked ? currentLevel : nextBadgeLevel(currentLevel)
  const stroke = RING_COLORS[ringLevel]
  const imageAlt = alt || `Badge ${LABELS[currentLevel]}${locked ? ' à débloquer' : ''}`
  const circumference = 2 * Math.PI * 44
  const safePct = isMaxLevel ? 100 : Math.max(0, Math.min(100, ringPct))
  const gradientId = `badge-ring-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`

  return <span className={`student-level-badge student-level-badge--${currentLevel} student-level-badge--ring-${ringLevel} ${locked ? 'is-locked' : 'is-earned'} ${className}`.trim()}>
    <svg viewBox="0 0 100 100" role="img" aria-label={imageAlt}>
      <defs>
        <linearGradient id={gradientId} gradientUnits="userSpaceOnUse" x1="100" y1="0" x2="0" y2="100">
          <stop offset="0%" stopColor={stroke} stopOpacity="1" />
          <stop offset="48%" stopColor={mixWithWhite(stroke, 0.48)} stopOpacity="0.92" />
          <stop offset="100%" stopColor={stroke} stopOpacity="1" />
          <animateTransform attributeName="gradientTransform" type="rotate" from="0 50 50" to="360 50 50" dur="2.8s" repeatCount="indefinite" />
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="34" className="student-level-badge__halo" style={{ fill: withAlpha(stroke, 0.12) }} />
      <circle cx="50" cy="50" r="44" className="student-level-badge__track" style={{ stroke: withAlpha(stroke, 0.22) }} />
      <circle cx="50" cy="50" r="44" className="student-level-badge__arc" style={{ stroke: `url(#${gradientId})` }} strokeDasharray={circumference} strokeDashoffset={circumference * (1 - safePct / 100)} />
    </svg>
    <img className="student-level-badge__art" src={BADGE_ART[currentLevel]} alt="" aria-hidden="true" draggable={false} />
  </span>
}
