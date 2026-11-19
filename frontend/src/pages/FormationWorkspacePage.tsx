import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from 'react'
import {
  Archive,
  ArrowLeft,
  BookOpen,
  CalendarPlus,
  CheckCircle2,
  Film,
  GraduationCap,
  ImagePlus,
  Pencil,
  Plus,
  Save,
  Send,
  Sparkles,
  UserPlus,
  Users,
  X,
} from 'lucide-react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  ApiError,
  assignSessionTeacher,
  createFormationSession,
  getFormation,
  listMembers,
  uploadFormationVideo,
  updateFormation,
  updateFormationEnrollment,
  updateFormationSession,
  uploadSchoolAsset,
  type FormationDetail,
  type Member,
} from '../lib/api'
import { CharacterCounter } from '../components/CharacterCounter'
import { characterCount, exceedsCharacterLimit, FORMATION_CHARACTER_LIMITS } from '../lib/characterLimits'
import { PublicProgramField } from '../components/PublicProgramField'
import { formatSchoolDate, formatSchoolMoney } from '../public/publicHelpers'
import { toast } from '../ui/toast'
import { publishedWithoutSale } from '../lib/formationStatus'
import '../formation-workspace.css'

type Tab = 'presentation' | 'tarif' | 'sessions' | 'contenu'
type Session = FormationDetail['sessions'][number]

const today = () => new Date().toISOString().slice(0, 10)

function readVideoDuration(file: File): Promise<number> {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video')
    const url = URL.createObjectURL(file)
    let timeout = 0
    const cleanup = () => {
      window.clearTimeout(timeout)
      URL.revokeObjectURL(url)
      video.removeAttribute('src')
      video.load()
    }
    video.preload = 'metadata'
    video.addEventListener('loadedmetadata', () => {
      const duration = video.duration
      cleanup()
      if (!Number.isFinite(duration)) {
        reject(new Error('Impossible de lire la durée de cette vidéo.'))
        return
      }
      resolve(duration)
    }, { once: true })
    video.addEventListener('error', () => {
      cleanup()
      reject(new Error('Impossible de lire cette vidéo MP4.'))
    }, { once: true })
    timeout = window.setTimeout(() => {
      cleanup()
      reject(new Error('La lecture des informations de la vidéo a expiré.'))
    }, 10_000)
    video.src = url
  })
}

// As on the mother site: a session is to come, running or over by its dates; its sale is shown alongside.
function sessionStateLabel(session: { status: string; start_date: string; end_date: string }) {
  if (session.status === 'cancelled') return 'Annulée'
  if (session.status === 'completed' || session.end_date < today()) return 'Terminée'
  const stage = session.start_date <= today() ? 'En cours' : 'À venir'
  return `${stage} · ${session.status === 'open' ? 'inscriptions ouvertes' : 'inscriptions fermées'}`
}

const FORMAT_KICKER: Record<FormationDetail['format_type'], string> = {
  live: 'Formation en live', presentiel: 'Formation en présentiel', ligne: 'Formation en ligne',
}

/** The session to open first: the one running or coming next, else the latest. */
function defaultSession(formation: FormationDetail): Session | undefined {
  const next = formation.next_session ? formation.sessions.find((item) => item.id === formation.next_session?.id) : undefined
  if (next) return next
  return [...formation.sessions].sort((a, b) => b.start_date.localeCompare(a.start_date))[0]
}

export function FormationWorkspacePage() {
  const params = useParams()
  const formationId = Number(params.formationId)
  const [searchParams, setSearchParams] = useSearchParams()
  const [formation, setFormation] = useState<FormationDetail | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [description, setDescription] = useState('')
  const [shortDescription, setShortDescription] = useState('')
  const [objectives, setObjectives] = useState('')
  const [prerequisites, setPrerequisites] = useState('')
  const [coverUrl, setCoverUrl] = useState('')
  const [presentationVideoUrl, setPresentationVideoUrl] = useState('')
  const [price, setPrice] = useState('')
  const [allowInstallments, setAllowInstallments] = useState(false)
  const [installmentCount, setInstallmentCount] = useState('3')
  const [depositEnabled, setDepositEnabled] = useState(false)
  const [depositPercent, setDepositPercent] = useState('37.5')
  const [publicProgram, setPublicProgram] = useState('')
  const [creatingSession, setCreatingSession] = useState(false)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const justCreated = searchParams.get('nouvelle') === '1'
  const longestObjective = Math.max(0, ...objectives.split(/\r\n|\n|\r/).map(characterCount))
  const presentationHasCharacterLimitIssues =
    exceedsCharacterLimit(shortDescription, FORMATION_CHARACTER_LIMITS.shortDescription)
    || exceedsCharacterLimit(description, FORMATION_CHARACTER_LIMITS.description)
    || exceedsCharacterLimit(objectives, FORMATION_CHARACTER_LIMITS.objectives)
    || longestObjective > FORMATION_CHARACTER_LIMITS.objective
    || exceedsCharacterLimit(prerequisites, FORMATION_CHARACTER_LIMITS.prerequisites)

  async function refresh() {
    try {
      const [detail, team] = await Promise.all([getFormation(formationId), listMembers()])
      setFormation(detail)
      setDescription(detail.description)
      setShortDescription(detail.short_description)
      setObjectives(detail.objectives)
      setPrerequisites(detail.prerequisites)
      setCoverUrl(detail.cover_image_url || '')
      setPresentationVideoUrl(detail.presentation_video_url || '')
      setPrice(detail.price_cents ? String(detail.currency === 'XAF' ? detail.price_cents : detail.price_cents / 100) : '')
      setAllowInstallments(detail.allow_installments)
      setInstallmentCount(String(detail.installment_count))
      setDepositEnabled(detail.reservation_deposit_enabled)
      setDepositPercent(String(detail.reservation_deposit_percent))
      setPublicProgram(detail.public_program)
      setMembers(team)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Impossible de charger la formation.')
    }
  }

  useEffect(() => {
    if (Number.isInteger(formationId)) void refresh()
  }, [formationId])

  const teachers = useMemo(
    () => members.filter((item) => item.status === 'active' && item.role === 'teacher'),
    [members],
  )

  const online = formation?.format_type === 'ligne'
  const sessionTab: Tab = online ? 'contenu' : 'sessions'
  const requestedTab = searchParams.get('onglet') as Tab | null
  const tab: Tab = requestedTab && ['presentation', 'tarif', sessionTab].includes(requestedTab)
    ? requestedTab
    : formation && formation.status === 'published' && !justCreated ? sessionTab : 'presentation'
  const selectedSession = formation
    ? formation.sessions.find((item) => item.id === Number(searchParams.get('session'))) ?? defaultSession(formation)
    : undefined

  function go(changes: { onglet?: Tab; session?: number | null }) {
    const next = new URLSearchParams(searchParams)
    next.delete('nouvelle')
    if (changes.onglet) next.set('onglet', changes.onglet)
    if (changes.session === null) next.delete('session')
    else if (changes.session) next.set('session', String(changes.session))
    setSearchParams(next, { replace: true })
  }

  async function publishFormation() {
    if (!formation) return
    setWorking(true)
    setError('')
    setMessage('')
    try {
      await updateFormation(formation.id, { status: 'published' })
      setFormation(await getFormation(formation.id))
      setMessage('Formation publiée. Vérifiez aussi que le site public de l’école est publié.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Publication impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function archiveFormation() {
    if (!formation) return
    // As on the mother site: warn about future sessions that already have students.
    const upcoming = formation.sessions.filter((session) => session.status !== 'cancelled' && session.status !== 'completed'
      && session.start_date > today() && session.enrollments.some((item) => item.status === 'active'))
    const warning = upcoming.length
      ? `Ces sessions à venir ont déjà des inscrits : ${upcoming.map((session) => session.label).join(', ')}. Leurs étudiants gardent leur accès, mais la formation disparaîtra du catalogue.

`
      : ''
    if (!window.confirm(`${warning}Archiver « ${formation.title} » ? L’historique des sessions, des inscriptions et des paiements est conservé.`)) return
    setWorking(true)
    setError('')
    setMessage('')
    try {
      await updateFormation(formation.id, { status: 'archived' })
      setFormation(await getFormation(formation.id))
      setMessage('Formation archivée : elle n’apparaît plus dans le catalogue.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Archivage impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function save(event: FormEvent, success: string, includePresentation = true) {
    event.preventDefault()
    if (!formation) return
    if (includePresentation && presentationHasCharacterLimitIssues) {
      setError('Raccourcissez les champs signalés avant d’enregistrer la présentation.')
      return
    }
    setWorking(true)
    setError('')
    setMessage('')
    try {
      await updateFormation(formation.id, {
        ...(includePresentation ? {
          description: description.trim(),
          short_description: shortDescription.trim(),
          objectives: objectives.trim(),
          prerequisites: prerequisites.trim(),
          cover_image_url: coverUrl || null,
          presentation_video_url: presentationVideoUrl || null,
        } : {}),
        price_cents: price ? Math.round(Number(price) * (formation.currency === 'XAF' ? 1 : 100)) : 0,
        allow_installments: allowInstallments,
        installment_count: Math.min(12, Math.max(2, Number(installmentCount) || 2)),
        reservation_deposit_enabled: depositEnabled,
        reservation_deposit_percent: Math.min(99, Math.max(1, Number(depositPercent) || 37.5)),
      })
      setFormation(await getFormation(formation.id))
      setMessage(success)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Enregistrement impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function uploadCover(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setWorking(true)
    setError('')
    try {
      const asset = await uploadSchoolAsset(file)
      setCoverUrl(asset.public_url)
      setMessage('Photo importée. Enregistrez la présentation pour l’utiliser.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Import de la photo impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function uploadPresentationVideo(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.mp4')) {
      setError('Choisissez une vidéo au format MP4.')
      return
    }
    if (file.size > 50 * 1024 * 1024) {
      setError('La vidéo de présentation ne doit pas dépasser 50 Mo.')
      return
    }

    setWorking(true)
    setError('')
    setMessage('')
    try {
      const duration = await readVideoDuration(file)
      if (duration > 3 * 60) {
        setError('La vidéo de présentation ne doit pas dépasser 3 minutes.')
        return
      }
      const asset = await uploadFormationVideo(file)
      setPresentationVideoUrl(asset.public_url)
      setMessage('Vidéo importée. Enregistrez la présentation pour l’afficher sur la fiche publique.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : 'Import de la vidéo impossible.')
    } finally {
      setWorking(false)
    }
  }

  if (!formation && !error) return <div className="page-state">Chargement de la formation…</div>
  if (!formation) return <main className="app-page"><div className="form-error">{error}</div></main>

  const next = formation.next_session
  const issues = formation.publication_issues
  const noSale = publishedWithoutSale(formation)

  return (
    <main className="app-page formation-workspace-page">
      <Link className="admin-back-link" to="/app/manage/formations">
        <ArrowLeft size={15} /> Toutes les formations
      </Link>

      <header className="app-page-header">
        <div>
          <span className="page-kicker">{FORMAT_KICKER[formation.format_type]}</span>
          <h1>{formation.title}</h1>
          <p>{formation.short_description || formation.description || 'Aucune description.'}</p>
        </div>
        <div className="formation-workspace-actions">
          <span className={`formation-status ${formation.status}`}>{formation.status === 'published' ? 'Publiée' : formation.status === 'archived' ? 'Archivée' : 'Brouillon'}</span>
          {formation.status === 'draft' && <button className="primary-button" type="button" disabled={working || issues.length > 0} onClick={() => void publishFormation()}><Send size={15} /> {working ? 'Publication…' : 'Publier la formation'}</button>}
          {formation.status !== 'archived' && <button className="secondary-button" type="button" disabled={working} onClick={() => void archiveFormation()}><Archive size={15} /> Archiver</button>}
        </div>
      </header>

      <section className="formation-facts" aria-label="En bref">
        <div>
          <span>{online ? 'Accès' : 'Prochaine session'}</span>
          <strong>{online ? 'Accès continu' : next ? next.label : 'Aucune session à venir'}</strong>
          {!online && next && <small>{formatSchoolDate(next.start_date)} → {formatSchoolDate(next.end_date)}</small>}
        </div>
        <div>
          <span>Inscrits</span>
          <strong>{next ? `${next.enrolled_count}${next.seat_capacity ? ` / ${next.seat_capacity}` : ''}` : formation.student_count}</strong>
          <small>{next ? 'sur la prochaine session' : 'au total'}</small>
        </div>
        <div>
          <span>Prix</span>
          <strong>{formation.price_cents > 0 ? formatSchoolMoney(formation.price_cents, formation.currency) : 'À définir'}</strong>
          {formation.allow_installments && formation.price_cents > 0 && <small>en {formation.installment_count} fois possible</small>}
        </div>
        <div className={issues.length ? 'is-warning' : 'is-ok'}>
          <span>Publication</span>
          <strong>{noSale ? 'Publiée · aucune session en vente' : issues.length ? `${issues.length} point${issues.length > 1 ? 's' : ''} à compléter` : 'Prête'}</strong>
          <small>{noSale ? 'ouvrez une session pour vendre' : issues.length ? 'voir ci-dessous' : formation.status === 'published' ? 'visible au catalogue' : 'vous pouvez publier'}</small>
        </div>
      </section>

      {justCreated && (
        <div className="billing-alert neutral formation-created">
          <Sparkles size={19} />
          <div>
            <strong>Formation créée en brouillon</strong>
            <span>
              Complétez la présentation et le tarif
              {online ? ', puis ajoutez le contenu' : ', puis créez une première session et ouvrez ses inscriptions'}. Vous pourrez ensuite la publier.
            </span>
          </div>
        </div>
      )}
      {error && <div className="form-error">{error}</div>}
      {message && <div className="form-success">{message} {message.startsWith('Formation publiée') && <Link to="/app/manage/identity?tab=site">Vérifier le site public</Link>}</div>}

      {noSale && <section className="app-card formation-readiness"><strong>Aucune session en vente</strong><p>La formation reste visible sur votre site, mais personne ne peut l’acheter : ouvrez les inscriptions d’une session pour reprendre la vente.</p></section>}
      {issues.length > 0 && !noSale && <section className="app-card formation-readiness"><strong>À compléter avant publication ou ouverture des inscriptions</strong>{formation.status === 'published' && <p>Les informations manquantes peuvent masquer la fiche publique ou bloquer les inscriptions.</p>}<ul>{issues.map((issue) => <li key={issue}>{issue}</li>)}</ul></section>}

      <nav className="formation-tabs" role="tablist" aria-label="Sections de la formation">
        <button type="button" role="tab" aria-selected={tab === 'presentation'} className={tab === 'presentation' ? 'is-active' : ''} onClick={() => go({ onglet: 'presentation' })}>Présentation</button>
        <button type="button" role="tab" aria-selected={tab === 'tarif'} className={tab === 'tarif' ? 'is-active' : ''} onClick={() => go({ onglet: 'tarif' })}>Tarif et paiement</button>
        <button type="button" role="tab" aria-selected={tab === sessionTab} className={tab === sessionTab ? 'is-active' : ''} onClick={() => go({ onglet: sessionTab })}>
          {online ? 'Contenu' : <>Sessions <span>{formation.sessions.length}</span></>}
        </button>
      </nav>

      {tab === 'presentation' && (
        <form className="app-card formation-presentation" onSubmit={(event) => void save(event, 'Présentation enregistrée.')}>
          <div className="settings-section-heading"><div><span className="section-label">Page publique</span><h2>Présentation de la formation</h2><p>Ce que voient les visiteurs sur la fiche de la formation.</p></div><ImagePlus size={20} /></div>
          <div className="formation-cover-field">
            <span>Photo de couverture</span>
            <div className="formation-cover-field__body">
              {coverUrl ? <img src={coverUrl} alt="Couverture de la formation" /> : <div className="formation-cover-field__empty"><ImagePlus size={22} /></div>}
              <div className="formation-cover-field__actions">
                <label className="secondary-button compact-action">
                  <ImagePlus size={16} /> {coverUrl ? 'Changer la photo' : 'Choisir une photo'}
                  <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={(event) => void uploadCover(event)} disabled={working} hidden />
                </label>
                <small>Image horizontale recommandée · JPG, PNG ou WebP</small>
              </div>
            </div>
          </div>
          <div className="formation-video-field">
            <span>Vidéo de présentation (facultative)</span>
            {presentationVideoUrl && (
              <video
                className="formation-video-field__preview"
                src={presentationVideoUrl}
                poster={coverUrl || undefined}
                controls
                playsInline
                preload="metadata"
              />
            )}
            {!presentationVideoUrl && <div className="formation-video-field__empty"><Film size={19} /><span>Ajoutez une vidéo pour présenter cette formation.</span></div>}
            <div className="formation-video-field__actions">
              <label className="secondary-button compact-action">
                <Film size={14} /> {presentationVideoUrl ? 'Changer la vidéo' : 'Choisir une vidéo'}
                <input type="file" accept=".mp4,video/mp4" onChange={(event) => void uploadPresentationVideo(event)} disabled={working} hidden />
              </label>
              {presentationVideoUrl && (
                <button className="secondary-button compact-action" type="button" disabled={working} onClick={() => setPresentationVideoUrl('')}>
                  Retirer la vidéo
                </button>
              )}
            </div>
            <small>Format accepté et recommandé : MP4 (H.264), horizontal en 16:9. Durée maximale : 3 minutes · Taille maximale : 50 Mo. Sans vidéo, la photo de couverture reste affichée.</small>
          </div>
          <label>Résumé court<textarea value={shortDescription} onChange={(event) => setShortDescription(event.target.value)} rows={3} placeholder="Texte court affiché dans l’introduction et sur les cartes du catalogue." /><CharacterCounter value={shortDescription} limit={FORMATION_CHARACTER_LIMITS.shortDescription} /></label>
          <label>Description générale<textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={5} placeholder="Présentez la formation, sa promesse et son approche pédagogique." /><CharacterCounter value={description} limit={FORMATION_CHARACTER_LIMITS.description} /></label>
          <label>À la fin de cette formation, l’apprenant sera capable de…<textarea value={objectives} onChange={(event) => setObjectives(event.target.value)} rows={5} placeholder={'Concevoir une application complète\nAutomatiser des tâches métier\nCréer une interface professionnelle'} /><small>Un acquis par ligne pour un affichage clair sur le site public.</small><CharacterCounter value={objectives} limit={FORMATION_CHARACTER_LIMITS.objectives} /><CharacterCounter count={longestObjective} limit={FORMATION_CHARACTER_LIMITS.objective} label="Objectif le plus long" /></label>
          <label>À qui s’adresse cette formation ? / Prérequis<textarea value={prerequisites} onChange={(event) => setPrerequisites(event.target.value)} rows={4} placeholder="Décrivez le public cible, le niveau attendu et les éventuels prérequis." /><CharacterCounter value={prerequisites} limit={FORMATION_CHARACTER_LIMITS.prerequisites} /></label>
          <PublicProgramField
            formationId={formation.id}
            value={publicProgram}
            disabled={working}
            onSaved={(detail) => {
              setFormation(detail)
              setPublicProgram(detail.public_program)
              setMessage('Programme public enregistré. L’accordéon de la fiche publique est à jour.')
            }}
          />
          <button className="primary-button" type="submit" disabled={working || presentationHasCharacterLimitIssues}><Save size={15} /> Enregistrer la présentation</button>
        </form>
      )}

      {tab === 'tarif' && (
        <form className="app-card formation-presentation" onSubmit={(event) => void save(event, 'Tarif enregistré.', false)}>
          <div className="settings-section-heading"><div><span className="section-label">Vente</span><h2>Tarif et paiement</h2><p>Le prix affiché sur la fiche, et comment vos étudiants peuvent le régler.</p></div></div>
          <label>Prix ({formation.currency})<input type="number" min={formation.currency === 'XAF' ? '1' : '0.01'} step={formation.currency === 'XAF' ? '1' : '0.01'} value={price} onChange={(event) => setPrice(event.target.value)} placeholder={formation.currency === 'XAF' ? 'Ex. 150000' : 'Ex. 250.00'} /></label>
          <fieldset className="formation-payment-options">
            <legend>Modalités de paiement</legend>
            {online && <small>Une formation en ligne se règle en une fois et reste accessible à vie.</small>}
            {!online && <label className="formation-payment-toggle"><input type="checkbox" checked={allowInstallments} onChange={(event) => setAllowInstallments(event.target.checked)} /> Autoriser le paiement en plusieurs fois</label>}
            {!online && allowInstallments && <label>Nombre maximal de paiements<input type="number" min={2} max={12} step={1} value={installmentCount} onChange={(event) => setInstallmentCount(event.target.value)} /></label>}
            {!online && allowInstallments && formation.currency === 'XAF' && <small>Possible à partir de 70 000 FCFA, avec au moins 35 000 FCFA par paiement : le prix peut donc réduire ce nombre.</small>}
            {allowInstallments && !online && <small>Les paiements sont espacés d’au moins 7 jours et le dernier tombe 5 jours avant la fin de la session : une session d’un mois peut se payer en 3 fois dans le mois.</small>}
            {formation.format_type === 'live' && <>
              <label className="formation-payment-toggle"><input type="checkbox" checked={depositEnabled} onChange={(event) => setDepositEnabled(event.target.checked)} /> Réserver une place avec un acompte</label>
              {depositEnabled && <label>Acompte (% du prix)<input type="number" min={1} max={99} step={0.5} value={depositPercent} onChange={(event) => setDepositPercent(event.target.value)} /></label>}
              {depositEnabled && <small>L’acompte non remboursable réserve la place quand la session commence dans plus de 10 jours. Le solde est dû 10 jours avant le début : sans lui, l’accès est suspendu mais la place reste gardée. Les montants en FCFA sont arrondis à 500 FCFA.</small>}
            </>}
          </fieldset>
          <button className="primary-button" type="submit" disabled={working}><Save size={15} /> Enregistrer le tarif</button>
        </form>
      )}

      {tab === 'sessions' && !online && (
        <div className="formation-sessions">
          <aside className="formation-sessions__list" aria-label="Sessions">
            <button type="button" className="primary-button full" onClick={() => setCreatingSession(true)}>
              <CalendarPlus size={15} /> Nouvelle session
            </button>
            {[...formation.sessions].sort((a, b) => b.start_date.localeCompare(a.start_date)).map((session) => {
              const active = session.enrollments.filter((item) => item.status !== 'cancelled').length
              const fill = session.seat_capacity > 0 ? Math.min(100, Math.round((active / session.seat_capacity) * 100)) : null
              return (
                <button
                  key={session.id}
                  type="button"
                  className={`formation-sessions__item${!creatingSession && selectedSession?.id === session.id ? ' is-active' : ''}`}
                  onClick={() => { setCreatingSession(false); go({ session: session.id }) }}
                >
                  <small>{sessionStateLabel(session)}</small>
                  <strong>{session.label}</strong>
                  <span>{formatSchoolDate(session.start_date)} → {formatSchoolDate(session.end_date)}</span>
                  <span>{active}{session.seat_capacity ? ` / ${session.seat_capacity}` : ''} inscrit{active > 1 ? 's' : ''} · {session.courses.length} cours</span>
                  {fill !== null && <i className="formations-list__bar"><b style={{ width: `${fill}%` }} /></i>}
                </button>
              )
            })}
            {formation.sessions.length === 0 && <p className="muted-note">Aucune session pour l’instant.</p>}
          </aside>
          <div className="formation-sessions__detail">
            {creatingSession || !selectedSession ? (
              <NewSessionForm
                formation={formation}
                onCancel={formation.sessions.length ? () => setCreatingSession(false) : undefined}
                onCreated={(detail, created) => {
                  setFormation(detail)
                  setCreatingSession(false)
                  if (created) go({ session: created.id })
                  setMessage(created?.status === 'open' ? 'Session créée, inscriptions ouvertes.' : 'Session créée.')
                }}
              />
            ) : (
              <SessionWorkspace key={selectedSession.id} formation={formation} session={selectedSession} teachers={teachers} onChange={setFormation} />
            )}
          </div>
        </div>
      )}

      {tab === 'contenu' && online && (
        formation.sessions[0]
          ? <SessionWorkspace formation={formation} session={formation.sessions[0]} teachers={teachers} onChange={setFormation} />
          : <div className="app-card formation-empty"><BookOpen size={26} /><strong>Contenu en préparation</strong><p>Actualisez la page pour charger le contenu pédagogique.</p></div>
      )}
    </main>
  )
}

function NewSessionForm({
  formation,
  onCancel,
  onCreated,
}: {
  formation: FormationDetail
  onCancel?: () => void
  onCreated: (detail: FormationDetail, created: Session | undefined) => void
}) {
  // Reuse by default the content of the latest session that has some.
  const sources = useMemo(
    () => [...formation.sessions].filter((item) => item.courses.length > 0).sort((a, b) => b.start_date.localeCompare(a.start_date)),
    [formation.sessions],
  )
  const [label, setLabel] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [capacity, setCapacity] = useState('')
  const [campus, setCampus] = useState('')
  const [source, setSource] = useState(sources[0] ? String(sources[0].id) : '')
  const [withTeachers, setWithTeachers] = useState(true)
  const contentIssues = formation.content_issues ?? []
  const [openNow, setOpenNow] = useState(contentIssues.length === 0)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setWorking(true)
    setError('')
    try {
      const before = new Set(formation.sessions.map((item) => item.id))
      const detail = await createFormationSession(formation.id, {
        label: label.trim(),
        start_date: startDate,
        end_date: endDate,
        campus_label: campus.trim() || null,
        seat_capacity: Number(capacity),
        copy_content_from_session_id: source ? Number(source) : null,
        copy_teachers: withTeachers,
        status: openNow && contentIssues.length === 0 ? 'open' : 'planned',
      })
      onCreated(detail, detail.sessions.find((item) => !before.has(item.id)))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Création de session impossible.')
    } finally {
      setWorking(false)
    }
  }

  const chosen = sources.find((item) => String(item.id) === source)
  return (
    <form className="app-card session-new-card" onSubmit={submit}>
      <div className="settings-section-heading">
        <div>
          <span className="section-label">Nouvelle session</span>
          <h2>Ouvrir une session</h2>
          <p>Une session regroupe des étudiants sur des dates données, avec ses professeurs et son contenu.</p>
        </div>
        {onCancel && <button type="button" className="public-program-icon-button" onClick={onCancel} aria-label="Fermer"><X size={18} /></button>}
      </div>
      <div className="session-new-grid">
        <label>Nom de la session<input value={label} onChange={(event) => setLabel(event.target.value)} required minLength={2} placeholder="Cohorte octobre 2026" /></label>
        <label>Début<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} required /></label>
        <label>Fin<input type="date" value={endDate} min={startDate || undefined} onChange={(event) => setEndDate(event.target.value)} required /></label>
        <label>Places<input type="number" min={1} value={capacity} onChange={(event) => setCapacity(event.target.value)} required /></label>
        {formation.format_type === 'presentiel' && <label>Lieu<input value={campus} onChange={(event) => setCampus(event.target.value)} required placeholder="Bonamoussadi" /></label>}
      </div>
      <label className="formation-payment-toggle">
        <input type="checkbox" checked={openNow && contentIssues.length === 0} disabled={contentIssues.length > 0} onChange={(event) => setOpenNow(event.target.checked)} />
        Ouvrir les inscriptions dès maintenant
      </label>
      {contentIssues.length > 0 && <small>Pour ouvrir les inscriptions, complétez d’abord la formation : {contentIssues.join(' ')}</small>}
      {sources.length > 0 && (
        <fieldset className="session-new-copy">
          <legend>Contenu</legend>
          <label>
            Reprendre le contenu de
            <select value={source} onChange={(event) => setSource(event.target.value)}>
              <option value="">Aucune session : partir de zéro</option>
              {sources.map((item) => <option key={item.id} value={item.id}>{item.label} · {item.courses.length} cours</option>)}
            </select>
          </label>
          {chosen && (
            <>
              <label className="formation-payment-toggle"><input type="checkbox" checked={withTeachers} onChange={(event) => setWithTeachers(event.target.checked)} /> Reprendre aussi ses professeurs ({chosen.teachers.length})</label>
              <small>Les cours, modules et leçons sont recopiés tels quels. Les quiz, devoirs et ressources le sont en brouillon, leurs dates décalées comme la session : vérifiez-les puis publiez-les. Le planning des séances reste à faire.</small>
            </>
          )}
        </fieldset>
      )}
      {error && <div className="form-error">{error}</div>}
      <div className="session-new-actions">
        {onCancel && <button type="button" className="secondary-button" onClick={onCancel} disabled={working}>Annuler</button>}
        <button className="primary-button" disabled={working}><Plus size={15} /> {working ? 'Création…' : 'Créer la session'}</button>
      </div>
    </form>
  )
}

function SessionWorkspace({
  formation,
  session,
  teachers,
  onChange,
}: {
  formation: FormationDetail
  session: Session
  teachers: Member[]
  onChange: (value: FormationDetail) => void
}) {
  const [teacherId, setTeacherId] = useState('')
  const [accessStartDate, setAccessStartDate] = useState(session.start_date)
  const [accessEndDate, setAccessEndDate] = useState(session.end_date)
  const [editLabel, setEditLabel] = useState(session.label)
  const [editCapacity, setEditCapacity] = useState(String(session.seat_capacity))
  const [editCampus, setEditCampus] = useState(session.campus_label ?? '')
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setAccessStartDate(session.start_date)
    setAccessEndDate(session.end_date)
  }, [session.start_date, session.end_date])

  useEffect(() => {
    setEditLabel(session.label)
    setEditCapacity(String(session.seat_capacity))
    setEditCampus(session.campus_label ?? '')
  }, [session.label, session.seat_capacity, session.campus_label])

  const online = formation.format_type === 'ligne'
  const assignedTeacherIds = new Set(session.teachers.map((item) => item.teacher_id))
  const invalidAccessPeriod = !accessStartDate || !accessEndDate || accessEndDate < accessStartDate
  const isOnsite = formation.format_type === 'presentiel'
  const sessionUnchanged = editLabel.trim() === session.label
    && accessStartDate === session.start_date
    && accessEndDate === session.end_date
    && Number(editCapacity) === session.seat_capacity
    && (!isOnsite || editCampus.trim() === (session.campus_label ?? ''))
  const enrollments = session.enrollments.filter((item) => item.status !== 'cancelled')
  const toValidate = enrollments.filter((item) => item.status === 'active')
  const ended = session.status === 'completed' || session.end_date < today()
  const publishedCourseCount = session.courses.filter((course) => course.status === 'published').length
  const draftCourseCount = session.courses.filter((course) => course.status === 'draft').length
  const archivedCourseCount = session.courses.filter((course) => course.status === 'archived').length

  function saveSession(event: FormEvent) {
    event.preventDefault()
    void run(() => updateFormationSession(formation.id, session.id, {
      label: editLabel.trim(),
      start_date: accessStartDate,
      end_date: accessEndDate,
      seat_capacity: Number(editCapacity),
      ...(isOnsite ? { campus_label: editCampus.trim() } : {}),
    }), 'Session enregistrée.')
  }

  async function run(action: () => Promise<FormationDetail>, done?: string) {
    setWorking(true)
    setError('')
    try {
      onChange(await action())
      if (done) toast.success(done)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Action impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function validateAll() {
    if (!window.confirm(`Valider le parcours des ${toValidate.length} étudiants encore en cours ? Le certificat s’ouvre pour ceux qui ont rempli les acquis.`)) return
    setWorking(true)
    setError('')
    try {
      let detail: FormationDetail | null = null
      for (const enrollment of toValidate) {
        detail = await updateFormationEnrollment(formation.id, session.id, enrollment.id, 'completed')
      }
      if (detail) onChange(detail)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Validation impossible.')
    } finally {
      setWorking(false)
    }
  }

  return (
    <article className="app-card session-workspace-card">
      <header className="session-workspace-heading">
        <div>
          <span className="section-label">{online ? 'Contenu pédagogique' : sessionStateLabel(session)}</span>
          <h2>{online ? formation.title : session.label}</h2>
          <p>
            {formatSchoolDate(session.start_date)} → {formatSchoolDate(session.end_date)}
            {session.seat_capacity > 0 ? ` · ${enrollments.length}/${session.seat_capacity} places` : ''}
            {isOnsite && session.campus_label ? ` · ${session.campus_label}` : ''}
          </p>
          {session.program_frozen_at && <small className="session-program-status is-frozen">Programme figé le {new Date(session.program_frozen_at).toLocaleDateString(activeSchoolLocale())} : les badges se mesurent sur ce programme et les contenus qui le composent ne changent plus de structure.</small>}
          {!session.program_frozen_at && (session.program_missing?.length ?? 0) > 0 && <small className="session-program-status">Programme à compléter avant le début : {session.program_missing?.join(' ; ')}. Il sera figé au démarrage de la session.</small>}
        </div>
        <div className="session-workspace-stats">
          <span title="Professeurs"><GraduationCap size={14} /> {session.teachers.length}</span>
          <span title="Étudiants inscrits"><Users size={14} /> {session.enrollments.filter((item) => item.status === 'active').length}</span>
          <span title="Cours"><BookOpen size={14} /> {session.courses.length}</span>
        </div>
        {!online && (session.status === 'planned' || session.status === 'open') && <button
          className="secondary-button"
          type="button"
          disabled={working || (session.status === 'planned' && (formation.content_issues ?? formation.publication_issues).length > 0)}
          title={session.status === 'planned' && (formation.content_issues ?? []).length > 0 ? 'Complétez d’abord la formation : ' + (formation.content_issues ?? []).join(' ') : undefined}
          onClick={() => void run(
            () => updateFormationSession(formation.id, session.id, { status: session.status === 'open' ? 'planned' : 'open' }),
            session.status === 'open' ? 'Inscriptions fermées.' : 'Inscriptions ouvertes.',
          )}
        >{session.status === 'open' ? 'Fermer les inscriptions' : 'Ouvrir les inscriptions'}</button>}
      </header>

      {error && <div className="form-error">{error}</div>}

      {!online && <details className="session-edit-panel">
        <summary><Pencil size={14} /> Modifier la session</summary>
        <form className="session-create-grid" onSubmit={saveSession}>
          <label>Nom de session<input value={editLabel} onChange={(e) => setEditLabel(e.target.value)} required minLength={2} /></label>
          <label>Début<input type="date" value={accessStartDate} onChange={(e) => setAccessStartDate(e.target.value)} required /></label>
          <label>Fin<input type="date" value={accessEndDate} min={accessStartDate || undefined} onChange={(e) => setAccessEndDate(e.target.value)} required /></label>
          <label>Places<input type="number" min={1} value={editCapacity} onChange={(e) => setEditCapacity(e.target.value)} required /></label>
          {isOnsite && <label>Lieu<input value={editCampus} onChange={(e) => setEditCampus(e.target.value)} required placeholder="Bonamoussadi" /></label>}
          <button className="secondary-button" disabled={working || invalidAccessPeriod || sessionUnchanged}><Save size={14} /> Enregistrer</button>
        </form>
      </details>}


      <section className="session-block">
        <h3>Professeurs</h3>
        <div className="inline-management-form">
          <select value={teacherId} onChange={(e) => setTeacherId(e.target.value)}>
            <option value="">Choisir un professeur</option>
            {teachers.filter((item) => !assignedTeacherIds.has(item.user_id)).map((item) => (
              <option key={item.id} value={item.user_id}>{item.user.full_name}</option>
            ))}
          </select>
          <button
            className="secondary-button"
            type="button"
            disabled={!teacherId || working}
            onClick={() => void run(() => assignSessionTeacher(
              formation.id, session.id, Number(teacherId), session.teachers.length === 0 ? 'principal' : 'intervenant',
            ), 'Professeur affecté.').then(() => setTeacherId(''))}
          >
            <UserPlus size={14} /> Affecter
          </button>
        </div>
        <div className="compact-person-list">
          {session.teachers.map((item) => (
            <span key={item.id}><strong>{item.teacher_name}</strong><small>{item.role === 'principal' ? 'Principal' : 'Intervenant'}</small></span>
          ))}
          {session.teachers.length === 0 && <small>Aucun professeur affecté.</small>}
        </div>
      </section>

      <section className="session-block">
        <div className="session-block__heading">
          <h3>Étudiants <span>{enrollments.length}</span></h3>
          {!online && toValidate.length > 0 && ended && (
            <button type="button" className="primary-button compact-action" disabled={working} onClick={() => void validateAll()}>
              <CheckCircle2 size={14} /> Valider les {toValidate.length} parcours
            </button>
          )}
        </div>
        <p className="muted-note">
          {online
            ? 'Les étudiants accèdent automatiquement à la formation après leur achat sur le site public.'
            : ended
              ? 'La session est terminée : validez les parcours pour ouvrir le certificat à ceux qui ont rempli les acquis.'
              : `Les étudiants sont inscrits après leur achat. La validation des parcours se fait à la fin de la session, le ${formatSchoolDate(session.end_date)}.`}
        </p>
        {enrollments.length > 0 ? (
          <div className="session-students">
            {enrollments.map((item) => (
              <div className="session-students__row" key={item.id}>
                <span><strong>{item.student_name}</strong><small>{item.student_email}</small></span>
                <span className={`session-students__status is-${item.status}`}>{item.status === 'completed' ? 'Parcours validé' : 'En cours'}</span>
                <span>
                  {!online && ended && item.status === 'active' && (
                    <button
                      className="enrollment-complete-button"
                      type="button"
                      disabled={working || session.status === 'cancelled'}
                      onClick={() => void run(() => updateFormationEnrollment(formation.id, session.id, item.id, 'completed'), 'Parcours validé.')}
                    >Valider le parcours</button>
                  )}
                </span>
              </div>
            ))}
          </div>
        ) : <p className="muted-note">{online ? 'Aucun achat confirmé pour cette formation.' : 'Aucun achat confirmé pour cette session.'}</p>}
        <Link className="secondary-button compact-action" to="/app/manage/students">Voir la gestion des étudiants</Link>
      </section>

      <section className="session-course-section">
        <div className="settings-section-heading">
          <div>
            <span className="section-label">Contenu pédagogique</span>
            <h3>Programme pédagogique</h3>
          </div>
        </div>

        <div className="session-program-summary">
          <div className="session-program-summary__intro">
            <BookOpen size={20} aria-hidden="true" />
            <div>
              <strong>{session.courses.length ? 'Suivi du programme' : 'Programme à construire'}</strong>
              <p>
                {session.teachers.length
                  ? 'Les professeurs affectés à cette session créent et publient les cours depuis leur espace Mes cours.'
                  : 'Affectez d’abord un professeur à cette session. Il pourra ensuite construire le programme depuis son espace Mes cours.'}
              </p>
            </div>
          </div>

          {session.courses.length > 0 && (
            <div className="session-program-summary__stats" aria-label="État du programme">
              <span><strong>{session.courses.length}</strong> cours</span>
              <span><strong>{publishedCourseCount}</strong> {publishedCourseCount === 1 ? 'cours publié' : 'cours publiés'}</span>
              <span><strong>{draftCourseCount}</strong> cours en brouillon</span>
              {archivedCourseCount > 0 && <span><strong>{archivedCourseCount}</strong> {archivedCourseCount === 1 ? 'cours archivé' : 'cours archivés'}</span>}
            </div>
          )}
        </div>

        {session.courses.length > 0 ? (
          <div className="session-program-course-list">
            {session.courses.map((course) => {
              const lessonCount = course.chapters.reduce((total, chapter) => total + chapter.lessons.length, 0)
              const publishedLessonCount = course.chapters.reduce(
                (total, chapter) => total + chapter.lessons.filter((lesson) => lesson.publication_status === 'published').length,
                0,
              )
              const statusLabel = course.status === 'published' ? 'Publié' : course.status === 'archived' ? 'Archivé' : 'Brouillon'
              return (
                <article className="session-program-course" key={course.id}>
                  <div className="session-program-course__main">
                    <strong>{course.title}</strong>
                    <small>{course.teacher_name || 'Professeur non affecté'}</small>
                  </div>
                  <div className="session-program-course__meta">
                    <span>{course.chapters.length} {course.chapters.length === 1 ? 'module' : 'modules'}</span>
                    <span>{publishedLessonCount}/{lessonCount} leçons publiées</span>
                    <span className={`session-program-course__status is-${course.status}`}>{statusLabel}</span>
                  </div>
                </article>
              )
            })}
          </div>
        ) : (
          <div className="session-program-empty">
            <strong>Aucun cours créé pour le moment</strong>
            <span>Le programme apparaîtra ici dès qu’un professeur l’aura commencé.</span>
          </div>
        )}
      </section>
    </article>
  )
}
