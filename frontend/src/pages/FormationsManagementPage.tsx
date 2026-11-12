import { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  BookOpen,
  CalendarDays,
  GraduationCap,
  Plus,
  Search,
  Send,
  Users,
} from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import { NewFormationDialog } from '../components/NewFormationDialog'
import {
  ApiError,
  getOnboardingStatus,
  listFormations,
  updateFormation,
  type FormationSummary,
  type OnboardingStatus,
} from '../lib/api'
import { formatSchoolDate, formatSchoolMoney } from '../public/publicHelpers'
import '../formations-list.css'

const FORMAT_LABELS: Record<FormationSummary['format_type'], string> = {
  live: 'Live',
  ligne: 'En ligne',
  presentiel: 'Présentiel',
}
const STATUS_LABELS: Record<FormationSummary['status'], string> = {
  published: 'Publiée',
  draft: 'Brouillon',
  archived: 'Archivée',
}

function nextSessionCell(formation: FormationSummary) {
  if (formation.format_type === 'ligne') return { title: 'Accès continu', detail: 'Formation en ligne' }
  const session = formation.next_session
  if (!session) return { title: 'Aucune session à venir', detail: `${formation.session_count} session(s) au total` }
  return { title: session.label, detail: `${formatSchoolDate(session.start_date)} → ${formatSchoolDate(session.end_date)}` }
}

/** The school's formations: a short list to find one, and a button to create the next. */
export function FormationsManagementPage() {
  const { activeOrganization } = useTenant()
  const navigate = useNavigate()
  const [formations, setFormations] = useState<FormationSummary[]>([])
  const [setup, setSetup] = useState<OnboardingStatus | null>(null)
  const [creating, setCreating] = useState(false)
  const [query, setQuery] = useState('')
  const [format, setFormat] = useState('')
  const [status, setStatus] = useState('')
  const [category, setCategory] = useState('')
  const [publishingId, setPublishingId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function refresh() {
    try {
      const [items, setupStatus] = await Promise.all([listFormations(), getOnboardingStatus()])
      setFormations(items)
      setSetup(setupStatus)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de charger les formations.')
    }
  }

  useEffect(() => {
    void refresh()
  }, [activeOrganization?.id])

  async function publish(formation: FormationSummary) {
    setPublishingId(formation.id)
    setError('')
    setMessage('')
    try {
      const updated = await updateFormation(formation.id, { status: 'published' })
      setFormations((current) => current.map((item) => item.id === formation.id ? updated : item))
      setMessage('Formation publiée. Pour qu’elle apparaisse aux visiteurs, vérifiez aussi la publication du site public.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Publication impossible.')
    } finally {
      setPublishingId(null)
    }
  }

  const totals = useMemo(() => ({
    sessions: formations.reduce((sum, item) => sum + item.session_count, 0),
    students: formations.reduce((sum, item) => sum + item.student_count, 0),
    courses: formations.reduce((sum, item) => sum + item.course_count, 0),
    published: formations.filter((item) => item.status === 'published').length,
  }), [formations])

  const categories = useMemo(
    () => [...new Set(formations.map((item) => item.category.trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'fr')),
    [formations],
  )

  const rows = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase('fr-FR')
    return formations.filter((item) => {
      if (format && item.format_type !== format) return false
      if (status && item.status !== status) return false
      if (category && item.category.trim() !== category) return false
      return !needle || `${item.title} ${item.category} ${item.level}`.toLocaleLowerCase('fr-FR').includes(needle)
    })
  }, [formations, query, format, status, category])

  const setupBlockingStep = setup?.steps.find((step) => step.key !== 'formation' && !step.completed)
  const filtered = Boolean(query || format || status || category)

  return (
    <main className="app-page formations-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Pédagogie</span>
          <h1>Formations</h1>
          <p>Vos programmes, leurs sessions et leur page publique.</p>
        </div>
        <button
          className="primary-button"
          type="button"
          disabled={!setup || Boolean(setupBlockingStep)}
          onClick={() => setCreating(true)}
        >
          <Plus size={16} /> Nouvelle formation
        </button>
      </header>

      {message && <div className="form-success">{message} <Link to="/app/manage/site-public">Vérifier le site public</Link></div>}
      {error && <div className="form-error">{error}</div>}
      {setupBlockingStep && <div className="app-card formation-readiness"><strong>Création verrouillée</strong><p>Terminez d’abord l’étape « {setupBlockingStep.label} ».</p><Link className="secondary-button compact-action" to={setupBlockingStep.path}>Continuer cette étape <ArrowRight size={15} /></Link></div>}

      <section className="formation-metrics">
        <article><GraduationCap size={18} /><div><strong>{formations.length}</strong><span>{totals.published} publiée(s)</span></div></article>
        <article><CalendarDays size={18} /><div><strong>{totals.sessions}</strong><span>Sessions</span></div></article>
        <article><Users size={18} /><div><strong>{totals.students}</strong><span>Étudiants inscrits</span></div></article>
        <article><BookOpen size={18} /><div><strong>{totals.courses}</strong><span>Cours</span></div></article>
      </section>

      <section className="app-card formations-list">
        <div className="formations-list__toolbar">
          <label className="formations-list__search">
            <Search size={15} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Rechercher une formation" aria-label="Rechercher une formation" />
          </label>
          <select value={format} onChange={(event) => setFormat(event.target.value)} aria-label="Format">
            <option value="">Tous les formats</option>
            {Object.entries(FORMAT_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Statut">
            <option value="">Tous les statuts</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          {categories.length > 1 && (
            <select value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Catégorie">
              <option value="">Toutes les catégories</option>
              {categories.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          )}
        </div>

        <p className="formations-list__count">{rows.length} formation{rows.length > 1 ? 's' : ''}</p>

        {rows.length > 0 && (
          <div className="formations-list__table">
            <div className="formations-list__row is-head">
              <span>Formation</span><span>Prochaine session</span><span>Remplissage</span><span>Prix</span><span>Statut</span><span />
            </div>
            {rows.map((formation) => {
              const session = nextSessionCell(formation)
              const next = formation.next_session
              const fill = next && next.seat_capacity > 0 ? Math.min(100, Math.round((next.enrolled_count / next.seat_capacity) * 100)) : null
              return (
                <div className="formations-list__row" key={formation.id}>
                  <div className="formations-list__title">
                    <span className={`formations-list__format is-${formation.format_type}`}>{FORMAT_LABELS[formation.format_type]}</span>
                    <Link to={`/app/manage/formations/${formation.id}`}><strong>{formation.title}</strong></Link>
                    <small>{[formation.category, formation.level].filter(Boolean).join(' · ') || 'Sans catégorie'}</small>
                  </div>
                  <div>
                    <strong>{session.title}</strong>
                    <small>{session.detail}</small>
                  </div>
                  <div>
                    {next ? (
                      <>
                        <strong>{next.enrolled_count}{next.seat_capacity ? ` / ${next.seat_capacity}` : ''} inscrit{next.enrolled_count > 1 ? 's' : ''}</strong>
                        {fill !== null && <i className="formations-list__bar"><b style={{ width: `${fill}%` }} /></i>}
                      </>
                    ) : (
                      <><strong>{formation.student_count} étudiant{formation.student_count > 1 ? 's' : ''}</strong><small>au total</small></>
                    )}
                  </div>
                  <div>
                    <strong>{formation.price_cents > 0 ? formatSchoolMoney(formation.price_cents, formation.currency) : 'À définir'}</strong>
                    {formation.allow_installments && formation.price_cents > 0 && <small>en {formation.installment_count} fois possible</small>}
                  </div>
                  <div>
                    <span className={`formation-status ${formation.status}`}>{STATUS_LABELS[formation.status]}</span>
                    {formation.publication_issues.length > 0 && (
                      <small className="formations-list__issues" title={formation.publication_issues.join('\n')}>
                        {formation.publication_issues.length} point{formation.publication_issues.length > 1 ? 's' : ''} à compléter
                      </small>
                    )}
                  </div>
                  <div className="formations-list__actions">
                    {formation.status === 'draft' && formation.publication_issues.length === 0 && (
                      <button className="primary-button compact-action" type="button" disabled={publishingId !== null} onClick={() => void publish(formation)}>
                        <Send size={14} /> {publishingId === formation.id ? 'Publication…' : 'Publier'}
                      </button>
                    )}
                    <Link className="secondary-button compact-action" to={`/app/manage/formations/${formation.id}`}>
                      Ouvrir <ArrowRight size={14} />
                    </Link>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {rows.length === 0 && (
          <div className="formation-empty">
            <GraduationCap size={28} />
            <strong>{filtered ? 'Aucune formation ne correspond' : 'Aucune formation'}</strong>
            <p>{filtered ? 'Modifiez la recherche ou les filtres.' : 'Créez votre premier programme : le nom et le format suffisent pour commencer.'}</p>
            {!filtered && (
              <button className="primary-button" type="button" disabled={!setup || Boolean(setupBlockingStep)} onClick={() => setCreating(true)}>
                <Plus size={16} /> Nouvelle formation
              </button>
            )}
          </div>
        )}
      </section>

      <NewFormationDialog
        open={creating}
        existing={formations}
        onClose={() => setCreating(false)}
        onCreated={(formation) => {
          setCreating(false)
          navigate(`/app/manage/formations/${formation.id}?nouvelle=1`)
        }}
      />
    </main>
  )
}
