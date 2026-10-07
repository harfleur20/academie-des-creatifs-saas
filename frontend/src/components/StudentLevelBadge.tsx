import type { StudentBadge } from '../lib/api'

type BadgeLevel = StudentBadge['level']

const BADGE_IMAGES: Record<BadgeLevel, string> = {
  aventurier: '/student-badges/level-1.webp',
  debutant: '/student-badges/level-1.webp',
  intermediaire: '/student-badges/level-2.webp',
  semi_pro: '/student-badges/level-3.webp',
  professionnel: '/student-badges/level-4.webp',
}

const BADGE_NUMBERS: Record<BadgeLevel, number> = {
  aventurier: 1,
  debutant: 1,
  intermediaire: 2,
  semi_pro: 3,
  professionnel: 4,
}

export function isBadgePreview(level?: BadgeLevel | null) {
  return !level || level === 'aventurier'
}

export function badgeLevelFromValue(
  value: string | null | undefined,
): BadgeLevel | null {
  if (
    value === 'aventurier'
    || value === 'debutant'
    || value === 'intermediaire'
    || value === 'semi_pro'
    || value === 'professionnel'
  ) {
    return value
  }
  return null
}

export function badgeLevelNumber(level?: BadgeLevel | null) {
  return BADGE_NUMBERS[level || 'aventurier']
}

export function StudentLevelBadge({
  level,
  className = '',
  locked,
  alt,
}: {
  level?: BadgeLevel | null
  className?: string
  locked?: boolean
  alt?: string
}) {
  const currentLevel = level || 'aventurier'
  const number = badgeLevelNumber(currentLevel)
  const isLocked = locked ?? isBadgePreview(currentLevel)
  const imageAlt = alt || (
    isLocked
      ? `Badge niveau ${number} à débloquer`
      : `Badge niveau ${number}`
  )

  return (
    <span
      className={`student-level-badge ${isLocked ? 'is-locked' : 'is-earned'} ${className}`.trim()}
    >
      <img src={BADGE_IMAGES[currentLevel]} alt={imageAlt} />
    </span>
  )
}
