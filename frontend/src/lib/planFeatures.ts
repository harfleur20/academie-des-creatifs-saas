import type { PlanEntitlement } from './api'

/** How a plan's entitlements read for a school (docs/FORFAITS.md). */
const FEATURE_LABELS: Record<string, (limit: number | null) => string> = {
  students: (limit) => (limit === null ? 'Étudiants illimités' : `${limit.toLocaleString('fr-FR')} étudiants actifs`),
  teachers: (limit) => (limit === null ? 'Professeurs illimités' : `${limit} professeurs`),
  active_formations: (limit) => (limit === null ? 'Formations illimitées' : `${limit} formations publiées`),
  live: () => 'Cours en live dans la plateforme',
  custom_domain: () => 'Votre propre nom de domaine',
  priority_support: () => 'Accompagnement prioritaire',
  automations: () => 'Relances et rappels automatiques',
  advanced_reporting: () => 'Rapports avancés',
}

/** The order features are listed in, quotas first. */
const FEATURE_ORDER = ['students', 'teachers', 'active_formations', 'live', 'custom_domain', 'priority_support']

export function entitlementLabel(item: PlanEntitlement): string {
  const label = FEATURE_LABELS[item.feature_key]
  if (label) return label(item.limit_value)
  const name = item.feature_key.replace(/_/g, ' ')
  const text = name.charAt(0).toUpperCase() + name.slice(1)
  return item.limit_value === null ? text : `${text} : ${item.limit_value}`
}

export function includedFeatures(entitlements: PlanEntitlement[]): PlanEntitlement[] {
  const rank = (key: string) => {
    const index = FEATURE_ORDER.indexOf(key)
    return index === -1 ? FEATURE_ORDER.length : index
  }
  return entitlements.filter((item) => item.enabled).sort((a, b) => rank(a.feature_key) - rank(b.feature_key))
}

/** XAF has no subunit: amounts are stored in whole francs. Other currencies are in cents. */
export function formatMoney(amount: number, currency: string): string {
  if (currency.toUpperCase() === 'XAF') {
    return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'XAF', maximumFractionDigits: 0 }).format(amount)
  }
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency, maximumFractionDigits: 2 }).format(amount / 100)
}

export function commissionLabel(bps: number | undefined): string | null {
  if (bps === undefined) return null
  const pct = (bps / 100).toLocaleString('fr-FR', { maximumFractionDigits: 2 })
  return `${pct} % sur vos ventes`
}
