import { useEffect, useState, type FormEvent } from 'react'
import { Download, Video } from 'lucide-react'
import { ApiError, archiveLiveRecording, listLiveRecordings, retryLiveRecording, updateLiveRecording, type LiveRecording } from '../lib/api'

function durationLabel(seconds: number | null) {
  if (seconds === null) return ''
  const minutes = Math.floor(seconds / 60)
  return `${minutes} min`
}

export function LiveRecordingsPanel({
  sessionId,
  canManage = false,
  finishedDayIds,
}: {
  sessionId: number
  canManage?: boolean
  finishedDayIds?: Set<number>
}) {
  const [recordings, setRecordings] = useState<LiveRecording[]>([])
  const [loading, setLoading] = useState(true)
  const [workingId, setWorkingId] = useState<number | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    function refresh() {
      void listLiveRecordings(sessionId)
        .then((rows) => { if (!cancelled) {
          setRecordings((current) => rows.map((row) => {
            const previous = current.find((item) => item.id === row.id)
            return previous?.status === row.status && previous.content_url && row.content_url
              ? { ...row, content_url: previous.content_url }
              : row
          }))
          setError('')
        } })
        .catch((cause) => { if (!cancelled) setError(cause instanceof ApiError ? cause.message : 'Replays indisponibles.') })
        .finally(() => { if (!cancelled) setLoading(false) })
    }
    refresh()
    const timer = window.setInterval(refresh, 30_000)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [sessionId])

  async function update(recording: LiveRecording, changes: Parameters<typeof updateLiveRecording>[1]) {
    setWorkingId(recording.id)
    setError('')
    try {
      const updated = await updateLiveRecording(recording.id, changes)
      setRecordings((rows) => rows.map((row) => row.id === recording.id ? updated : row))
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Modification du replay impossible.')
    } finally {
      setWorkingId(null)
    }
  }

  async function retry(recording: LiveRecording) {
    setWorkingId(recording.id)
    setError('')
    try {
      await retryLiveRecording(recording.id)
      setRecordings((rows) => rows.map((row) => row.id === recording.id ? { ...row, status: 'processing' } : row))
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Relance du traitement impossible.')
    } finally {
      setWorkingId(null)
    }
  }

  async function archive(recording: LiveRecording) {
    if (!window.confirm('Retirer ce replay de la session ?')) return
    setWorkingId(recording.id)
    setError('')
    try {
      await archiveLiveRecording(recording.id)
      setRecordings((rows) => rows.filter((row) => row.id !== recording.id))
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Retrait du replay impossible.')
    } finally {
      setWorkingId(null)
    }
  }

  function saveDetails(event: FormEvent<HTMLFormElement>, recording: LiveRecording) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    void update(recording, {
      title: String(data.get('title') ?? '').trim(),
      description: String(data.get('description') ?? '').trim(),
    })
  }

  return (
    <section className="app-card live-recordings-panel" aria-label="Replays des cours">
      <header><Video size={19} aria-hidden="true" /><div><h2>Replays des cours</h2><p>Les enregistrements publiés apparaissent ici après leur traitement.</p></div></header>
      {error && <div className="form-error">{error}</div>}
      {loading && <p>Chargement des replays…</p>}
      {!loading && recordings.length === 0 && <p>Aucun replay disponible pour cette session.</p>}
      <div className="live-recordings-list">
        {recordings.map((recording) => {
          const publishable = recording.status === 'ready' && finishedDayIds?.has(recording.course_day_id)
          return <article key={recording.id} className="live-recording-card">
            <div><strong>{recording.title}</strong><small>{recording.status === 'ready' ? recording.is_published ? 'Publié' : 'Prêt à publier' : recording.status === 'failed' ? 'Traitement échoué' : 'En cours de traitement'}{recording.duration_seconds !== null && ` · ${durationLabel(recording.duration_seconds)}`}</small></div>
            {recording.content_url && <video controls preload="metadata" src={recording.content_url} />}
            {recording.description && <p>{recording.description}</p>}
            {canManage && <details className="live-recording-details">
              <summary>Modifier le titre et la description</summary>
              <form onSubmit={(event) => saveDetails(event, recording)}>
                <label>Titre<input name="title" defaultValue={recording.title} required minLength={2} maxLength={255} /></label>
                <label>Description<textarea name="description" defaultValue={recording.description ?? ''} maxLength={2000} rows={3} /></label>
                <button type="submit" className="secondary-button" disabled={workingId === recording.id}>Enregistrer</button>
              </form>
            </details>}
            <div className="live-recording-actions">
              {recording.content_url && (canManage || recording.download_allowed) && <a className="secondary-button" href={`${recording.content_url}&download=true`}><Download size={15} /> Télécharger</a>}
              {canManage && <>
                <button type="button" className="secondary-button" disabled={workingId === recording.id || (!recording.is_published && !publishable)} onClick={() => void update(recording, { is_published: !recording.is_published })}>{recording.is_published ? 'Retirer' : 'Publier'}</button>
                <label><input type="checkbox" checked={recording.download_allowed} disabled={workingId === recording.id || recording.status !== 'ready'} onChange={(event) => void update(recording, { download_allowed: event.target.checked })} /> Téléchargement étudiant</label>
                {recording.status === 'failed' && <button type="button" className="secondary-button" disabled={workingId === recording.id} onClick={() => void retry(recording)}>Relancer le traitement</button>}
                <button type="button" className="secondary-button" disabled={workingId === recording.id} onClick={() => void archive(recording)}>Retirer ce replay</button>
              </>}
            </div>
          </article>
        })}
      </div>
    </section>
  )
}
