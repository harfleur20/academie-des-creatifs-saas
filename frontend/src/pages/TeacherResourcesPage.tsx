import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react'
import { ExternalLink, FileUp, Link2, Plus } from 'lucide-react'
import {
  ApiError,
  createTeacherResource,
  getTeacherWorkspace,
  listTeacherResources,
  uploadAssignmentAsset,
  type AcademicResource,
  type TeacherWorkspace,
} from '../lib/api'

export function TeacherResourcesPage() {
  const [workspace, setWorkspace] = useState<TeacherWorkspace | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [items, setItems] = useState<AcademicResource[]>([])
  const [title, setTitle] = useState('')
  const [url, setUrl] = useState('')
  const [type, setType] = useState<AcademicResource['resource_type']>('link')
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getTeacherWorkspace()
      .then((data) => {
        setWorkspace(data)
        setSessionId(data.sessions[0]?.session_id ?? null)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [])

  useEffect(() => {
    if (!sessionId) return
    listTeacherResources(sessionId)
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [sessionId])

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setWorking(true)
    setError('')
    try {
      const asset = await uploadAssignmentAsset(file)
      setUrl(asset.public_url)
      if (file.type.startsWith('image/')) setType('image')
      else if (file.type.startsWith('video/')) setType('video')
      else if (file.type === 'application/pdf') setType('pdf')
      else setType('file')
      if (!title) setTitle(file.name)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function create(event: FormEvent) {
    event.preventDefault()
    if (!sessionId) return
    setWorking(true)
    setError('')
    try {
      const created = await createTeacherResource(sessionId, {
        title: title.trim(),
        resource_type: type,
        url: url.trim(),
        publish_now: true,
      })
      setItems((current) => [created, ...current])
      setTitle('')
      setUrl('')
      setType('link')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Publication impossible.')
    } finally {
      setWorking(false)
    }
  }

  return (
    <main className="app-page academic-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Espace professeur</span>
          <h1>Ressources</h1>
          <p>Publiez les supports utiles aux étudiants de vos sessions.</p>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}

      <label className="academic-session-select">
        Session
        <select value={sessionId ?? ''} onChange={(event) => setSessionId(Number(event.target.value))}>
          {workspace?.sessions.map((session) => (
            <option key={session.session_id} value={session.session_id}>
              {session.formation_title} · {session.session_label}
            </option>
          ))}
        </select>
      </label>

      <section className="academic-two-column">
        <form className="app-card academic-form-card" onSubmit={create}>
          <span className="section-label">Nouvelle ressource</span>
          <h2>Publier un support</h2>
          <label>
            Titre
            <input value={title} onChange={(event) => setTitle(event.target.value)} required minLength={2} />
          </label>
          <label>
            Type
            <select value={type} onChange={(event) => setType(event.target.value as AcademicResource['resource_type'])}>
              <option value="link">Lien</option>
              <option value="pdf">PDF</option>
              <option value="image">Image</option>
              <option value="video">Vidéo</option>
              <option value="file">Fichier</option>
            </select>
          </label>
          <label>
            URL
            <input value={url} onChange={(event) => setUrl(event.target.value)} required placeholder="https://..." />
          </label>
          <label className="secondary-button academic-upload">
            <FileUp size={14} /> Uploader un fichier
            <input type="file" onChange={(event) => void upload(event)} />
          </label>
          <button className="primary-button" disabled={working || !url.trim()}>
            <Plus size={14} /> {working ? 'Publication…' : 'Publier'}
          </button>
        </form>

        <section className="academic-card-list">
          {items.map((item) => (
            <article className="app-card academic-item-card" key={item.id}>
              <div className="academic-item-icon"><Link2 size={17} /></div>
              <div>
                <span className="section-label">{item.resource_type}</span>
                <h3>{item.title}</h3>
                <small>Prof. {item.teacher_name || '—'}</small>
              </div>
              <a className="secondary-button compact-action" href={item.url} target="_blank" rel="noreferrer">
                <ExternalLink size={13} /> Ouvrir
              </a>
            </article>
          ))}
          {items.length === 0 && <div className="app-card formation-empty"><Link2 size={26}/><strong>Aucune ressource</strong><p>Publiez le premier support de cette session.</p></div>}
        </section>
      </section>
    </main>
  )
}
