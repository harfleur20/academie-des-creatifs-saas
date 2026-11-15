import { useEffect, useState } from 'react'
import { Award, CalendarCheck2, Download, FileText, Sigma, X } from 'lucide-react'
import { ApiError, downloadTranscriptPdf, getTranscript, type Transcript } from '../lib/api'
import { saveBlobFile } from '../lib/download'
import '../transcript.css'

const numbers = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 })

function day(value: string | null) {
  return value ? new Date(value.slice(0, 10) + 'T00:00:00').toLocaleDateString('fr-FR') : '-'
}

function pdfName(transcript: Transcript) {
  const base = `releve-${transcript.student_code || transcript.student_name}-${transcript.formation_title}`
  return base.normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^A-Za-z0-9]+/g, '-').replace(/^-|-$/g, '').toLowerCase().slice(0, 90) + '.pdf'
}

/**
 * The transcript of one enrollment: the official average and its mention, the attendance, the
 * badge, and every grade by kind (backend app/services/transcripts.py). Shared by the student's
 * results, the management's follow-up and the teacher's students.
 */
export function TranscriptView({ transcript, showStudent = false }: { transcript: Transcript; showStudent?: boolean }) {
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState('')
  const final = transcript.status === 'final'

  async function download() {
    setDownloading(true)
    setError('')
    try {
      saveBlobFile(await downloadTranscriptPdf(transcript.enrollment_id), pdfName(transcript))
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Téléchargement impossible.')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <article className="transcript">
      <header className="transcript__head">
        <div>
          <span className="section-label">Relevé de notes</span>
          <h2>{transcript.formation_title}</h2>
          <p>
            {showStudent && <><strong>{transcript.student_name}</strong>{transcript.student_code ? ` · ${transcript.student_code}` : ''} · </>}
            {transcript.session_label} · {transcript.format_label} · du {day(transcript.session_start)} au {day(transcript.session_end)}
          </p>
        </div>
        <div className="transcript__actions">
          <span className={`transcript__status ${final ? 'is-final' : 'is-provisional'}`}>{final ? 'Définitif' : 'Provisoire'}</span>
          <button type="button" className="primary-button" disabled={downloading} onClick={() => void download()}>
            <Download size={15} /> {downloading ? 'Préparation…' : 'Télécharger le PDF'}
          </button>
        </div>
      </header>
      {error && <div className="form-error">{error}</div>}

      <div className="transcript__figures">
        <article>
          <span><Sigma size={15} /> Moyenne générale</span>
          <strong>{transcript.average_20 === null ? '-' : `${numbers.format(transcript.average_20)} / 20`}</strong>
          <small>{transcript.average_20 === null ? 'Pas encore de note' : transcript.mention ?? 'Sans mention'}</small>
        </article>
        <article>
          <span><CalendarCheck2 size={15} /> Assiduité</span>
          <strong>{transcript.counted_sessions ? `${transcript.attended_sessions} / ${transcript.counted_sessions} séances` : '-'}</strong>
          <small>{transcript.attendance_pct === null ? 'Aucune séance comptée' : `${numbers.format(transcript.attendance_pct)} % de présence`}</small>
        </article>
        <article>
          <span><Award size={15} /> Badge</span>
          <strong>{transcript.badge_label ?? '-'}</strong>
          <small>Niveau atteint</small>
        </article>
      </div>

      {transcript.groups.length === 0 && (
        <div className="transcript__empty"><FileText size={22} /><p>Aucune note pour le moment.</p></div>
      )}
      {transcript.groups.map((group) => (
        <section className="transcript__group" key={group.key}>
          <h3>{group.label}</h3>
          <div className="transcript__lines" role="table" aria-label={group.label}>
            <div className="transcript__line transcript__line--head" role="row">
              <span role="columnheader">Évaluation</span>
              <span role="columnheader">Date</span>
              <span role="columnheader">Note /20</span>
              <span role="columnheader">Barème</span>
            </div>
            {group.lines.map((line, index) => (
              <div className={`transcript__line${line.counted ? '' : ' is-excluded'}`} role="row" key={line.label + index}>
                <span role="cell" className="transcript__label">
                  {line.label}
                  {line.note && <small>{line.note}</small>}
                </span>
                <span role="cell" className="transcript__date">{day(line.date)}</span>
                <span role="cell" className="transcript__score">{numbers.format(line.score_20)}</span>
                <span role="cell" className="transcript__scale">{numbers.format(line.score)}/{numbers.format(line.max_score)}</span>
              </div>
            ))}
          </div>
        </section>
      ))}

      <p className="transcript__rule">
        Moyenne : toutes les notes ramenées sur 20, à poids égal. Les quiz automatiques sont affichés mais ne comptent pas.
        Mentions : Passable dès 10, Assez bien dès 12, Bien dès 14, Très bien dès 16.
        {!final && ' Relevé provisoire : la session est en cours, les notes peuvent encore évoluer.'}
      </p>
    </article>
  )
}

/** The transcript of a student, opened from the management's follow-up or the teacher's students. */
export function TranscriptDialog({ enrollmentId, onClose }: { enrollmentId: number; onClose: () => void }) {
  const [transcript, setTranscript] = useState<Transcript | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setTranscript(null)
    setError('')
    getTranscript(enrollmentId)
      .then((value) => { if (active) setTranscript(value) })
      .catch((cause) => { if (active) setError(cause instanceof ApiError ? cause.message : 'Relevé indisponible.') })
    return () => { active = false }
  }, [enrollmentId])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    document.body.classList.add('transcript-dialog-open')
    window.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.classList.remove('transcript-dialog-open')
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [onClose])

  return (
    <div className="transcript-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <div className="transcript-dialog" role="dialog" aria-modal="true" aria-label="Relevé de notes">
        <button type="button" className="transcript-dialog__close" aria-label="Fermer" onClick={onClose}><X size={18} /></button>
        {error && <div className="form-error">{error}</div>}
        {!transcript && !error && <div className="transcript__loading">Chargement du relevé…</div>}
        {transcript && <TranscriptView transcript={transcript} showStudent />}
      </div>
    </div>
  )
}
