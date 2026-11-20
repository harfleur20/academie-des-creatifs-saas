import { Clock3 } from 'lucide-react'
import { deviceTimeZone } from '../lib/timeZone'

/** Course times show in each person's own time zone: say which, under a planning or a timetable. */
export function DeviceTimeNote() {
  return (
    <p className="device-time-note" style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '4px 0 0', color: '#64748b', fontSize: '0.85em' }}>
      <Clock3 size={13} aria-hidden="true" />
      <span>Heures affichées à l’heure de votre appareil</span>
      <span data-no-translate>({deviceTimeZone()})</span>
    </p>
  )
}
