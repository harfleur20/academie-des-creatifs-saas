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

export function StudentLevelBadge({ level, className = '', locked = false, alt, schoolName }: {
  level?: BadgeLevel | null
  className?: string
  locked?: boolean
  alt?: string
  schoolName?: string | null
}) {
  const currentLevel = level || 'aventurier'
  const number = badgeLevelNumber(currentLevel)
  const schoolMark = schoolName?.trim().charAt(0).toLocaleUpperCase('fr-FR') || 'A'
  const title = alt || `Sceau créatif ${LABELS[currentLevel]}${locked ? ' à débloquer' : ''}`

  return <span className={`student-level-badge student-level-badge--${currentLevel} ${locked ? 'is-locked' : 'is-earned'} ${className}`.trim()}>
    <svg viewBox="0 0 120 120" role="img" aria-label={title} xmlns="http://www.w3.org/2000/svg">
      <circle cx="60" cy="60" r="56" className="student-level-badge__outer" />
      <circle cx="60" cy="60" r="48" className="student-level-badge__ring" />
      <circle cx="60" cy="60" r="41" className="student-level-badge__field" />
      {LEVELS.map((stage, index) => <circle key={stage} cx={32 + index * 14} cy="18" r="2.7" className={index < number ? 'student-level-badge__milestone is-active' : 'student-level-badge__milestone'} />)}
      <path d="M35 49c9-3 17-2 25 3v27c-8-5-16-6-25-3V49Zm50 0c-9-3-17-2-25 3v27c8-5 16-6 25-3V49Z" className="student-level-badge__book" />
      <path d="M60 52v27M38 54c8-2 15-1 19 2m25-2c-8-2-15-1-19 2" className="student-level-badge__book-lines" />
      <path d="m60 31 2.4 6.6L69 40l-6.6 2.4L60 49l-2.4-6.6L51 40l6.6-2.4L60 31Z" className="student-level-badge__spark" />
      <path d="M41 91h38" className="student-level-badge__signature-line" />
      <text x="60" y="102" textAnchor="middle" className="student-level-badge__school-mark">{schoolMark}</text>
    </svg>
  </span>
}
