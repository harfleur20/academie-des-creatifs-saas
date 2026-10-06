import { useEffect, useState, type FormEvent } from 'react'
import { BookOpenCheck, GraduationCap, Save, ToggleLeft, ToggleRight } from 'lucide-react'
import {
  getSchoolCharter,
  saveSchoolCharter,
  type CharterAudience,
  type SchoolCharter,
} from '../onboarding/workspaceOnboardingApi'

function CharterEditor({ audience }: { audience: CharterAudience }) {
  const [charter, setCharter] = useState<SchoolCharter | null>(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    getSchoolCharter(audience)
      .then((next) => {
        if (!active) return
        setCharter(next)
        setTitle(next.title)
        setContent(next.content)
        setEnabled(next.is_enabled)
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : 'Impossible de charger la charte.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [audience])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setWorking(true)
    setError('')
    setMessage('')
    try {
      const saved = await saveSchoolCharter(audience, {
        title: title.trim(),
        content: content.trim(),
        is_enabled: enabled,
      })
      setCharter(saved)
      setMessage(saved.version !== charter?.version
        ? `Nouvelle version ${saved.version} publiée. Une nouvelle validation sera demandée.`
        : 'Paramètres de la charte enregistrés.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Enregistrement impossible.')
    } finally {
      setWorking(false)
    }
  }

  const label = audience === 'teacher' ? 'enseignants' : 'étudiants'

  return (
    <form className="app-card charter-admin-card" onSubmit={submit}>
      <div className="settings-section-heading">
        <div>
          <span className="section-label">{audience === 'teacher' ? 'Équipe pédagogique' : 'Apprenants'}</span>
          <h2>{audience === 'teacher' ? 'Charte enseignant' : 'Charte étudiant'}</h2>
          <p>Modifiez librement le texte ou désactivez la validation pour les {label}.</p>
        </div>
        {audience === 'teacher' ? <BookOpenCheck size={20} /> : <GraduationCap size={20} />}
      </div>

      {loading ? <div className="empty-row">Chargement…</div> : (
        <>
          <button
            type="button"
            className={`charter-toggle${enabled ? ' is-enabled' : ''}`}
            onClick={() => setEnabled((value) => !value)}
          >
            {enabled ? <ToggleRight size={26} /> : <ToggleLeft size={26} />}
            <span><strong>{enabled ? 'Validation obligatoire activée' : 'Validation obligatoire désactivée'}</strong><small>{enabled ? `Les ${label} doivent accepter la version active avant d’accéder à leur espace.` : `Les ${label} accèdent à leur espace sans validation de charte.`}</small></span>
          </button>

          <label>
            Titre
            <input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={180} required />
          </label>
          <label>
            Contenu de la charte
            <textarea value={content} onChange={(event) => setContent(event.target.value)} rows={16} maxLength={10000} required />
            <small>{content.length}/10000 caractères · toute modification du titre ou du texte crée une nouvelle version.</small>
          </label>

          <div className="charter-admin-meta">
            <span>Version actuelle <strong>{charter?.version || 1}</strong></span>
            <span>État <strong>{enabled ? 'Active' : 'Désactivée'}</strong></span>
          </div>

          {message && <div className="form-success">{message}</div>}
          {error && <div className="form-error">{error}</div>}
          <button className="primary-button" disabled={working || title.trim().length < 3 || content.trim().length < 20}>
            <Save size={16} /> {working ? 'Enregistrement…' : 'Enregistrer la charte'}
          </button>
        </>
      )}
    </form>
  )
}

export function CharterSettingsPage() {
  return (
    <main className="app-page charter-settings-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Règles de l’école</span>
          <h1>Chartes enseignant & étudiant</h1>
          <p>Chaque école décide du contenu, de l’activation et des versions à faire accepter.</p>
        </div>
      </header>
      <div className="charter-admin-grid">
        <CharterEditor audience="teacher" />
        <CharterEditor audience="student" />
      </div>
    </main>
  )
}
