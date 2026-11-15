import { useEffect, useState } from 'react'
import { ExternalLink, FileText } from 'lucide-react'
import {
  ApiError,
  listStudentResources,
  openTeacherResource,
  type AcademicResource,
} from '../lib/api'

export function StudentResourcesPage() {
  const [items, setItems] = useState<AcademicResource[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    listStudentResources()
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [])

  return (
    <main className="app-page academic-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Espace étudiant</span>
          <h1>Ressources</h1>
          <p>Supports publiés par vos professeurs pour vos formations.</p>
        </div>
      </header>
      {error && <div className="form-error">{error}</div>}
      <section className="academic-card-list">
        {items.map((item) => (
          <article className="app-card academic-item-card" key={item.id}>
            <div className="academic-item-icon"><FileText size={17} /></div>
            <div>
              <span className="section-label">{item.resource_type}</span>
              <h3>{item.title}</h3>
              <small>{item.formation_title} · {item.session_label} · Prof. {item.teacher_name || '-'}</small>
            </div>
            <button className="primary-button compact-action" type="button" onClick={() => void openTeacherResource(item.url).catch((cause) => setError(cause instanceof Error ? cause.message : 'Téléchargement impossible.'))}>
              <ExternalLink size={13} /> Ouvrir
            </button>
          </article>
        ))}
        {items.length === 0 && <div className="app-card formation-empty"><FileText size={26}/><strong>Aucune ressource publiée</strong><p>Les supports de vos professeurs apparaîtront ici.</p></div>}
      </section>
    </main>
  )
}
