import { useEffect, useMemo, useState, type Dispatch, type FormEvent, type SetStateAction } from 'react'
import { Plus, Tag } from 'lucide-react'
import {
  createPromoCode,
  createPromotion,
  getCommercialCatalog,
  listPromoCodes,
  listPromotions,
  type PromoCode,
  type Promotion,
  type PublicFormation,
} from '../lib/api'

type CommonDraft = {
  discount_type: 'percentage' | 'fixed'
  discount_value: string
  starts_at: string
  ends_at: string
  max_uses: string
  formation_id: string
  session_id: string
}

const emptyCommon = (): CommonDraft => ({
  discount_type: 'percentage',
  discount_value: '10',
  starts_at: '',
  ends_at: '',
  max_uses: '',
  formation_id: '',
  session_id: '',
})

export function PromotionsAdminPage() {
  const [promos, setPromos] = useState<Promotion[]>([])
  const [codes, setCodes] = useState<PromoCode[]>([])
  const [formations, setFormations] = useState<PublicFormation[]>([])
  const [promoName, setPromoName] = useState('')
  const [promoDraft, setPromoDraft] = useState<CommonDraft>(emptyCommon)
  const [code, setCode] = useState('')
  const [codeDraft, setCodeDraft] = useState<CommonDraft>(emptyCommon)
  const [maxPerCustomer, setMaxPerCustomer] = useState('1')
  const [minimumOrder, setMinimumOrder] = useState('0')
  const [allowOnPromotions, setAllowOnPromotions] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function load() {
    const [promotionRows, codeRows, catalog] = await Promise.all([
      listPromotions(),
      listPromoCodes(),
      getCommercialCatalog(),
    ])
    setPromos(promotionRows)
    setCodes(codeRows)
    setFormations(catalog)
  }

  useEffect(() => {
    void load().catch((err) =>
      setError(err instanceof Error ? err.message : 'Chargement impossible.'),
    )
  }, [])

  function normalize(draft: CommonDraft) {
    return {
      discount_type: draft.discount_type,
      discount_value: Number(draft.discount_value),
      starts_at: draft.starts_at ? new Date(draft.starts_at).toISOString() : null,
      ends_at: draft.ends_at ? new Date(draft.ends_at).toISOString() : null,
      max_uses: draft.max_uses ? Number(draft.max_uses) : null,
      formation_id: draft.formation_id ? Number(draft.formation_id) : null,
      session_id: draft.session_id ? Number(draft.session_id) : null,
    }
  }

  async function addPromotion(event: FormEvent) {
    event.preventDefault()
    setError('')
    setMessage('')
    try {
      await createPromotion({
        name: promoName.trim(),
        ...normalize(promoDraft),
        is_active: true,
      })
      setPromoName('')
      setPromoDraft(emptyCommon())
      setMessage('Promotion créée.')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Création impossible.')
    }
  }

  async function addCode(event: FormEvent) {
    event.preventDefault()
    setError('')
    setMessage('')
    try {
      await createPromoCode({
        code: code.trim().toUpperCase(),
        ...normalize(codeDraft),
        max_uses_per_customer: Number(maxPerCustomer),
        minimum_order_cents: Number(minimumOrder),
        allow_on_promotions: allowOnPromotions,
        is_active: true,
      })
      setCode('')
      setCodeDraft(emptyCommon())
      setMaxPerCustomer('1')
      setMinimumOrder('0')
      setAllowOnPromotions(false)
      setMessage('Code promo créé.')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Création impossible.')
    }
  }

  return (
    <main className="app-page commerce-admin-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Commercial</span>
          <h1>Promotions & codes promo</h1>
          <p>Définissez précisément les réductions, leur période et les formations concernées.</p>
        </div>
      </header>

      {message && <div className="form-success">{message}</div>}
      {error && <div className="form-error">{error}</div>}

      <section className="commerce-two-columns">
        <div>
          <form className="app-card commerce-mini-form commerce-promo-form" onSubmit={addPromotion}>
            <Tag />
            <h2>Promotion directe</h2>
            <label>Nom<input value={promoName} onChange={(e) => setPromoName(e.target.value)} placeholder="Rentrée 2026" required /></label>
            <DiscountFields draft={promoDraft} setDraft={setPromoDraft} formations={formations} />
            <button className="primary-button"><Plus size={14} /> Créer la promotion</button>
          </form>
          <PromoList promotions={promos} formations={formations} />
        </div>

        <div>
          <form className="app-card commerce-mini-form commerce-promo-form" onSubmit={addCode}>
            <Tag />
            <h2>Code promo</h2>
            <label>Code<input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="RENTREE20" required /></label>
            <DiscountFields draft={codeDraft} setDraft={setCodeDraft} formations={formations} />
            <label>Utilisations max par client<input type="number" min="1" value={maxPerCustomer} onChange={(e) => setMaxPerCustomer(e.target.value)} /></label>
            <label>Montant minimum de commande (centimes)<input type="number" min="0" value={minimumOrder} onChange={(e) => setMinimumOrder(e.target.value)} /></label>
            <label className="check-field"><input type="checkbox" checked={allowOnPromotions} onChange={(e) => setAllowOnPromotions(e.target.checked)} /> Autoriser sur une formation déjà en promotion</label>
            <button className="primary-button"><Plus size={14} /> Créer le code</button>
          </form>
          <CodeList codes={codes} formations={formations} />
        </div>
      </section>
    </main>
  )
}

function DiscountFields({
  draft,
  setDraft,
  formations,
}: {
  draft: CommonDraft
  setDraft: Dispatch<SetStateAction<CommonDraft>>
  formations: PublicFormation[]
}) {
  const sessions = useMemo(
    () => formations.find((item) => item.id === Number(draft.formation_id))?.sessions ?? [],
    [formations, draft.formation_id],
  )
  const patch = (value: Partial<CommonDraft>) =>
    setDraft((current) => ({ ...current, ...value }))

  return <>
    <label>Type
      <select value={draft.discount_type} onChange={(e) => patch({ discount_type: e.target.value as CommonDraft['discount_type'] })}>
        <option value="percentage">Pourcentage</option>
        <option value="fixed">Montant fixe (centimes)</option>
      </select>
    </label>
    <label>Valeur<input type="number" min="1" max={draft.discount_type === 'percentage' ? 100 : undefined} value={draft.discount_value} onChange={(e) => patch({ discount_value: e.target.value })} required /></label>
    <label>Début<input type="datetime-local" value={draft.starts_at} onChange={(e) => patch({ starts_at: e.target.value })} /></label>
    <label>Fin<input type="datetime-local" value={draft.ends_at} onChange={(e) => patch({ ends_at: e.target.value })} /></label>
    <label>Utilisations max<input type="number" min="1" value={draft.max_uses} onChange={(e) => patch({ max_uses: e.target.value })} placeholder="Illimité" /></label>
    <label>Formation
      <select value={draft.formation_id} onChange={(e) => patch({ formation_id: e.target.value, session_id: '' })}>
        <option value="">Toutes les formations</option>
        {formations.map((formation) => <option key={formation.id} value={formation.id}>{formation.title}</option>)}
      </select>
    </label>
    <label>Session
      <select value={draft.session_id} disabled={!draft.formation_id} onChange={(e) => patch({ session_id: e.target.value })}>
        <option value="">Toutes les sessions</option>
        {sessions.map((session) => <option key={session.id} value={session.id}>{session.label}</option>)}
      </select>
    </label>
  </>
}

function formationLabel(id: number | null, formations: PublicFormation[]) {
  if (!id) return 'Toutes les formations'
  return formations.find((item) => item.id === id)?.title ?? ('Formation #' + id)
}

function PromoList({ promotions, formations }: { promotions: Promotion[]; formations: PublicFormation[] }) {
  return <div className="commerce-simple-list">
    {promotions.map((item) => (
      <article className="app-card" key={item.id}>
        <div><strong>{item.name}</strong><small>{formationLabel(item.formation_id, formations)}</small></div>
        <span>{item.discount_type === 'percentage' ? item.discount_value + '%' : item.discount_value + ' cents'}</span>
        <small>{item.used_count}{item.max_uses ? ' / ' + item.max_uses : ''} utilisation(s)</small>
      </article>
    ))}
  </div>
}

function CodeList({ codes, formations }: { codes: PromoCode[]; formations: PublicFormation[] }) {
  return <div className="commerce-simple-list">
    {codes.map((item) => (
      <article className="app-card" key={item.id}>
        <div><strong>{item.code}</strong><small>{formationLabel(item.formation_id, formations)}</small></div>
        <span>{item.discount_type === 'percentage' ? item.discount_value + '%' : item.discount_value + ' cents'}</span>
        <small>{item.used_count}{item.max_uses ? ' / ' + item.max_uses : ''} utilisation(s)</small>
      </article>
    ))}
  </div>
}
