import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  BadgePercent,
  CalendarDays,
  Clock3,
  Infinity as InfinityIcon,
  Plus,
  ShieldCheck,
  TicketPercent,
  UsersRound,
} from 'lucide-react'
import {
  ApiError,
  createCoupon,
  createPromotion,
  listCoupons,
  listFormations,
  listPromotions,
  setCouponActive,
  setPromotionActive,
  type Coupon,
  type FormationSummary,
  type Promotion,
} from '../lib/api'

const PROMO_NAME = '%Promo'

type PromotionState = 'live' | 'scheduled' | 'ended' | 'paused' | 'exhausted'

function localDateInput(value = new Date()) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function addDays(value: string, days: number) {
  const date = new Date(`${value}T12:00:00`)
  date.setDate(date.getDate() + days)
  return localDateInput(date)
}

function startOfDayIso(value: string) {
  return new Date(`${value}T00:00:00`).toISOString()
}

function endOfDayIso(value: string) {
  return new Date(`${value}T23:59:59.999`).toISOString()
}

function formatDate(value: string | null) {
  if (!value) return 'Sans date'
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value))
}

function formatMoney(cents: number, currency = 'XAF') {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(cents / 100)
}

function promotionState(promotion: Promotion): PromotionState {
  const now = Date.now()
  if (!promotion.is_active) return 'paused'
  if (promotion.max_uses !== null && promotion.uses_count >= promotion.max_uses) return 'exhausted'
  if (promotion.starts_at && new Date(promotion.starts_at).getTime() > now) return 'scheduled'
  if (promotion.ends_at && new Date(promotion.ends_at).getTime() < now) return 'ended'
  return 'live'
}

function stateLabel(state: PromotionState) {
  if (state === 'live') return 'En cours'
  if (state === 'scheduled') return 'Programmée'
  if (state === 'ended') return 'Terminée'
  if (state === 'exhausted') return 'Épuisée'
  return 'Désactivée'
}

function rangesOverlap(
  leftStart: number,
  leftEnd: number,
  rightStart: number,
  rightEnd: number,
) {
  return leftStart <= rightEnd && rightStart <= leftEnd
}

export function PromotionsPage() {
  const initialStart = useMemo(() => localDateInput(), [])
  const [formations, setFormations] = useState<FormationSummary[]>([])
  const [promos, setPromos] = useState<Promotion[]>([])
  const [coupons, setCoupons] = useState<Coupon[]>([])
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)

  const [promoFormation, setPromoFormation] = useState('')
  const [promoType, setPromoType] = useState<'percentage' | 'fixed'>('percentage')
  const [promoValue, setPromoValue] = useState('20')
  const [promoStartsOn, setPromoStartsOn] = useState(initialStart)
  const [promoEndsOn, setPromoEndsOn] = useState(addDays(initialStart, 7))
  const [promoMaxUses, setPromoMaxUses] = useState('')

  const [code, setCode] = useState('')
  const [couponType, setCouponType] = useState<'percentage' | 'fixed'>('percentage')
  const [couponValue, setCouponValue] = useState('10')
  const [couponFormation, setCouponFormation] = useState('')

  async function load() {
    const [formationRows, promotionRows, couponRows] = await Promise.all([
      listFormations(),
      listPromotions(),
      listCoupons(),
    ])
    setFormations(formationRows)
    setPromos(promotionRows)
    setCoupons(couponRows)
  }

  useEffect(() => {
    void load().catch((err) => {
      setError(err instanceof ApiError ? err.message : 'Chargement impossible.')
    })
  }, [])

  const selectedFormation = useMemo(
    () => formations.find((formation) => formation.id === Number(promoFormation)) ?? null,
    [formations, promoFormation],
  )

  const normalizedValue = Number(promoValue)
  const promoStartMs = promoStartsOn ? new Date(`${promoStartsOn}T00:00:00`).getTime() : Number.NaN
  const promoEndMs = promoEndsOn ? new Date(`${promoEndsOn}T23:59:59.999`).getTime() : Number.NaN

  const overlappingPromotion = useMemo(() => {
    if (!promoFormation || !Number.isFinite(promoStartMs) || !Number.isFinite(promoEndMs)) return null
    return promos.find((promotion) => {
      if (!promotion.is_active || promotion.formation_id !== Number(promoFormation) || promotion.session_id !== null) return false
      const existingStart = promotion.starts_at ? new Date(promotion.starts_at).getTime() : Number.NEGATIVE_INFINITY
      const existingEnd = promotion.ends_at ? new Date(promotion.ends_at).getTime() : Number.POSITIVE_INFINITY
      return rangesOverlap(promoStartMs, promoEndMs, existingStart, existingEnd)
    }) ?? null
  }, [promoEndMs, promoFormation, promoStartMs, promos])

  const promotionValidation = useMemo(() => {
    if (!promoFormation) return 'Choisissez la formation concernée.'
    if (!promoStartsOn || !promoEndsOn) return 'La date de début et la date de fin sont obligatoires.'
    if (promoEndMs < promoStartMs) return 'La date de fin doit être postérieure ou égale à la date de début.'
    if (!Number.isFinite(normalizedValue) || normalizedValue <= 0) return 'La remise doit être supérieure à zéro.'
    if (promoType === 'percentage' && normalizedValue > 100) return 'Une remise ne peut pas dépasser 100 %.'
    if (promoMaxUses && (!Number.isInteger(Number(promoMaxUses)) || Number(promoMaxUses) <= 0)) return 'La limite d’utilisation doit être un nombre entier positif.'
    if (overlappingPromotion) return `Une promotion couvre déjà cette formation sur cette période (${formatDate(overlappingPromotion.starts_at)} → ${formatDate(overlappingPromotion.ends_at)}).`
    return ''
  }, [normalizedValue, overlappingPromotion, promoEndMs, promoEndsOn, promoFormation, promoMaxUses, promoStartMs, promoStartsOn, promoType])

  const discountedPreview = useMemo(() => {
    if (!selectedFormation || !Number.isFinite(normalizedValue) || normalizedValue <= 0) return null
    const discountCents = promoType === 'percentage'
      ? Math.round(selectedFormation.price_cents * normalizedValue / 100)
      : Math.round(normalizedValue * 100)
    return Math.max(0, selectedFormation.price_cents - discountCents)
  }, [normalizedValue, promoType, selectedFormation])

  async function addPromo(event: FormEvent) {
    event.preventDefault()
    if (promotionValidation) {
      setError(promotionValidation)
      return
    }
    setWorking(true)
    setError('')
    try {
      await createPromotion({
        name: PROMO_NAME,
        formation_id: Number(promoFormation),
        session_id: null,
        discount_type: promoType,
        discount_value: promoType === 'percentage'
          ? Math.round(normalizedValue)
          : Math.round(normalizedValue * 100),
        starts_at: startOfDayIso(promoStartsOn),
        ends_at: endOfDayIso(promoEndsOn),
        max_uses: promoMaxUses ? Number(promoMaxUses) : null,
        is_active: true,
      })
      setPromoValue(promoType === 'percentage' ? '20' : '5000')
      setPromoMaxUses('')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Création impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function addCoupon(event: FormEvent) {
    event.preventDefault()
    setWorking(true)
    setError('')
    try {
      const rawCouponValue = Number(couponValue)
      await createCoupon({
        code: code.toUpperCase(),
        name: `Code ${code.toUpperCase()}`,
        discount_type: couponType,
        discount_value: couponType === 'fixed' ? Math.round(rawCouponValue * 100) : Math.round(rawCouponValue),
        valid_from: null,
        valid_until: null,
        max_uses: null,
        max_uses_per_customer: 1,
        minimum_order_cents: 0,
        eligible_formation_ids: couponFormation ? [Number(couponFormation)] : [],
        eligible_session_ids: [],
        allow_on_promotions: false,
        is_active: true,
      })
      setCode('')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Création impossible.')
    } finally {
      setWorking(false)
    }
  }

  function hasActiveTwin(promotion: Promotion) {
    return promos.some((candidate) => (
      candidate.id !== promotion.id
      && candidate.is_active
      && candidate.formation_id === promotion.formation_id
      && candidate.session_id === promotion.session_id
      && candidate.discount_type === promotion.discount_type
      && candidate.discount_value === promotion.discount_value
      && candidate.starts_at === promotion.starts_at
      && candidate.ends_at === promotion.ends_at
    ))
  }

  return (
    <main className="app-page promo-admin-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Marketing</span>
          <h1>Promotions & codes promo</h1>
          <p>Programmez les remises dans le temps. Le prix appliqué est figé dans la commande au moment de l’achat.</p>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}

      <section className="promo-admin-grid promo-admin-grid--strong">
        <form className="app-card promo-create-card promo-create-card--direct" onSubmit={addPromo}>
          <div className="promo-card-heading">
            <span className="promo-card-icon"><BadgePercent size={21} /></span>
            <div>
              <span>Remise automatique</span>
              <h2>Promotion directe</h2>
              <p>La remise s’applique automatiquement au prix affiché pendant la période choisie.</p>
            </div>
          </div>

          <div className="promo-policy-strip">
            <ShieldCheck size={18} />
            <span><strong>{PROMO_NAME}</strong> · Une seule promotion directe peut couvrir une même formation sur une période donnée.</span>
          </div>

          <label>
            Formation
            <select value={promoFormation} onChange={(event) => setPromoFormation(event.target.value)} required>
              <option value="">Choisir une formation</option>
              {formations.map((formation) => (
                <option key={formation.id} value={formation.id}>{formation.title}</option>
              ))}
            </select>
          </label>

          <div className="academic-form-row promo-discount-row">
            <label>
              Type de remise
              <select
                value={promoType}
                onChange={(event) => {
                  const next = event.target.value as typeof promoType
                  setPromoType(next)
                  setPromoValue(next === 'percentage' ? '20' : '5000')
                }}
              >
                <option value="percentage">Pourcentage (%)</option>
                <option value="fixed">Montant fixe</option>
              </select>
            </label>
            <label>
              {promoType === 'percentage' ? 'Réduction (%)' : `Réduction (${selectedFormation?.currency || 'devise'})`}
              <input
                type="number"
                min="1"
                max={promoType === 'percentage' ? '100' : undefined}
                step="1"
                value={promoValue}
                onChange={(event) => setPromoValue(event.target.value)}
                required
              />
            </label>
          </div>

          <div className="academic-form-row promo-date-row">
            <label>
              <span className="promo-label-with-icon"><CalendarDays size={15} /> Début</span>
              <input type="date" value={promoStartsOn} onChange={(event) => setPromoStartsOn(event.target.value)} required />
            </label>
            <label>
              <span className="promo-label-with-icon"><Clock3 size={15} /> Fin</span>
              <input type="date" min={promoStartsOn} value={promoEndsOn} onChange={(event) => setPromoEndsOn(event.target.value)} required />
            </label>
          </div>

          <label>
            Limite d’utilisations <span className="promo-optional">facultatif</span>
            <input
              type="number"
              min="1"
              step="1"
              value={promoMaxUses}
              onChange={(event) => setPromoMaxUses(event.target.value)}
              placeholder="Illimité"
            />
          </label>

          <div className="promo-preview-card">
            <div>
              <span>Aperçu</span>
              <strong>{selectedFormation?.title || 'Choisissez une formation'}</strong>
            </div>
            {selectedFormation && discountedPreview !== null && (
              <div className="promo-preview-price">
                <small>{formatMoney(selectedFormation.price_cents, selectedFormation.currency)}</small>
                <strong>{formatMoney(discountedPreview, selectedFormation.currency)}</strong>
              </div>
            )}
            <div className="promo-preview-meta">
              <span><CalendarDays size={14} /> {promoStartsOn ? formatDate(startOfDayIso(promoStartsOn)) : '—'} → {promoEndsOn ? formatDate(endOfDayIso(promoEndsOn)) : '—'}</span>
              <span>{promoMaxUses ? <UsersRound size={14} /> : <InfinityIcon size={14} />} {promoMaxUses ? `${promoMaxUses} utilisations maximum` : 'Utilisations illimitées'}</span>
            </div>
          </div>

          {promotionValidation && <div className="promo-inline-warning">{promotionValidation}</div>}

          <button className="primary-button promo-create-button" disabled={working || Boolean(promotionValidation)}>
            <Plus size={16} /> Programmer la promotion
          </button>
        </form>

        <form className="app-card promo-create-card" onSubmit={addCoupon}>
          <div className="promo-card-heading">
            <span className="promo-card-icon"><TicketPercent size={21} /></span>
            <div>
              <span>Code à saisir</span>
              <h2>Code promo</h2>
              <p>Réduction volontaire saisie par l’étudiant au moment de l’achat.</p>
            </div>
          </div>
          <label>
            Code
            <input value={code} onChange={(event) => setCode(event.target.value.replace(/[^A-Za-z0-9_-]/g, '').toUpperCase())} placeholder="RENTREE26" required />
          </label>
          <label>
            Formation <span className="promo-optional">facultatif</span>
            <select value={couponFormation} onChange={(event) => setCouponFormation(event.target.value)}>
              <option value="">Toutes les formations</option>
              {formations.map((formation) => <option key={formation.id} value={formation.id}>{formation.title}</option>)}
            </select>
          </label>
          <div className="academic-form-row">
            <label>
              Type
              <select
                value={couponType}
                onChange={(event) => {
                  const next = event.target.value as typeof couponType
                  setCouponType(next)
                  setCouponValue(next === 'percentage' ? '10' : '5000')
                }}
              >
                <option value="percentage">Pourcentage</option>
                <option value="fixed">Montant fixe</option>
              </select>
            </label>
            <label>
              Valeur
              <input type="number" min="1" max={couponType === 'percentage' ? '100' : undefined} value={couponValue} onChange={(event) => setCouponValue(event.target.value)} />
            </label>
          </div>
          <div className="promo-policy-strip is-muted">
            <ShieldCheck size={17} />
            <span>Par défaut : 1 utilisation par client et non cumulable avec une promotion directe.</span>
          </div>
          <button className="primary-button" disabled={working || !code}><Plus size={14} /> Créer le code</button>
        </form>
      </section>

      <section className="app-card promo-list-card promo-list-card--detailed">
        <div className="promo-list-heading">
          <div>
            <span className="page-kicker">Automatiques</span>
            <h2>Promotions directes</h2>
          </div>
          <strong>{promos.length}</strong>
        </div>
        {promos.map((promotion) => {
          const state = promotionState(promotion)
          const formation = formations.find((item) => item.id === promotion.formation_id)
          const canReactivate = state !== 'ended' && state !== 'exhausted' && !hasActiveTwin(promotion)
          return (
            <div className="promo-admin-row promo-admin-row--detailed" key={promotion.id}>
              <div className="promo-row-main">
                <span className={`promo-state promo-state--${state}`}>{stateLabel(state)}</span>
                <div>
                  <strong>{PROMO_NAME} · {promotion.discount_type === 'percentage' ? `-${promotion.discount_value}%` : `-${formatMoney(promotion.discount_value, formation?.currency)}`}</strong>
                  <small>{formation?.title || 'Formation supprimée'}</small>
                </div>
              </div>
              <div className="promo-row-details">
                <span><CalendarDays size={14} /> {formatDate(promotion.starts_at)} → {formatDate(promotion.ends_at)}</span>
                <span>{promotion.max_uses === null ? <InfinityIcon size={14} /> : <UsersRound size={14} />} {promotion.max_uses === null ? `${promotion.uses_count} utilisation(s) · illimité` : `${promotion.uses_count}/${promotion.max_uses} utilisation(s)`}</span>
              </div>
              <button
                className={`member-status ${promotion.is_active ? 'active' : 'suspended'}`}
                disabled={working || (!promotion.is_active && !canReactivate)}
                title={!promotion.is_active && !canReactivate ? 'Cette promotion ne peut plus être réactivée.' : undefined}
                onClick={async () => {
                  setWorking(true)
                  setError('')
                  try {
                    await setPromotionActive(promotion.id, !promotion.is_active)
                    await load()
                  } catch (err) {
                    setError(err instanceof ApiError ? err.message : 'Modification impossible.')
                  } finally {
                    setWorking(false)
                  }
                }}
                type="button"
              >
                {promotion.is_active ? 'Désactiver' : 'Réactiver'}
              </button>
            </div>
          )
        })}
        {promos.length === 0 && <div className="empty-row">Aucune promotion programmée.</div>}
      </section>

      <section className="app-card promo-list-card">
        <h2>Codes promo</h2>
        {coupons.map((coupon) => (
          <div className="promo-admin-row" key={coupon.id}>
            <div>
              <strong>{coupon.code}</strong>
              <small>{coupon.discount_type === 'percentage' ? `-${coupon.discount_value}%` : `-${coupon.discount_value}`} · {coupon.uses_count} utilisation(s)</small>
            </div>
            <button
              type="button"
              className={`member-status ${coupon.is_active ? 'active' : 'suspended'}`}
              onClick={async () => {
                await setCouponActive(coupon.id, !coupon.is_active)
                await load()
              }}
            >
              {coupon.is_active ? 'Actif' : 'Inactif'}
            </button>
          </div>
        ))}
        {coupons.length === 0 && <div className="empty-row">Aucun code promo.</div>}
      </section>
    </main>
  )
}
