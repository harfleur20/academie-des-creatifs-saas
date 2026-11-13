/**
 * The plan someone clicked on the landing page, carried through signup and school creation
 * (docs/FORFAITS.md). Kept in this tab only; a lost choice just means the default path.
 */
export type BillingInterval = 'monthly' | 'annual'
export type PlanChoice = { plan: string; interval: BillingInterval }

const KEY = 'academie_saas_plan_choice'
/** Clicking one of these sends a new school to the billing page; the others start with the trial. */
export const PAY_FIRST_PLANS = new Set(['starter', 'business'])

export function planChoiceFromSearch(search: string): PlanChoice | null {
  const params = new URLSearchParams(search)
  const plan = (params.get('plan') || '').trim().toLowerCase()
  if (!/^[a-z0-9_-]{1,64}$/.test(plan)) return null
  return { plan, interval: params.get('interval') === 'annual' ? 'annual' : 'monthly' }
}

export function savePlanChoice(choice: PlanChoice) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(choice))
  } catch {
    // Storage can be unavailable in privacy-restricted browser contexts.
  }
}

export function readPlanChoice(): PlanChoice | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(KEY) || 'null') as PlanChoice | null
    return value && typeof value.plan === 'string' ? planChoiceFromSearch(`?plan=${value.plan}&interval=${value.interval}`) : null
  } catch {
    return null
  }
}

export function clearPlanChoice() {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // Nothing to clear.
  }
}

export function planChoiceQuery(choice: PlanChoice): string {
  return `plan=${encodeURIComponent(choice.plan)}&interval=${choice.interval}`
}

export function billingPathFor(choice: PlanChoice): string {
  return `/app/manage/billing?${planChoiceQuery(choice)}`
}
