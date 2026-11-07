import type { StudentBadge } from '../lib/api'

type BadgeLevel = StudentBadge['level']

const LEVELS: BadgeLevel[] = ['aventurier', 'debutant', 'intermediaire', 'semi_pro', 'professionnel']
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
  const ringLevel = !locked && ringPct < 100 ? nextBadgeLevel(currentLevel) : currentLevel
  const imageAlt = alt || `Badge ${LABELS[currentLevel]}${locked ? ' à débloquer' : ''}`
  const circumference = 2 * Math.PI * 44
  const safePct = Math.max(0, Math.min(100, ringPct))

  return <span className={`student-level-badge student-level-badge--${currentLevel} student-level-badge--ring-${ringLevel} ${locked ? 'is-locked' : 'is-earned'} ${className}`.trim()}>
    <svg viewBox="0 0 100 100" role="img" aria-label={imageAlt}>
      <circle cx="50" cy="50" r="44" className="student-level-badge__track" />
      <circle cx="50" cy="50" r="44" className="student-level-badge__arc" strokeDasharray={circumference} strokeDashoffset={circumference * (1 - safePct / 100)} />
      <circle cx="50" cy="50" r="34" className="student-level-badge__halo" />
      <circle cx="50" cy="50" r="28" className="student-level-badge__core" />
      {currentLevel === 'aventurier' && <g className="student-level-badge__motif">
        <path d="M50 30 35 66h15V30Zm2 1v35h14L52 31Z" />
        <path d="m47 31 12-3-7 7z" />
      </g>}
      {currentLevel === 'debutant' && <g className="student-level-badge__motif" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M31 50c9-12 24-15 38-7l6-6v19l-7-6c-13 12-27 12-37 0Z" /><circle cx="43" cy="45" r="1" fill="currentColor" stroke="none" /><path d="M58 42c-3 5-3 11 0 16" />
      </g>}
      {currentLevel === 'intermediaire' && <g className="student-level-badge__motif" fill="none" stroke="currentColor" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round">
        <path d="M44 58c0-13 6-24 17-30 8 12 8 23 0 33l-10 10-8-8 1-5Z" /><circle cx="57" cy="44" r="4" /><path d="m44 56-11 2-6 12 16-7m18-2 2 12-12 6 2-16M38 76l-7 6" />
      </g>}
      {currentLevel === 'semi_pro' && <g className="student-level-badge__motif" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        <path d="M34 71c8-17 18-21 27-27 6-4 9-8 9-15" /><path d="m46 55 3 4m9-15 3 4" /><path d="m32 34 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1 3-6Z" fill="currentColor" stroke="none" />
      </g>}
      {currentLevel === 'professionnel' && <g className="student-level-badge__motif" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="57" cy="32" r="5" fill="currentColor" stroke="none" /><path d="m53 42-8 13 12 8m-3-19 10 6 9-4m-27 9-13-1-7 8m31 1 10 10 9 1m-19-11-9 10-14 2" />
      </g>}
    </svg>
  </span>
}
