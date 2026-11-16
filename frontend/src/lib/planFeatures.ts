import { activeSchoolLocale } from '../app/schoolLocale'
import type { PlanEntitlement } from './api'

/** The plan fields the cards and the comparison read. */
type PlanLike = { entitlements: PlanEntitlement[]; sales_commission_bps?: number }

function lookup(entitlements: PlanEntitlement[]) {
  const get = (key: string) => entitlements.find((item) => item.feature_key === key)
  return {
    has: (key: string) => get(key) !== undefined,
    on: (key: string) => Boolean(get(key)?.enabled),
    limit: (key: string) => get(key)?.limit_value ?? null,
  }
}

function count(limit: number | null, one: string, many: string, unlimited: string): string {
  if (limit === null) return unlimited
  return limit === 1 ? `1 ${one}` : `${limit} ${many}`
}

export type PlanFeatureLine = { key: string; label: string; soon: boolean; excluded: boolean }

/**
 * The few lines a plan card shows (docs/FORFAITS.md); the comparison table has the rest.
 * Features included already but not working yet carry a "Bientôt" tag.
 */
export function planHighlights(entitlements: PlanEntitlement[]): PlanFeatureLine[] {
  if (entitlements.length === 0) return []
  const plan = lookup(entitlements)
  const lines: PlanFeatureLine[] = []
  const add = (key: string, label: string, soon = false, excluded = false) => lines.push({ key, label, soon, excluded })

  if (plan.on('organizations')) {
    add('organizations', count(plan.limit('organizations'), 'école', 'écoles', 'Écoles illimitées'))
  }
  if (plan.on('students')) add('students', count(plan.limit('students'), 'étudiant', 'étudiants', 'Étudiants illimités'))
  const formations = plan.on('active_formations') ? plan.limit('active_formations') : 0
  const teachers = plan.on('teachers') ? plan.limit('teachers') : 0
  add('content', formations === null && teachers === null
    ? 'Formations et professeurs illimités'
    : `${count(formations, 'formation', 'formations', 'Formations illimitées')} · ${count(teachers, 'professeur', 'professeurs', 'professeurs illimités')}`)

  if (plan.on('live')) {
    const perClass = plan.limit('live')
    const rooms = plan.limit('live_rooms')
    const atOnce = !plan.on('live_rooms') || rooms === null ? '' : rooms === 1 ? ', 1 à la fois' : `, ${rooms} en même temps`
    const monthly = plan.on('live_hours') ? plan.limit('live_hours') : null
    const hours = monthly === null ? '' : `, ${monthly} h par mois`
    add('live', perClass === null ? `Cours en live${atOnce}${hours}` : `Live jusqu’à ${perClass} étudiants${atOnce}${hours}`)
  } else {
    add('formats', 'Formations en ligne et en présentiel')
    if (plan.has('live')) add('live', 'Sans cours en live', false, true)
  }

  if (plan.on('replays')) {
    const replays = plan.limit('replays')
    const transcription = plan.on('transcription') ? plan.limit('transcription') : undefined
    const hours = (value: number | null) => (value === null ? '' : ` ${value} h`)
    add('replays', transcription === undefined
      ? `Replays des lives${replays === null ? '' : `, ${replays} h par mois`}`
      : replays === transcription
        ? `Replays et transcription${replays === null ? '' : `, ${replays} h par mois`}`
        : `Replays${hours(replays)} et transcription${hours(transcription)} par mois`, true)
  }

  if (plan.on('white_label')) add('white_label', 'Votre seule marque, sans « Powered by »')
  else if (plan.on('custom_domain')) add('custom_domain', 'Votre propre nom de domaine')
  return lines
}

function retention(days: number | null): string {
  if (!days) return 'Fin de la session'
  if (days % 30 === 0 && days >= 60) return `Session + ${days / 30} mois`
  return `Session + ${days} jours`
}

/** A cell of the comparison: a value, included (true) or not (false). */
export type ComparisonCell = string | boolean
export type ComparisonRow = { key: string; label: string; soon: boolean; cell: (plan: PlanLike) => ComparisonCell }

function quotaRow(key: string, label: string, unlimited: string): ComparisonRow {
  return {
    key, label, soon: false,
    cell: (item) => {
      const plan = lookup(item.entitlements)
      if (!plan.on(key)) return false
      const limit = plan.limit(key)
      return limit === null ? unlimited : limit.toLocaleString(activeSchoolLocale())
    },
  }
}

function sizeRow(key: string, label: string, unit = '', soon = false, format?: (limit: number | null) => string): ComparisonRow {
  return {
    key, label, soon,
    cell: (item) => {
      const plan = lookup(item.entitlements)
      if (!plan.on(key)) return false
      const limit = plan.limit(key)
      if (format) return format(limit)
      return limit === null ? true : `${limit}${unit}`
    },
  }
}

function featureRow(key: string, label: string, soon = false): ComparisonRow {
  return { key, label, soon, cell: (item) => lookup(item.entitlements).on(key) }
}

/** Everything the plans include, row by row, for the comparison table. */
export const COMPARISON_ROWS: ComparisonRow[] = [
  quotaRow('organizations', 'Écoles gérées', 'Illimitées'),
  quotaRow('students', 'Étudiants', 'Illimités'),
  quotaRow('active_formations', 'Formations publiées', 'Illimitées'),
  quotaRow('teachers', 'Professeurs', 'Illimités'),
  { key: 'formats', label: 'Formations en ligne et en présentiel', soon: false, cell: (item) => item.entitlements.length > 0 },
  sizeRow('live', 'Cours en live : étudiants par classe'),
  sizeRow('live_rooms', 'Lives en même temps'),
  {
    // Live hours a month: counted on the free plan only, without limit elsewhere.
    key: 'live_hours', label: 'Heures de live par mois', soon: false,
    cell: (item) => {
      const plan = lookup(item.entitlements)
      if (!plan.on('live')) return false
      const limit = plan.on('live_hours') ? plan.limit('live_hours') : null
      return limit === null ? 'Illimitées' : `${limit} h`
    },
  },
  sizeRow('live_class_hours', 'Durée d’un cours en live', '', false, (limit) => (limit === null ? 'Libre' : `${limit} h au plus`)),
  sizeRow('replays', 'Replays des lives par mois', ' h', true),
  sizeRow('replay_retention_days', 'Conservation des replays', '', true, retention),
  sizeRow('transcription', 'Transcription des lives par mois', ' h', true),
  featureRow('advanced_stats', 'Statistiques avancées et exports Excel', true),
  featureRow('custom_domain', 'Votre propre nom de domaine'),
  featureRow('white_label', 'Sans la mention « Powered by »'),
  featureRow('whatsapp_support', 'Support WhatsApp'),
  featureRow('priority_support', 'Support prioritaire et aide à la mise en place'),
  {
    key: 'commission', label: 'Commission sur vos ventes, frais de paiement compris', soon: false,
    cell: (item) => (item.sales_commission_bps === undefined ? false : `${(item.sales_commission_bps / 100).toLocaleString(activeSchoolLocale())} %`),
  },
]

/** The rows at least one plan has something in. */
export function comparisonRows(plans: PlanLike[]): ComparisonRow[] {
  return COMPARISON_ROWS.filter((row) => plans.some((plan) => row.cell(plan) !== false))
}

/** The price per month a plan is shown at: an annual price spread over twelve months. */
export function monthlyEquivalent(plan: { monthly_price_cents: number | null; annual_price_cents: number | null }, annual: boolean) {
  if (!annual) return plan.monthly_price_cents
  return plan.annual_price_cents === null ? null : Math.round(plan.annual_price_cents / 12)
}

/** XAF has no subunit: amounts are stored in whole francs. Other currencies are in cents. */
export function formatMoney(amount: number, currency: string): string {
  if (currency.toUpperCase() === 'XAF') {
    return new Intl.NumberFormat(activeSchoolLocale(), { style: 'currency', currency: 'XAF', maximumFractionDigits: 0 }).format(amount)
  }
  return new Intl.NumberFormat(activeSchoolLocale(), { style: 'currency', currency, maximumFractionDigits: 2 }).format(amount / 100)
}

export function commissionLabel(bps: number | undefined): string | null {
  if (bps === undefined) return null
  const pct = (bps / 100).toLocaleString(activeSchoolLocale(), { maximumFractionDigits: 2 })
  return `${pct} % sur vos ventes`
}
