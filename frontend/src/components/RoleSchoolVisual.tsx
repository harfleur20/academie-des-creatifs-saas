import {
  BookOpen,
  CalendarDays,
  GraduationCap,
  NotebookPen,
} from 'lucide-react'
import { SchoolLogo } from '../brand/SchoolLogo'

type RoleSchoolVisualProps = {
  role: 'teacher' | 'student'
  schoolName: string
  logoUrl?: string | null
}

export function RoleSchoolVisual({
  role,
  schoolName,
  logoUrl,
}: RoleSchoolVisualProps) {
  const isTeacher = role === 'teacher'
  const spaceLabel = isTeacher ? 'Espace pédagogique' : 'Espace étudiant'
  const thirdTopic = isTeacher ? 'Évaluations' : 'Résultats'

  return (
    <div
      className={`role-school-visual role-school-visual--${role}`}
      aria-hidden="true"
    >
      <div className="role-school-visual__board">
        <div className="role-school-visual__brand">
          <SchoolLogo
            logoUrl={logoUrl}
            alt={schoolName}
            className="role-school-visual__logo"
          />
          <span>
            <small>{schoolName}</small>
            <strong>{spaceLabel}</strong>
          </span>
        </div>

        <div className="role-school-visual__rule" />

        <div className="role-school-visual__topics">
          <span><BookOpen size={16} /> Cours</span>
          <span><CalendarDays size={16} /> Planning</span>
          <span><NotebookPen size={16} /> {thirdTopic}</span>
        </div>
      </div>

      <span className="role-school-visual__bubble role-school-visual__bubble--cap">
        <GraduationCap size={26} />
      </span>
      <span className="role-school-visual__bubble role-school-visual__bubble--book">
        <BookOpen size={21} />
      </span>
      <span className="role-school-visual__bubble role-school-visual__bubble--calendar">
        <CalendarDays size={20} />
      </span>
    </div>
  )
}
