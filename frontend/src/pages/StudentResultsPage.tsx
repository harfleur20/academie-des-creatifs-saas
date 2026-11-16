import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useState } from 'react'
import { CalendarCheck2, FileText } from 'lucide-react'
import {
  ApiError,
  ATTENDANCE_LABELS,
  getTranscript,
  listMyTranscripts,
  listStudentAttendance,
  type StudentAttendance,
  type Transcript,
  type TranscriptSummary,
} from '../lib/api'
import { TranscriptView } from '../components/TranscriptView'

/** The student's results: the transcript of each formation (with its PDF), then the attendance. */
export function StudentResultsPage() {
  const [summaries, setSummaries] = useState<TranscriptSummary[] | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [transcript, setTranscript] = useState<Transcript | null>(null)
  const [attendance, setAttendance] = useState<StudentAttendance[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([listMyTranscripts(), listStudentAttendance()])
      .then(([items, rows]) => {
        setSummaries(items)
        setSelectedId(items[0]?.enrollment_id ?? null)
        // Classes still to come have nothing to say about attendance yet.
        const now = Date.now()
        setAttendance(rows.filter((row) => new Date(row.scheduled_at).getTime() <= now))
      })
      .catch((cause) => setError(cause instanceof ApiError ? cause.message : 'Chargement impossible.'))
  }, [])

  useEffect(() => {
    if (selectedId === null) return
    let active = true
    setTranscript(null)
    getTranscript(selectedId)
      .then((value) => { if (active) setTranscript(value) })
      .catch((cause) => { if (active) setError(cause instanceof ApiError ? cause.message : 'Relevé indisponible.') })
    return () => { active = false }
  }, [selectedId])

  return (
    <main className="app-page academic-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Espace étudiant</span>
          <h1>Mes résultats</h1>
          <p>Votre relevé de notes pour chaque formation, à télécharger, et vos présences.</p>
        </div>
      </header>
      {error && <div className="form-error">{error}</div>}

      {summaries && summaries.length > 1 && (
        <div className="transcript-picker" role="tablist" aria-label="Formation">
          {summaries.map((item) => (
            <button
              type="button"
              role="tab"
              key={item.enrollment_id}
              aria-selected={item.enrollment_id === selectedId}
              className={item.enrollment_id === selectedId ? 'is-active' : ''}
              onClick={() => setSelectedId(item.enrollment_id)}
            >
              <strong>{item.formation_title}</strong>
              <small>{item.session_label}{item.average_20 !== null ? ` · ${item.average_20.toLocaleString(activeSchoolLocale())}/20` : ''}</small>
            </button>
          ))}
        </div>
      )}

      {summaries && summaries.length === 0 && (
        <div className="transcript__empty"><FileText size={22} /><p>Votre relevé apparaîtra ici dès votre inscription à une formation.</p></div>
      )}
      {selectedId !== null && !transcript && !error && <div className="transcript__loading">Chargement du relevé…</div>}
      {transcript && <TranscriptView transcript={transcript} />}

      <article className="app-card student-attendance-card">
        <div className="settings-section-heading">
          <div><span className="section-label">Assiduité</span><h2>Mes présences</h2><p>Les séances déjà passées, de la plus ancienne à la plus récente.</p></div>
          <CalendarCheck2 size={19} />
        </div>
        <div className="result-list">
          {attendance.map((row) => (
            <div className="result-row" key={row.course_day_id}>
              <div><strong>{row.title}</strong><small>{new Date(row.scheduled_at).toLocaleString(activeSchoolLocale())}</small></div>
              <span className={'attendance-status ' + (row.status || 'pending')}>{row.status ? ATTENDANCE_LABELS[row.status] : 'À confirmer'}</span>
            </div>
          ))}
          {attendance.length === 0 && <p className="empty-row">Aucune séance passée pour le moment.</p>}
        </div>
      </article>
    </main>
  )
}
