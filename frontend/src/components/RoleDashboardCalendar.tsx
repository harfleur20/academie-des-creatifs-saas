import { useMemo, useState } from 'react'
import { CalendarOff, ChevronLeft, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

export type RoleScheduleItem = {
  id: string
  title: string
  detail: string
  startsAt: string
  durationMinutes: number
  href: string
  status?: string
}

function dateKey(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export function RoleDashboardCalendar({
  items,
}: {
  items: RoleScheduleItem[]
}) {
  const today = new Date()
  const [cursor, setCursor] = useState(
    new Date(today.getFullYear(), today.getMonth(), 1),
  )
  const [selected, setSelected] = useState(dateKey(today))

  const itemsByDate = useMemo(() => {
    const result = new Map<string, RoleScheduleItem[]>()
    for (const item of items) {
      const key = dateKey(new Date(item.startsAt))
      const current = result.get(key) || []
      current.push(item)
      result.set(key, current)
    }
    return result
  }, [items])

  const cells = useMemo(() => {
    const year = cursor.getFullYear()
    const month = cursor.getMonth()
    const first = new Date(year, month, 1)
    const daysInMonth = new Date(year, month + 1, 0).getDate()
    const mondayIndex = (first.getDay() + 6) % 7
    const result: Array<Date | null> = [
      ...Array.from({ length: mondayIndex }, () => null),
    ]
    for (let day = 1; day <= daysInMonth; day += 1) {
      result.push(new Date(year, month, day))
    }
    return result
  }, [cursor])

  const selectedDate = new Date(`${selected}T12:00:00`)
  const dayItems = (itemsByDate.get(selected) || [])
    .slice()
    .sort((a, b) => (
      new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime()
    ))

  return (
    <div className="role-calendar-layout">
      <section className="role-mini-calendar">
        <header>
          <button
            type="button"
            onClick={() => setCursor(
              new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1),
            )}
            aria-label="Mois précédent"
          >
            <ChevronLeft size={15} />
          </button>
          <strong>
            {capitalize(cursor.toLocaleDateString('fr-FR', {
              month: 'long',
              year: 'numeric',
            }))}
          </strong>
          <button
            type="button"
            onClick={() => setCursor(
              new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1),
            )}
            aria-label="Mois suivant"
          >
            <ChevronRight size={15} />
          </button>
        </header>

        <div className="role-mini-calendar__grid">
          {['LUN', 'MAR', 'MER', 'JEU', 'VEN', 'SAM', 'DIM'].map((label) => (
            <span className="role-mini-calendar__weekday" key={label}>
              {label}
            </span>
          ))}
          {cells.map((date, index) => {
            if (!date) {
              return <span key={`empty-${index}`} />
            }
            const key = dateKey(date)
            const hasEvents = itemsByDate.has(key)
            const isToday = key === dateKey(today)
            return (
              <button
                type="button"
                key={key}
                className={[
                  selected === key ? 'is-selected' : '',
                  isToday ? 'is-today' : '',
                  hasEvents ? 'has-event' : '',
                ].filter(Boolean).join(' ')}
                onClick={() => setSelected(key)}
              >
                {date.getDate()}
                {hasEvents && <i />}
              </button>
            )
          })}
        </div>
      </section>

      <section className="role-calendar-day">
        <header>
          <strong>
            {selected === dateKey(today)
              ? 'Aujourd’hui'
              : capitalize(selectedDate.toLocaleDateString('fr-FR', {
                  weekday: 'long',
                }))}
            {' · '}
            {selectedDate.toLocaleDateString('fr-FR', {
              day: 'numeric',
              month: 'long',
              year: 'numeric',
            })}
          </strong>
          {dayItems.length > 0 && <span>{dayItems.length} cours</span>}
        </header>

        <div className="role-calendar-events">
          {dayItems.map((item) => {
            const starts = new Date(item.startsAt)
            const ends = new Date(
              starts.getTime() + item.durationMinutes * 60_000,
            )
            return (
              <article key={item.id}>
                <div>
                  <strong>{item.title}</strong>
                  <p>
                    <b>
                      {starts.toLocaleTimeString('fr-FR', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                      {'–'}
                      {ends.toLocaleTimeString('fr-FR', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </b>
                    {' · '}
                    {item.detail}
                    {item.status ? ` · ${item.status}` : ''}
                  </p>
                </div>
                <Link className="dashboard-text-link" to={item.href}>Voir la séance <ChevronRight size={14} aria-hidden="true" /></Link>
              </article>
            )
          })}
          {dayItems.length === 0 && (
            <div className="role-calendar-empty">
              <CalendarOff size={46} strokeWidth={1.3} aria-hidden="true" />
              <p>Pas de cours {selected === dateKey(today) ? 'aujourd’hui' : 'ce jour'}.</p>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
