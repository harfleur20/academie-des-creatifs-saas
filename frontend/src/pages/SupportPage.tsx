import { useState, type FormEvent } from 'react'
import {
  BadgeHelp,
  CheckCircle2,
  Clock3,
  CreditCard,
  LifeBuoy,
  MessageSquareText,
  Send,
  ShieldCheck,
  Wrench,
} from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { useTenant } from '../app/TenantContext'
import { ApiError, type WorkspaceSpace } from '../lib/api'
import {
  submitSupportRequest,
  type SupportCategory,
  type SupportPriority,
} from '../support/supportApi'

const categoryOptions: Array<{ value: SupportCategory; label: string }> = [
  { value: 'technical', label: 'Problème technique' },
  { value: 'billing', label: 'Facturation' },
  { value: 'account', label: 'Compte et accès' },
  { value: 'pedagogy', label: 'Pédagogie' },
  { value: 'other', label: 'Autre' },
]

const spaceLabels: Record<WorkspaceSpace, string> = {
  manage: 'Gestion de l’école',
  teacher: 'Espace enseignant',
  student: 'Espace étudiant',
}

export function SupportPage({ space }: { space: WorkspaceSpace }) {
  const { user } = useAuth()
  const { activeOrganization } = useTenant()
  const [category, setCategory] = useState<SupportCategory>('technical')
  const [priority, setPriority] = useState<SupportPriority>('normal')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [reference, setReference] = useState('')
  const [working, setWorking] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setReference('')
    setWorking(true)
    try {
      const result = await submitSupportRequest({
        category,
        priority,
        subject: subject.trim(),
        message: message.trim(),
        page_url: window.location.href,
      })
      setReference(result.reference)
      setSubject('')
      setMessage('')
      setPriority('normal')
      setCategory('technical')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible d’envoyer votre demande au support.')
    } finally {
      setWorking(false)
    }
  }

  return (
    <main className="app-page support-page">
      <header className="app-page-header support-page-header">
        <div>
          <span className="page-kicker">Centre d’aide</span>
          <h1>Support</h1>
          <p>Expliquez votre problème et transmettez directement les informations utiles à l’équipe support.</p>
        </div>
        <div className="support-header-badge"><LifeBuoy size={18} /> {spaceLabels[space]}</div>
      </header>

      {reference && (
        <section className="support-success-card">
          <CheckCircle2 size={22} />
          <div>
            <strong>Demande envoyée</strong>
            <p>Votre référence est <b>{reference}</b>. Conservez-la pour vos échanges avec le support.</p>
          </div>
        </section>
      )}

      {error && <div className="form-error">{error}</div>}

      <section className="support-quick-grid">
        <article className="app-card support-quick-card">
          <span><Wrench size={19} /></span>
          <strong>Technique</strong>
          <p>Connexion, affichage, upload, certificat, vidéo ou comportement anormal.</p>
        </article>
        <article className="app-card support-quick-card">
          <span><CreditCard size={19} /></span>
          <strong>Facturation</strong>
          <p>Abonnement, paiement, facture, accès à une fonctionnalité ou renouvellement.</p>
        </article>
        <article className="app-card support-quick-card">
          <span><ShieldCheck size={19} /></span>
          <strong>Compte & accès</strong>
          <p>Compte bloqué, rôle, permissions, mot de passe ou problème d’accès à une école.</p>
        </article>
      </section>

      <section className="support-layout">
        <form className="app-card support-form" onSubmit={submit}>
          <div className="settings-section-heading">
            <div>
              <span className="section-label">Nouvelle demande</span>
              <h2>Contacter le support</h2>
            </div>
            <MessageSquareText size={19} />
          </div>

          <div className="support-form-row">
            <label>
              Catégorie
              <select value={category} onChange={(event) => setCategory(event.target.value as SupportCategory)}>
                {categoryOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label>
              Priorité
              <select value={priority} onChange={(event) => setPriority(event.target.value as SupportPriority)}>
                <option value="normal">Normale</option>
                <option value="urgent">Urgente</option>
              </select>
            </label>
          </div>

          <label>
            Sujet
            <input
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              minLength={3}
              maxLength={120}
              placeholder="Ex. Le certificat ne se télécharge pas"
              required
            />
          </label>

          <label>
            Décrivez le problème
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              minLength={10}
              maxLength={5000}
              rows={8}
              placeholder="Expliquez ce que vous faisiez, ce qui s’est passé et le résultat attendu."
              required
            />
            <small>{message.length}/5000 caractères</small>
          </label>

          <div className="support-context-box">
            <BadgeHelp size={17} />
            <div>
              <strong>Contexte joint automatiquement</strong>
              <span>{user?.email || 'Compte'} · {activeOrganization?.name || 'École'} · page actuelle</span>
            </div>
          </div>

          <button className="primary-button" disabled={working || subject.trim().length < 3 || message.trim().length < 10}>
            <Send size={15} /> {working ? 'Envoi…' : 'Envoyer la demande'}
          </button>
        </form>

        <aside className="support-side-column">
          <section className="app-card support-info-card">
            <div className="settings-section-heading">
              <div>
                <span className="section-label">Votre compte</span>
                <h2>Informations transmises</h2>
              </div>
              <ShieldCheck size={18} />
            </div>
            <dl>
              <div><dt>Nom</dt><dd>{user?.full_name || '-'}</dd></div>
              <div><dt>Email</dt><dd>{user?.email || '-'}</dd></div>
              <div><dt>École</dt><dd>{activeOrganization?.name || '-'}</dd></div>
              <div><dt>Espace</dt><dd>{spaceLabels[space]}</dd></div>
            </dl>
            <p className="support-info-note"><Clock3 size={15} /> La réponse du support est envoyée à l’adresse e-mail de votre compte.</p>
          </section>

          <section className="app-card support-faq-card">
            <div className="settings-section-heading">
              <div>
                <span className="section-label">Aide rapide</span>
                <h2>Questions fréquentes</h2>
              </div>
              <BadgeHelp size={18} />
            </div>
            <details>
              <summary>Je n’arrive plus à me connecter</summary>
              <p>Utilisez « Mot de passe oublié ? » sur l’écran de connexion. Si le problème persiste, choisissez « Compte et accès » dans le formulaire.</p>
            </details>
            <details>
              <summary>Un paiement est passé mais l’accès n’est pas actif</summary>
              <p>Choisissez « Facturation » et indiquez la formation, la date du paiement et toute référence disponible.</p>
            </details>
            <details>
              <summary>Une page ne fonctionne pas correctement</summary>
              <p>Décrivez les étapes exactes qui déclenchent le problème. La page depuis laquelle vous contactez le support est jointe automatiquement.</p>
            </details>
          </section>
        </aside>
      </section>
    </main>
  )
}
