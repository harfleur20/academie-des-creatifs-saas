import { useEffect, useState } from 'react'
import { Video } from 'lucide-react'
import { Link } from 'react-router-dom'
import { liveCountdown, liveState, LIVE_ROOM_OPENS_MINUTES, LIVE_STATE_LABELS, type LiveDay } from '../lib/liveWindow'
import './LiveJoinButton.css'

/** The current time, refreshed every 30 seconds: the button opens on its own, no reload needed. */
export function useNow(every = 30_000) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), every)
    return () => window.clearInterval(timer)
  }, [every])
  return now
}

export function LiveStateLabel({ day, className }: { day: LiveDay; className?: string }) {
  const now = useNow()
  return <span className={className}>{LIVE_STATE_LABELS[liveState(day, now)]}</span>
}

/**
 * The live class's button, as on the mother site: greyed with "Dans 1 j 2 h" until the room
 * opens, then "Commencer le cours" for the class's teacher (it starts as they enter) or
 * "Rejoindre le cours"; "Cours terminé" once entries are closed.
 */
export function LiveJoinButton({
  day,
  href,
  enabled,
  responsible = false,
  primary = false,
}: {
  day: LiveDay
  href: string
  enabled: boolean
  /** The class's own teacher: the class starts when they enter. */
  responsible?: boolean
  primary?: boolean
}) {
  const now = useNow()
  if (!enabled) return <small className="live-join-note">Service live en cours de configuration.</small>
  const state = liveState(day, now)
  if (state === 'cancelled' || state === 'closed') return null
  const kind = `${primary ? 'primary-button' : 'secondary-button'} live-join-button`
  if (state === 'planned') {
    return (
      <button type="button" className={`${kind} is-waiting`} disabled title={`La salle ouvre ${LIVE_ROOM_OPENS_MINUTES} minutes avant le début du cours.`}>
        <Video size={15} aria-hidden="true" /><span data-no-translate>{liveCountdown(Date.parse(day.scheduled_at) - now)}</span>
      </button>
    )
  }
  if (state === 'ended') {
    return <button type="button" className={`${kind} is-over`} disabled><Video size={15} aria-hidden="true" />Cours terminé</button>
  }
  return (
    <Link className={kind} to={href}>
      <Video size={15} aria-hidden="true" />{responsible && !day.started_at ? 'Commencer le cours' : 'Rejoindre le cours'}
    </Link>
  )
}
