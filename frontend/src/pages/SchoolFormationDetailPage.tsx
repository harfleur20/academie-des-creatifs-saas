import {
  ArrowLeft,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  Clock3,
  GraduationCap,
  Layers3,
  MapPin,
  ShoppingBag,
  Target,
  UserRoundCheck,
  Users,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getPublicSchoolFormation, type PublicFormationDetail, type PublicSession } from '../lib/api'
import { setSchoolCart } from '../public/schoolCart'
import { formatSchoolDate, formatSchoolMoney } from '../public/publicHelpers'
import { usePublicSchool } from '../public/SchoolPublicLayout'
import { SchoolFavoriteButton } from '../public/SchoolFavoriteButton'
import { PublicProgramSection } from '../components/PublicProgramSection'

const formatLabels: Record<PublicFormationDetail['format_type'], string> = {
  ligne: 'En ligne',
  live: 'Live',
  presentiel: 'Présentiel',
}

function contentLines(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.replace(/^[-•✓]\s*/, '').trim())
    .filter(Boolean)
}

export function SchoolFormationDetailPage() {
  const { schoolSlug = '', formationSlug = '' } = useParams()
  const { school, openCart } = usePublicSchool()
  const [formation, setFormation] = useState<PublicFormationDetail | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [toast, setToast] = useState('')
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    let active = true
    setFormation(null)
    setError('')
    getPublicSchoolFormation(schoolSlug, formationSlug)
      .then((data) => {
        if (!active) return
        setFormation(data)
        const available = data.sessions.filter((session) => session.can_purchase)
        setSessionId(available.length === 1 ? available[0].id : null)
      })
      .catch(() => {
        if (active) setError('Impossible de charger cette formation.')
      })
    return () => {
      active = false
    }
  }, [schoolSlug, formationSlug, retry])

  const selected = useMemo(
    () => formation?.sessions.find((session) => session.id === sessionId) ?? null,
    [formation, sessionId],
  )

  function add() {
    if (!formation) return
    const target = formation.format_type === 'ligne'
      ? formation.next_session
      : selected || (
        formation.sessions.filter((session) => session.can_purchase).length === 1
          ? formation.sessions.find((session) => session.can_purchase) ?? null
          : null
      )

    if (!target || !target.can_purchase) {
      setToast(
        formation.format_type === 'ligne'
          ? 'Cette formation n’est pas disponible à l’achat.'
          : 'Choisissez une session disponible avant de continuer.',
      )
      setTimeout(() => setToast(''), 3200)
      return
    }

    setSchoolCart(schoolSlug, {
      organization_id: school.organization_id,
      formation_id: formation.id,
      formation_slug: formation.slug,
      formation_title: formation.title,
      session_id: target.id,
      session_label: target.label,
      format_type: formation.format_type,
      price_cents: target.current_price_cents,
      currency: target.currency,
      cover_image_url: formation.cover_image_url,
    })
    openCart()
  }

  if (!formation) {
    return (
      <main className="school-section">
        <div className="school-empty">
          {error ? (
            <>
              {error}
              <button type="button" onClick={() => setRetry((value) => value + 1)}>Réessayer</button>
            </>
          ) : 'Chargement…'}
        </div>
      </main>
    )
  }

  const available = formation.sessions.filter((session) => session.can_purchase)
  const outcomes = contentLines(formation.objectives)
  const audience = contentLines(formation.prerequisites)
  const hasProgram = Boolean(formation.public_program.trim()) || formation.modules.length > 0
  const displayPrice = selected?.current_price_cents ?? formation.current_price_cents
  const displayBasePrice = selected?.price_cents ?? formation.price_cents
  const hasDiscount = selected
    ? selected.promotion_discount_cents > 0
    : formation.promotion_discount_cents > 0

  return (
    <main className="school-detail-page school-detail-page-v2">
      {toast && <div className="school-toast">{toast}</div>}

      <Link className="school-detail-back" to={`/school/${schoolSlug}/formations`}>
        <ArrowLeft size={14} /> Toutes les formations
      </Link>

      <section className="school-detail-hero school-detail-hero-v2">
        <div className="school-detail-intro school-detail-intro-v2">
          <span className="school-kicker">{formation.category} · {formation.level}</span>
          <div className="school-detail-title-line">
            <h1>{formation.title}</h1>
            <SchoolFavoriteButton slug={formation.slug} title={formation.title} />
          </div>
          <p>{formation.short_description || formation.description}</p>

          <div className="school-detail-meta school-detail-meta-v2">
            <span><Clock3 size={15} />{formation.training_hours ? `${formation.training_hours} h` : formation.format_type === 'ligne' ? 'À votre rythme' : 'Selon la session'}</span>
            <span><BookOpen size={15} />{formatLabels[formation.format_type]}</span>
            <span><GraduationCap size={15} />{formation.level}</span>
          </div>

          {formation.teacher_names.length > 0 && (
            <div className="school-detail-teacher-inline">
              <span className="school-detail-teacher-icon"><UserRoundCheck size={18} /></span>
              <span>
                <small>Équipe pédagogique</small>
                <strong>{formation.teacher_names.join(', ')}</strong>
              </span>
            </div>
          )}
        </div>

        <div className="school-detail-cover school-detail-cover-v2">
          {formation.cover_image_url
            ? <img src={formation.cover_image_url} alt={formation.title} />
            : <div className="school-detail-cover-placeholder"><Layers3 size={46} /></div>}
        </div>
      </section>

      <section className="school-detail-facts" aria-label="Informations clés de la formation">
        <article><Clock3 size={19} /><span><small>Durée</small><strong>{formation.training_hours ? `${formation.training_hours} heures` : formation.format_type === 'ligne' ? 'À votre rythme' : 'Selon la session'}</strong></span></article>
        <article><GraduationCap size={19} /><span><small>Niveau</small><strong>{formation.level || 'Tous niveaux'}</strong></span></article>
        <article><BookOpen size={19} /><span><small>Format</small><strong>{formatLabels[formation.format_type]}</strong></span></article>
        <article><Users size={19} /><span><small>Encadrement</small><strong>{formation.teacher_names.length > 0 ? `${formation.teacher_names.length} enseignant(s)` : 'Équipe de l’école'}</strong></span></article>
      </section>

      <section className="school-detail-layout school-detail-layout-v2">
        <article className="school-detail-content school-detail-content-v2">
          <section className="school-detail-section-card school-detail-presentation-section">
            <span className="school-detail-section-icon"><BookOpen size={19} /></span>
            <div>
              <span className="school-detail-section-kicker">La formation</span>
              <h2>Présentation</h2>
              <p>{formation.description}</p>
            </div>
          </section>

          {outcomes.length > 0 && (
            <section className="school-detail-section-block school-detail-outcomes-section">
              <div className="school-detail-section-heading-v2">
                <span className="school-detail-section-icon"><Target size={19} /></span>
                <div>
                  <span className="school-detail-section-kicker">Compétences visées</span>
                  <h2>Ce que vous saurez faire</h2>
                </div>
              </div>
              <ul className="school-learning-outcomes">
                {outcomes.map((item, index) => (
                  <li key={`${item}-${index}`}><CheckCircle2 size={16} /><span>{item}</span></li>
                ))}
              </ul>
            </section>
          )}

          {audience.length > 0 && (
            <section className="school-detail-section-block">
              <div className="school-detail-section-heading-v2">
                <span className="school-detail-section-icon"><Users size={19} /></span>
                <div>
                  <span className="school-detail-section-kicker">Pour bien démarrer</span>
                  <h2>À qui s’adresse cette formation ?</h2>
                </div>
              </div>
              <div className="school-detail-audience-grid">
                {audience.map((item, index) => (
                  <div key={`${item}-${index}`}><CheckCircle2 size={15} /><span>{item}</span></div>
                ))}
              </div>
            </section>
          )}

          {hasProgram && (
            <PublicProgramSection
              rawProgram={formation.public_program}
              fallbackModules={formation.modules}
            />
          )}

          {formation.teacher_names.length > 0 && (
            <section className="school-detail-section-block">
              <div className="school-detail-section-heading-v2">
                <span className="school-detail-section-icon"><UserRoundCheck size={19} /></span>
                <div>
                  <span className="school-detail-section-kicker">Accompagnement</span>
                  <h2>Équipe pédagogique</h2>
                </div>
              </div>
              <div className="school-detail-teacher-list">
                {formation.teacher_names.map((name) => (
                  <article key={name}>
                    <span>{name.trim().charAt(0).toUpperCase()}</span>
                    <div><strong>{name}</strong><small>Enseignant de la formation</small></div>
                  </article>
                ))}
              </div>
            </section>
          )}
        </article>

        <aside className="school-session-panel school-session-panel-v2">
          <div className="school-session-panel-price">
            <small>Tarif de la formation</small>
            {hasDiscount && <del>{formatSchoolMoney(displayBasePrice, formation.currency)}</del>}
            <strong>{formatSchoolMoney(displayPrice, formation.currency)}</strong>
            {formation.allow_installments && <span>Paiement possible jusqu’en {formation.installment_count} tranches.</span>}
          </div>

          <div className="school-session-panel-divider" />

          {formation.format_type === 'ligne' ? (
            <>
              <div className="school-session-panel-heading">
                <span className="school-session-panel-heading-icon"><BookOpen size={17} /></span>
                <div><strong>Formation en ligne</strong><small>Accès après confirmation du paiement</small></div>
              </div>
              <p>Progressez à votre rythme depuis votre espace étudiant.</p>
              <button className={`school-buy-button ${!formation.can_purchase ? 'is-locked' : ''}`} type="button" onClick={add}>
                <ShoppingBag size={16} />{formation.can_purchase ? 'Ajouter au panier' : 'Formation indisponible'}
              </button>
            </>
          ) : (
            <>
              <div className="school-session-panel-heading">
                <span className="school-session-panel-heading-icon"><CalendarDays size={17} /></span>
                <div><strong>Choisissez votre session</strong><small>{available.length} session(s) disponible(s)</small></div>
              </div>
              <div className="school-session-list">
                {formation.sessions.length > 0
                  ? formation.sessions.map((session) => (
                    <SessionChoice
                      key={session.id}
                      session={session}
                      selected={session.id === sessionId}
                      onSelect={() => session.can_purchase && setSessionId(session.id)}
                    />
                  ))
                  : <div className="school-no-session">Aucune session programmée.</div>}
              </div>
              <button className={`school-buy-button ${!formation.can_purchase ? 'is-locked' : ''}`} type="button" onClick={add}>
                <ShoppingBag size={16} />{formation.can_purchase ? 'Continuer avec cette session' : 'Pas de nouvelle session disponible'}
              </button>
              {available.length === 0 && <small>Achat verrouillé jusqu’à l’ouverture d’une nouvelle session.</small>}
            </>
          )}
        </aside>
      </section>
    </main>
  )
}

function SessionChoice({ session, selected, onSelect }: { session: PublicSession; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      className={`school-session-choice ${selected ? 'is-selected ' : ''}${!session.can_purchase ? 'is-disabled' : ''}`}
      onClick={onSelect}
    >
      <span className="school-session-radio" />
      <div>
        <strong>{session.label}</strong>
        <span><CalendarDays size={13} />{formatSchoolDate(session.start_date)} → {formatSchoolDate(session.end_date)}</span>
        {session.campus_label && <span><MapPin size={13} />{session.campus_label}</span>}
        {session.seats_remaining !== null && <span><Users size={13} />{session.seats_remaining} place(s) restante(s)</span>}
        {!session.can_purchase && <small>{session.unavailable_reason}</small>}
      </div>
      <div className="school-session-price">
        {session.promotion_discount_cents > 0 && <del>{formatSchoolMoney(session.price_cents, session.currency)}</del>}
        <strong>{formatSchoolMoney(session.current_price_cents, session.currency)}</strong>
        {session.can_purchase && <CheckCircle2 size={15} />}
      </div>
    </button>
  )
}
