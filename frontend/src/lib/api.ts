import { DEMO_READ_ONLY_MESSAGE, readDemoState } from './demoState'
import { toast } from '../ui/toast'

export type AuthUser = {
  id: number
  full_name: string
  email: string
  phone: string | null
  avatar_url: string | null
  status: string
  platform_role: string
}

export type AuthResponse = {
  message: string
  user: AuthUser
  access_token: string
  token_type: string
}

export type Organization = {
  id: number
  name: string
  name_changed_at: string | null
  slug: string
  subdomain: string | null
  status: string
  is_active: boolean
  contact_email: string | null
  timezone: string
  locale: string
  logo_url: string | null
  primary_color: string
  secondary_color: string
  accent_color: string
  created_at: string
}

export type Member = {
  id: number
  organization_id: number
  user_id: number
  role: 'owner' | 'admin' | 'manager' | 'teacher' | 'student'
  status: 'active' | 'suspended'
  roles: Array<{ role: 'owner' | 'admin' | 'manager' | 'teacher' | 'student' }>
  user: {
    id: number
    full_name: string
    email: string
  }
}

export type Invitation = {
  id: number
  organization_id: number
  email: string
  role: 'admin' | 'manager' | 'teacher'
  status: string
  invited_by_user_id: number | null
  expires_at: string
  created_at: string
  acceptance_token?: string
}

export type PlanEntitlement = {
  feature_key: string
  enabled: boolean
  limit_value: number | null
}

export type Plan = {
  id: number
  code: string
  name: string
  description: string
  currency: string
  monthly_price_cents: number | null
  annual_price_cents: number | null
  trial_days: number
  is_public: boolean
  /** Share of each student payment the platform keeps, in basis points (800 = 8 %). */
  sales_commission_bps?: number
  entitlements: PlanEntitlement[]
}

export type BillingLine = { label: string; quantity: number; unit_amount_cents: number; amount_cents: number }

export type Addon = {
  code: string
  name: string
  description: string
  feature_key: string | null
  unit_label: string
  unit_price_cents: number | null
  currency: string
  status: 'active' | 'coming_soon' | 'inactive'
  plan_codes: string[]
}

export type BillingUsage = {
  plan_code: string | null
  plan_name: string | null
  billing_interval: 'monthly' | 'annual'
  commission_bps: number
  live_included: boolean
  custom_domain_included: boolean
  metrics: Array<{
    feature_key: string
    label: string
    current: number
    limit: number | null
    extra: number
    unit_price_cents: number | null
    extra_amount_cents: number
  }>
  next_payment: { currency: string; lines: BillingLine[]; total_cents: number } | null
}

export const listAddons = () => request<Addon[]>('/billing/addons', { organizationId: null })
export const getBillingUsage = () => request<BillingUsage>('/billing/usage')

export type RevenueSummary = {
  currency: string
  gross_cents: number
  commission_cents: number
  earned_cents: number
  paid_out_cents: number
  pending_payout_cents: number
  available_cents: number
  commission_bps: number
  min_payout_cents: number
}

export type LedgerEntry = {
  id: number
  kind: string
  gross_cents: number
  commission_bps: number
  commission_cents: number
  amount_cents: number
  currency: string
  description: string
  occurred_at: string
}

export type Payout = {
  id: number
  amount_cents: number
  currency: string
  method: 'mobile_money' | 'bank'
  destination: string
  account_name: string
  status: 'requested' | 'paid' | 'rejected' | 'cancelled'
  requested_at: string
  processed_at: string | null
  transfer_reference: string | null
  note: string | null
}

export type AdminPayout = Payout & { organization_id: number; organization_name: string }

export const getRevenueSummary = () => request<RevenueSummary>('/revenue/summary')
export const listLedgerEntries = () => request<LedgerEntry[]>('/revenue/entries')
export const listPayouts = () => request<Payout[]>('/revenue/payouts')
export const requestPayout = (payload: { amount_cents: number; method: Payout['method']; destination: string; account_name: string }) =>
  request<Payout>('/revenue/payouts', { method: 'POST', body: JSON.stringify(payload) })
export const cancelPayout = (payoutId: number) =>
  request<Payout>(`/revenue/payouts/${payoutId}/cancel`, { method: 'POST' })

export const listAdminPayouts = (status?: Payout['status']) =>
  request<AdminPayout[]>(`/admin/payouts${status ? `?status=${status}` : ''}`, { organizationId: null })
export const markAdminPayoutPaid = (payoutId: number, payload: { transfer_reference: string; note?: string }) =>
  request<AdminPayout>(`/admin/payouts/${payoutId}/paid`, { method: 'POST', body: JSON.stringify(payload), organizationId: null })
export const rejectAdminPayout = (payoutId: number, note: string) =>
  request<AdminPayout>(`/admin/payouts/${payoutId}/reject`, { method: 'POST', body: JSON.stringify({ note }), organizationId: null })
export const listAdminAddons = () => request<Addon[]>('/admin/addons', { organizationId: null })
export const updateAdminAddon = (
  code: string,
  payload: Partial<Pick<Addon, 'name' | 'description' | 'unit_price_cents' | 'status' | 'plan_codes'>>,
  reason: string,
) =>
  request<Addon>(`/admin/addons/${code}?reason=${encodeURIComponent(reason)}`, { method: 'PATCH', body: JSON.stringify(payload), organizationId: null })

export type Subscription = {
  id: number
  organization_id: number
  status: 'trialing' | 'active' | 'past_due' | 'suspended' | 'cancelled'
  billing_interval: 'monthly' | 'annual'
  started_at: string
  trial_ends_at: string | null
  current_period_start: string | null
  current_period_end: string | null
  grace_period_ends_at: string | null
  suspended_at: string | null
  cancel_at_period_end: boolean
  cancelled_at: string | null
  provider: string | null
  chosen_plan_code?: string | null
  chosen_billing_interval?: 'monthly' | 'annual' | null
  plan: Plan
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const TOKEN_KEY = 'academie_saas_access_token'
const ORGANIZATION_KEY = 'academie_saas_organization_id'
const SUPPORT_MODE_KEY = 'academie_saas_support_mode'
const ORIGINAL_ADMIN_TOKEN_KEY = 'academie_saas_original_admin_token'
const BROWSER_SESSION_KEY = 'academie_saas_browser_session'

export type SupportModeState = {
  session_id: number
  organization_id: number
  organization_name: string
  expires_at: string
}

export class ApiError extends Error {
  status: number
  /** Machine-readable reason, when the server gives one (e.g. addon_required). */
  code: string | null

  constructor(status: number, message: string, code: string | null = null) {
    super(message)
    this.status = status
    this.code = code
  }
}

/**
 * Beyond its plan, adding a teacher or publishing a formation costs an add-on per unit:
 * the server says so (409 addon_required), the school confirms the price, and the call is sent again.
 */
async function withAddonConsent<T>(call: (acceptAddon: boolean) => Promise<T>): Promise<T> {
  try {
    return await call(false)
  } catch (error) {
    if (!(error instanceof ApiError) || error.code !== 'addon_required') throw error
    if (!window.confirm(`${error.message}\n\nAccepter l’option et continuer ?`)) {
      throw new ApiError(error.status, 'Ajout annulé : votre forfait reste inchangé.', 'addon_declined')
    }
    return call(true)
  }
}

export function getAccessToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(ORIGINAL_ADMIN_TOKEN_KEY)
  if (!isCurrentBrowserSession()) return null
  return sessionStorage.getItem(TOKEN_KEY)
}

export function isCurrentBrowserSession() {
  const token = sessionStorage.getItem(TOKEN_KEY)
  if (!token) return true
  let tabSession = sessionStorage.getItem(BROWSER_SESSION_KEY)
  const browserSession = localStorage.getItem(BROWSER_SESSION_KEY)
  if (!tabSession && !browserSession) {
    tabSession = crypto.randomUUID()
    sessionStorage.setItem(BROWSER_SESSION_KEY, tabSession)
    localStorage.setItem(BROWSER_SESSION_KEY, tabSession)
    return true
  }
  if (tabSession === browserSession) return true
  clearSession()
  return false
}

export function browserSessionStorageKey() {
  return BROWSER_SESSION_KEY
}

export function setAccessToken(token: string) {
  const browserSession = crypto.randomUUID()
  sessionStorage.setItem(TOKEN_KEY, token)
  sessionStorage.setItem(BROWSER_SESSION_KEY, browserSession)
  sessionStorage.removeItem(ORGANIZATION_KEY)
  localStorage.removeItem(ORGANIZATION_KEY)
  localStorage.setItem(BROWSER_SESSION_KEY, browserSession)
}

function restoreOriginalAdminSession() {
  const originalToken = sessionStorage.getItem(ORIGINAL_ADMIN_TOKEN_KEY)
  if (originalToken) {
    sessionStorage.setItem(TOKEN_KEY, originalToken)
  } else {
    sessionStorage.removeItem(TOKEN_KEY)
  }
  sessionStorage.removeItem(ORIGINAL_ADMIN_TOKEN_KEY)
  sessionStorage.removeItem(SUPPORT_MODE_KEY)
  sessionStorage.removeItem(ORGANIZATION_KEY)
}

export function getSupportMode(): SupportModeState | null {
  const raw = sessionStorage.getItem(SUPPORT_MODE_KEY)
  if (!raw) return null

  try {
    const state = JSON.parse(raw) as SupportModeState
    if (
      !Number.isInteger(state.session_id) ||
      !Number.isInteger(state.organization_id) ||
      !state.organization_name ||
      !state.expires_at
    ) {
      restoreOriginalAdminSession()
      return null
    }

    if (new Date(state.expires_at).getTime() <= Date.now()) {
      restoreOriginalAdminSession()
      return null
    }
    return state
  } catch {
    restoreOriginalAdminSession()
    return null
  }
}

export function clearSession() {
  const browserSession = sessionStorage.getItem(BROWSER_SESSION_KEY)
  if (browserSession && localStorage.getItem(BROWSER_SESSION_KEY) === browserSession) {
    localStorage.removeItem(BROWSER_SESSION_KEY)
  }
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(BROWSER_SESSION_KEY)
  sessionStorage.removeItem(ORGANIZATION_KEY)
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(ORGANIZATION_KEY)
  sessionStorage.removeItem(SUPPORT_MODE_KEY)
  sessionStorage.removeItem(ORIGINAL_ADMIN_TOKEN_KEY)
  localStorage.removeItem(SUPPORT_MODE_KEY)
  localStorage.removeItem(ORIGINAL_ADMIN_TOKEN_KEY)
}

export const logoutSession = () => request<void>('/auth/logout', { method: 'POST', organizationId: null, keepalive: true })

export function getStoredOrganizationId(): number | null {
  localStorage.removeItem(ORGANIZATION_KEY)
  const raw = sessionStorage.getItem(ORGANIZATION_KEY)
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isInteger(parsed) ? parsed : null
}

export function setStoredOrganizationId(id: number | null) {
  if (id === null) {
    sessionStorage.removeItem(ORGANIZATION_KEY)
    return
  }
  sessionStorage.setItem(ORGANIZATION_KEY, String(id))
}

async function request<T>(
  path: string,
  options: RequestInit & { organizationId?: number | null } = {},
): Promise<T> {
  const headers = new Headers(options.headers)
  if (!(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  // In the read-only demo, nothing is sent that would change something (the server refuses it too).
  const method = (options.method || 'GET').toUpperCase()
  if (method !== 'GET' && method !== 'HEAD' && !path.startsWith('/auth/demo') && readDemoState()) {
    toast.info(DEMO_READ_ONLY_MESSAGE)
    throw new ApiError(403, DEMO_READ_ONLY_MESSAGE, 'demo_read_only')
  }

  const token = getAccessToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const organizationId =
    options.organizationId === undefined
      ? getStoredOrganizationId()
      : options.organizationId

  if (organizationId !== null && organizationId !== undefined) {
    headers.set('X-Organization-Id', String(organizationId))
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    let message = `La requête a échoué (HTTP ${response.status}).`
    let code: string | null = null
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') message = body.detail
      else if (typeof body?.detail?.message === 'string') {
        message = body.detail.message
        code = typeof body.detail.code === 'string' ? body.detail.code : null
        if (code === 'demo_read_only') toast.info(message)
      }
    } catch {
      // Keep generic message.
    }
    throw new ApiError(response.status, message, code)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

async function requestBlob(
  path: string,
  options: RequestInit & { organizationId?: number | null } = {},
): Promise<Blob> {
  const headers = new Headers(options.headers)
  const token = getAccessToken()
  if (token) headers.set('Authorization', 'Bearer ' + token)

  const organizationId =
    options.organizationId === undefined
      ? getStoredOrganizationId()
      : options.organizationId

  if (organizationId !== null && organizationId !== undefined) {
    headers.set('X-Organization-Id', String(organizationId))
  }

  const response = await fetch(API_BASE + path, {
    ...options,
    headers,
  })

  if (!response.ok) {
    let message = `Le téléchargement a échoué (HTTP ${response.status}).`
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') message = body.detail
    } catch {
      // Keep generic message.
    }
    throw new ApiError(response.status, message)
  }

  return response.blob()
}

export async function login(email: string, password: string) {
  const response = await request<AuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
    organizationId: null,
  })
  setAccessToken(response.access_token)
  return response
}

export async function register(fullName: string, email: string, password: string) {
  const response = await request<AuthResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ full_name: fullName, email, password }),
    organizationId: null,
  })
  setAccessToken(response.access_token)
  return response
}

export const getMe = () =>
  request<AuthUser>('/auth/me', { organizationId: null })

export const updateMyProfile = (payload: {
  full_name: string
  phone: string | null
}) =>
  request<AuthUser>('/auth/me', {
    method: 'PATCH',
    body: JSON.stringify(payload),
    organizationId: null,
  })

export const changeMyPassword = (
  currentPassword: string,
  newPassword: string,
) =>
  request<void>('/auth/me/change-password', {
    method: 'POST',
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
    organizationId: null,
  })

export const uploadMyAvatar = (file: File) => {
  const body = new FormData()
  body.append('file', file)
  return request<AuthUser>('/auth/me/avatar', {
    method: 'POST',
    body,
    organizationId: null,
  })
}

export const listOrganizations = () =>
  request<Organization[]>('/organizations', { organizationId: null })

export const createOrganization = (payload: {
  name: string
  slug: string
  plan_code?: string
  billing_interval?: 'monthly' | 'annual'
}) =>
  request<Organization>('/organizations', {
    method: 'POST',
    body: JSON.stringify(payload),
    organizationId: null,
  })

export type OrganizationPolicy = {
  name_change_cooldown_days: number
}

export const getOrganizationPolicy = () =>
  request<OrganizationPolicy>('/organizations/policy', {
    organizationId: null,
  })

export const getCurrentOrganization = () =>
  request<Organization>('/organizations/current')

export const updateCurrentOrganization = (payload: {
  name?: string
  contact_email?: string | null
  timezone?: string
  locale?: string
  logo_url?: string | null
  primary_color?: string
  secondary_color?: string
  accent_color?: string
}) =>
  request<Organization>('/organizations/current', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })

export type WorkspaceSpace = 'manage' | 'teacher' | 'student'

export type OrganizationAccessProfile = {
  organization_id: number
  primary_role: Member['role'] | 'super_admin'
  roles: string[]
  spaces: WorkspaceSpace[]
  default_space: WorkspaceSpace | ''
}

export const getOrganizationAccessProfile = () =>
  request<OrganizationAccessProfile>('/organizations/current/access-profile')

export const listMembers = () =>
  request<Member[]>('/organizations/current/members')

const addonQuery = (accept: boolean) => (accept ? '?accept_addon=true' : '')

export const updateMember = (
  memberId: number,
  payload: { role?: Member['role']; status?: Member['status'] },
) =>
  withAddonConsent((accept) => request<Member>(`/organizations/current/members/${memberId}${addonQuery(accept)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  }))

export const updateMemberFunctionalRoles = (
  memberId: number,
  functionalRoles: Array<'teacher' | 'student'>,
) =>
  withAddonConsent((accept) => request<Member>(
    `/organizations/current/members/${memberId}/functional-roles${addonQuery(accept)}`,
    {
      method: 'PUT',
      body: JSON.stringify({ functional_roles: functionalRoles }),
    },
  ))

export const listInvitations = () =>
  request<Invitation[]>('/organizations/current/invitations')

export const createInvitation = (payload: {
  email: string
  role: Invitation['role']
}) =>
  withAddonConsent((accept) => request<Invitation>(`/organizations/current/invitations${addonQuery(accept)}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  }))

export const renewInvitation = (invitationId: number) =>
  request<Invitation>(`/organizations/current/invitations/${invitationId}/renew`, {
    method: 'POST',
  })



export type InvitationPreview = {
  organization_id: number
  organization_name: string
  email: string
  role: 'admin' | 'manager' | 'teacher'
  expires_at: string
  logo_url: string | null
  primary_color: string
  secondary_color: string
}

export type InvitationAcceptResult = {
  organization: Organization
  membership: Member
}

export const getInvitationPreview = (token: string) =>
  request<InvitationPreview>(
    '/organizations/invitations/' + encodeURIComponent(token),
    { organizationId: null },
  )

export const acceptOrganizationInvitation = (token: string) =>
  request<InvitationAcceptResult>(
    '/organizations/invitations/' + encodeURIComponent(token) + '/accept',
    { method: 'POST', organizationId: null },
  )

export const cancelInvitation = (invitationId: number) =>
  request<Invitation>(
    `/organizations/current/invitations/${invitationId}/cancel`,
    { method: 'POST' },
  )

export const listPlans = () =>
  request<Plan[]>('/billing/plans', { organizationId: null })

export const getCurrentSubscription = () =>
  request<Subscription>('/billing/subscription')


export type PaymentMode = {
  mode: string
  demo_enabled: boolean
  tara_configured: boolean
}

export type DemoPaymentAttempt = {
  id: number
  organization_id: number
  plan_id: number
  billing_interval: 'monthly' | 'annual'
  provider: string
  provider_reference: string
  status: 'pending' | 'paid' | 'failed' | 'cancelled'
  amount_cents: number
  currency: string
  confirmed_at: string | null
  checkout_url: string | null
  provider_transaction_id: string | null
  activated_subscription_id: number | null
  failure_reason: string | null
  plan: Plan
}

export type BillingInvoice = {
  id: number
  organization_id: number
  subscription_id: number | null
  plan_id: number
  payment_attempt_id: number | null
  invoice_number: string
  status: 'open' | 'paid' | 'void'
  amount_cents: number
  /** Plan, then add-ons billed per unit. */
  lines?: BillingLine[] | null
  currency: string
  billing_interval: 'monthly' | 'annual'
  period_start: string
  period_end: string
  issued_at: string
  due_at: string | null
  paid_at: string | null
  plan: Plan
}

export type DemoPaymentConfirmation = {
  payment: DemoPaymentAttempt
  subscription: Subscription
}

export const getPaymentMode = () =>
  request<PaymentMode>('/billing/payment-mode', { organizationId: null })

export const createDemoCheckout = (
  planCode: string,
  billingInterval: 'monthly' | 'annual',
) =>
  request<DemoPaymentAttempt>('/billing/demo/checkout', {
    method: 'POST',
    body: JSON.stringify({
      plan_code: planCode,
      billing_interval: billingInterval,
    }),
  })

export const confirmDemoPayment = (paymentAttemptId: number) =>
  request<DemoPaymentConfirmation>(
    `/billing/demo/payments/${paymentAttemptId}/confirm`,
    { method: 'POST' },
  )


export type TaraCheckout = {
  payment: DemoPaymentAttempt
  checkout_url: string
}

export type TaraReconcile = {
  payment: DemoPaymentAttempt
  subscription: Subscription | null
  status: 'pending' | 'paid' | 'failed'
}

export const createTaraCheckout = (
  planCode: string,
  billingInterval: 'monthly' | 'annual',
) =>
  request<TaraCheckout>('/billing/tara/checkout', {
    method: 'POST',
    body: JSON.stringify({
      plan_code: planCode,
      billing_interval: billingInterval,
    }),
  })

export const reconcileTaraPayment = (providerReference: string) =>
  request<TaraReconcile>(
    `/billing/tara/reconcile/${encodeURIComponent(providerReference)}`,
    { method: 'POST' },
  )


export const listBillingInvoices = () =>
  request<BillingInvoice[]>('/billing/invoices')

export const cancelSubscriptionAtPeriodEnd = () =>
  request<Subscription>('/billing/subscription/cancel-at-period-end', {
    method: 'POST',
  })

export const resumeSubscription = () =>
  request<Subscription>('/billing/subscription/resume', {
    method: 'POST',
  })


export type OrganizationDomain = {
  id: number
  organization_id: number
  hostname: string
  status: 'pending' | 'verified'
  verification_token: string
  is_primary: boolean
  verified_at: string | null
  created_at: string
}

export type OrganizationDomainConfig = {
  base_domain: string | null
  cname_target: string | null
  verification_record_prefix: string
}

export type HostBranding = {
  organization_id: number
  name: string
  slug: string
  subdomain: string | null
  hostname: string
  logo_url: string | null
  primary_color: string
  secondary_color: string
  accent_color: string
}

export const getOrganizationDomainConfig = () =>
  request<OrganizationDomainConfig>('/organizations/domain-config', {
    organizationId: null,
  })

export const updateCurrentSubdomain = (subdomain: string | null) =>
  request<Organization>('/organizations/current/subdomain', {
    method: 'PATCH',
    body: JSON.stringify({ subdomain }),
  })

export const listOrganizationDomains = () =>
  request<OrganizationDomain[]>('/organizations/current/domains')

export const createOrganizationDomain = (hostname: string) =>
  request<OrganizationDomain>('/organizations/current/domains', {
    method: 'POST',
    body: JSON.stringify({ hostname }),
  })

export const verifyOrganizationDomain = (domainId: number) =>
  request<OrganizationDomain>(
    `/organizations/current/domains/${domainId}/verify`,
    { method: 'POST' },
  )

export const setPrimaryOrganizationDomain = (domainId: number) =>
  request<OrganizationDomain>(
    `/organizations/current/domains/${domainId}/primary`,
    { method: 'POST' },
  )

export const deleteOrganizationDomain = (domainId: number) =>
  request<void>(
    `/organizations/current/domains/${domainId}`,
    { method: 'DELETE' },
  )

export const resolveHostBranding = (hostname: string) =>
  request<HostBranding>(
    `/organizations/resolve-host?hostname=${encodeURIComponent(hostname)}`,
    { organizationId: null },
  )


export type AdminRevenueTotal = {
  currency: string
  amount: number
  paid_invoices: number
}

export type AdminDashboard = {
  organizations_total: number
  organizations_active: number
  organizations_suspended: number
  subscriptions_trialing: number
  subscriptions_active: number
  subscriptions_past_due: number
  subscriptions_suspended: number
  users_total: number
  revenue: AdminRevenueTotal[]
}

export type AdminOrganization = {
  id: number
  name: string
  slug: string
  subdomain: string | null
  status: string
  is_active: boolean
  contact_email: string | null
  logo_url: string | null
  created_at: string
  owner_name: string | null
  owner_email: string | null
  member_count: number
  student_count: number
  teacher_count: number
  formation_count: number
  verified_domain_count: number
  subscription: {
    id: number
    status: 'trialing' | 'active' | 'past_due' | 'suspended' | 'cancelled'
    billing_interval: 'monthly' | 'annual'
    plan_code: string
    plan_name: string
    trial_ends_at: string | null
    current_period_end: string | null
    grace_period_ends_at: string | null
    provider: string | null
  } | null
}

export const getAdminDashboard = () =>
  request<AdminDashboard>('/admin/dashboard', { organizationId: null })

export const listAdminOrganizations = () =>
  request<AdminOrganization[]>('/admin/organizations', {
    organizationId: null,
  })


export type AdminAuditLog = {
  id: number
  action: string
  reason: string
  details: string | null
  actor_user_id: number | null
  actor_name: string | null
  actor_email: string | null
  created_at: string
}

export type AdminCommercialAccess = {
  id: number
  plan_id: number
  plan_code: string
  plan_name: string
  starts_at: string
  ends_at: string
  reason: string
  status: string
}

export type AdminUsageMetric = {
  feature_key: string
  label: string
  current_value: number
  limit_value: number | null
  enabled: boolean
  over_limit: boolean
}

export type AdminOrganizationDetail = AdminOrganization & {
  commercial_access: AdminCommercialAccess | null
  effective_plan_name: string | null
  effective_plan_source: 'subscription' | 'commercial_access' | null
  usage_metrics: AdminUsageMetric[]
  audit_logs: AdminAuditLog[]
}

export const getAdminOrganization = (organizationId: number) =>
  request<AdminOrganizationDetail>(
    `/admin/organizations/${organizationId}`,
    { organizationId: null },
  )

export const suspendAdminOrganization = (
  organizationId: number,
  reason: string,
) =>
  request<AdminOrganizationDetail>(
    `/admin/organizations/${organizationId}/suspend`,
    {
      method: 'POST',
      body: JSON.stringify({ reason }),
      organizationId: null,
    },
  )

export const reactivateAdminOrganization = (
  organizationId: number,
  reason: string,
) =>
  request<AdminOrganizationDetail>(
    `/admin/organizations/${organizationId}/reactivate`,
    {
      method: 'POST',
      body: JSON.stringify({ reason }),
      organizationId: null,
    },
  )

export const extendAdminTrial = (
  organizationId: number,
  days: number,
  reason: string,
) =>
  request<AdminOrganizationDetail>(
    `/admin/organizations/${organizationId}/extend-trial`,
    {
      method: 'POST',
      body: JSON.stringify({ days, reason }),
      organizationId: null,
    },
  )


export type AdminPlanEntitlement = {
  feature_key: string
  enabled: boolean
  limit_value: number | null
}

export type AdminPlan = {
  id: number
  code: string
  name: string
  description: string
  currency: string
  monthly_price_cents: number | null
  annual_price_cents: number | null
  trial_days: number
  is_public: boolean
  is_active: boolean
  sales_commission_bps: number
  entitlements: AdminPlanEntitlement[]
}

export const listAdminPlans = () =>
  request<AdminPlan[]>('/admin/plans', { organizationId: null })

export const updateAdminPlan = (
  planId: number,
  payload: Partial<Omit<AdminPlan, 'id' | 'code' | 'entitlements'>>,
  reason: string,
) =>
  request<AdminPlan>(
    `/admin/plans/${planId}?reason=${encodeURIComponent(reason)}`,
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
      organizationId: null,
    },
  )

export const replaceAdminPlanEntitlements = (
  planId: number,
  entitlements: AdminPlanEntitlement[],
  reason: string,
) =>
  request<AdminPlan>(
    `/admin/plans/${planId}/entitlements?reason=${encodeURIComponent(reason)}`,
    {
      method: 'PUT',
      body: JSON.stringify({ entitlements }),
      organizationId: null,
    },
  )


export const grantAdminCommercialAccess = (
  organizationId: number,
  planId: number,
  days: number,
  reason: string,
) =>
  request<AdminOrganizationDetail>(
    `/admin/organizations/${organizationId}/commercial-access`,
    {
      method: 'POST',
      body: JSON.stringify({
        plan_id: planId,
        days,
        reason,
      }),
      organizationId: null,
    },
  )

export const cancelAdminCommercialAccess = (
  organizationId: number,
  reason: string,
) =>
  request<AdminOrganizationDetail>(
    `/admin/organizations/${organizationId}/commercial-access`,
    {
      method: 'DELETE',
      body: JSON.stringify({ reason }),
      organizationId: null,
    },
  )

export type AdminSupportSession = {
  session_id: number
  organization_id: number
  organization_name: string
  access_token: string
  token_type: string
  expires_at: string
}

export async function startAdminSupportMode(
  organizationId: number,
  reason: string,
) {
  const adminToken = getAccessToken()
  if (!adminToken) {
    throw new ApiError(401, 'Session administrateur introuvable.')
  }

  const response = await request<AdminSupportSession>(
    `/admin/organizations/${organizationId}/support-session`,
    {
      method: 'POST',
      body: JSON.stringify({ reason }),
      organizationId: null,
    },
  )

  sessionStorage.setItem(ORIGINAL_ADMIN_TOKEN_KEY, adminToken)
  setAccessToken(response.access_token)
  setStoredOrganizationId(response.organization_id)
  sessionStorage.setItem(
    SUPPORT_MODE_KEY,
    JSON.stringify({
      session_id: response.session_id,
      organization_id: response.organization_id,
      organization_name: response.organization_name,
      expires_at: response.expires_at,
    } satisfies SupportModeState),
  )
  return response
}

export async function endAdminSupportMode() {
  const state = getSupportMode()
  try {
    if (state) {
      await request<void>('/auth/support/end', {
        method: 'POST',
        organizationId: null,
      })
    }
  } finally {
    restoreOriginalAdminSession()
  }
}


export type OnboardingStep = {
  key: 'school' | 'identity' | 'address' | 'matricule' | 'team' | 'billing' | 'formation'
  label: string
  description: string
  completed: boolean
  available: boolean
  path: string
}

export type OnboardingStatus = {
  completed_steps: number
  total_steps: number
  progress_percent: number
  is_complete: boolean
  next_step: OnboardingStep | null
  steps: OnboardingStep[]
}

export const getOnboardingStatus = () =>
  request<OnboardingStatus>('/onboarding/status')

export type FormationSummary = {
  id: number
  organization_id: number
  slug: string
  title: string
  description: string
  category: string
  level: string
  format_type: 'live' | 'ligne' | 'presentiel'
  training_hours: number | null
  short_description: string
  cover_image_url: string | null
  presentation_video_url: string | null
  objectives: string
  prerequisites: string
  public_program: string
  price_cents: number
  currency: string
  allow_installments: boolean
  installment_count: number
  reservation_deposit_enabled: boolean
  reservation_deposit_percent: number
  is_featured: boolean
  featured_order: number
  status: 'draft' | 'published' | 'archived'
  publication_issues: string[]
  session_count: number
  teacher_count: number
  student_count: number
  course_count: number
  created_at: string
  /** The session running now or starting next (none for online formations). */
  next_session?: {
    id: number
    label: string
    start_date: string
    end_date: string
    enrolled_count: number
    seat_capacity: number
  } | null
}

export type SessionTeacher = {
  id: number
  teacher_id: number
  teacher_name: string
  teacher_email: string
  role: 'principal' | 'intervenant'
  assigned_at: string
}

export type Enrollment = {
  id: number
  student_id: number
  student_name: string
  student_email: string
  student_avatar_url?: string | null
  status: 'active' | 'completed' | 'cancelled'
  created_at: string
}

export type Lesson = {
  id: number
  title: string
  order_index: number
  lesson_type: 'text' | 'video' | 'pdf' | 'quiz' | 'assignment' | 'resource'
  publication_status: 'draft' | 'published'
  version_number: number
  content: string | null
  video_url: string | null
  file_url: string | null
  quiz_id: number | null
  assignment_id: number | null
  resource_id: number | null
  available_at: string | null
}

export type Chapter = {
  id: number
  title: string
  order_index: number
  lessons: Lesson[]
}

export type Course = {
  id: number
  title: string
  description: string
  teacher_id: number | null
  teacher_name: string | null
  status: 'draft' | 'published' | 'archived'
  chapters: Chapter[]
  created_at: string
}

export type FormationSession = {
  program_frozen_at?: string | null
  program_missing?: string[]
  id: number
  label: string
  start_date: string
  end_date: string
  campus_label: string | null
  seat_capacity: number
  enrollment_open_at: string | null
  enrollment_close_at: string | null
  price_override_cents: number | null
  status: 'planned' | 'open' | 'completed' | 'cancelled'
  teachers: SessionTeacher[]
  enrollments: Enrollment[]
  courses: Course[]
  created_at: string
}

export type FormationDetail = FormationSummary & {
  sessions: FormationSession[]
}

export const listFormations = () =>
  request<FormationSummary[]>('/formations')

export const getFormation = (formationId: number) =>
  request<FormationDetail>(`/formations/${formationId}`)

export const createFormation = (payload: {
  slug: string
  title: string
  description?: string
  category?: string
  level?: string
  format_type?: 'live' | 'ligne' | 'presentiel'
  training_hours?: number | null
  short_description?: string
  cover_image_url?: string | null
  presentation_video_url?: string | null
  objectives?: string
  prerequisites?: string
  public_program?: string
  price_cents?: number
  currency?: string
  allow_installments?: boolean
  installment_count?: number
  is_featured?: boolean
  featured_order?: number
  status?: 'draft' | 'published'
}) =>
  withAddonConsent((accept) => request<FormationSummary>(`/formations${addonQuery(accept)}`, {
    method: 'POST',
    body: JSON.stringify({
      ...payload,
      description: payload.description ?? '',
    }),
  }))

export const updateFormation = (
  formationId: number,
  payload: Partial<Pick<
    FormationSummary,
    'title' | 'description' | 'category' | 'level' | 'format_type' | 'training_hours' |
    'short_description' | 'cover_image_url' | 'presentation_video_url' | 'objectives' | 'prerequisites' |
    'public_program' | 'price_cents' | 'currency' | 'allow_installments' |
    'installment_count' | 'reservation_deposit_enabled' | 'reservation_deposit_percent' |
    'is_featured' | 'featured_order' | 'status'
  >>,
) =>
  withAddonConsent((accept) => request<FormationSummary>(`/formations/${formationId}${addonQuery(accept)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  }))

export const createFormationSession = (
  formationId: number,
  payload: {
    label: string
    start_date: string
    end_date: string
    campus_label?: string | null
    seat_capacity?: number
    enrollment_open_at?: string | null
    enrollment_close_at?: string | null
    price_override_cents?: number | null
    status?: 'planned' | 'open'
    /** Take back the courses, activities (as drafts) and, if asked, the teachers of an earlier session. */
    copy_content_from_session_id?: number | null
    copy_teachers?: boolean
  },
) =>
  request<FormationDetail>(`/formations/${formationId}/sessions`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })


export const updateFormationSession = (
  formationId: number,
  sessionId: number,
  payload: Partial<{
    label: string
    start_date: string
    end_date: string
    campus_label: string | null
    seat_capacity: number
    enrollment_open_at: string | null
    enrollment_close_at: string | null
    price_override_cents: number | null
    status: 'planned' | 'open' | 'completed' | 'cancelled'
  }>,
) =>
  request<FormationDetail>(`/formations/${formationId}/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })

export const updateFormationEnrollment = (
  formationId: number,
  sessionId: number,
  enrollmentId: number,
  status: Enrollment['status'],
) =>
  request<FormationDetail>(`/formations/${formationId}/sessions/${sessionId}/enrollments/${enrollmentId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })

export const assignSessionTeacher = (
  formationId: number,
  sessionId: number,
  userId: number,
  role: 'principal' | 'intervenant',
) =>
  request<FormationDetail>(
    `/formations/${formationId}/sessions/${sessionId}/teachers`,
    {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, role }),
    },
  )

export const removeSessionTeacher = (
  formationId: number,
  sessionId: number,
  teacherId: number,
) =>
  request<FormationDetail>(
    `/formations/${formationId}/sessions/${sessionId}/teachers/${teacherId}`,
    { method: 'DELETE' },
  )

export const createSessionCourse = (
  formationId: number,
  sessionId: number,
  payload: {
    title: string
    description?: string
    teacher_id?: number | null
  },
) =>
  request<FormationDetail>(
    `/formations/${formationId}/sessions/${sessionId}/courses`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )

export const createCourseChapter = (
  formationId: number,
  sessionId: number,
  courseId: number,
  payload: { title: string; order_index?: number },
) =>
  request<FormationDetail>(
    `/formations/${formationId}/sessions/${sessionId}/courses/${courseId}/chapters`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )

export const createChapterLesson = (
  formationId: number,
  sessionId: number,
  courseId: number,
  chapterId: number,
  payload: {
    title: string
    order_index?: number
    lesson_type?: Lesson['lesson_type']
    content?: string | null
    video_url?: string | null
    file_url?: string | null
    quiz_id?: number | null
    assignment_id?: number | null
    resource_id?: number | null
    available_at?: string | null
  },
) =>
  request<FormationDetail>(
    `/formations/${formationId}/sessions/${sessionId}/courses/${courseId}/chapters/${chapterId}/lessons`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )

export type LessonPayload = Parameters<typeof createChapterLesson>[4]

export type LessonVersion = {
  id: number
  lesson_id: number
  version_number: number
  snapshot: LessonPayload & { publication_status: Lesson['publication_status'] }
  reason: 'initial' | 'created' | 'edited' | 'published' | 'restored'
  edited_by_user_id: number | null
  created_at: string
}

const lessonPath = (formationId: number, sessionId: number, courseId: number, chapterId: number, lessonId: number) =>
  `/formations/${formationId}/sessions/${sessionId}/courses/${courseId}/chapters/${chapterId}/lessons/${lessonId}`

export const listLessonVersions = (formationId: number, sessionId: number, courseId: number, chapterId: number, lessonId: number) =>
  request<LessonVersion[]>(`${lessonPath(formationId, sessionId, courseId, chapterId, lessonId)}/versions`)

export const restoreLessonVersion = (formationId: number, sessionId: number, courseId: number, chapterId: number, lessonId: number, versionNumber: number) =>
  request<FormationDetail>(`${lessonPath(formationId, sessionId, courseId, chapterId, lessonId)}/versions/${versionNumber}/restore`, { method: 'POST' })

export const updateSessionCourse = (formationId: number, sessionId: number, courseId: number, payload: { status: Course['status'] }) =>
  request<FormationDetail>(`/formations/${formationId}/sessions/${sessionId}/courses/${courseId}`, {
    method: 'PATCH', body: JSON.stringify(payload),
  })

export const updateChapterLesson = (formationId: number, sessionId: number, courseId: number, chapterId: number, lessonId: number, payload: LessonPayload) =>
  request<FormationDetail>(`/formations/${formationId}/sessions/${sessionId}/courses/${courseId}/chapters/${chapterId}/lessons/${lessonId}`, {
    method: 'PUT', body: JSON.stringify(payload),
  })

export const publishChapterLesson = (formationId: number, sessionId: number, courseId: number, chapterId: number, lessonId: number) =>
  request<FormationDetail>(`/formations/${formationId}/sessions/${sessionId}/courses/${courseId}/chapters/${chapterId}/lessons/${lessonId}/publish`, {
    method: 'POST',
  })


export type TeacherWorkspaceSession = {
  formation_id: number
  formation_title: string
  formation_image: string | null
  format_type: 'ligne' | 'live' | 'presentiel'
  session_id: number
  session_label: string
  start_date: string
  end_date: string
  campus_label: string | null
  seat_capacity: number
  status: string
  assignment_role: 'principal' | 'intervenant'
  student_count: number
  course_count: number
}

export type TeacherWorkspace = {
  teacher_code: string
  sessions: TeacherWorkspaceSession[]
  total_sessions: number
  total_students: number
  total_courses: number
}

export type StudentWorkspaceSession = {
  enrollment_id: number
  formation_id: number
  formation_title: string
  formation_image: string | null
  format_type: 'ligne' | 'live' | 'presentiel'
  dashboard_type: 'classic' | 'guided'
  session_id: number
  session_label: string
  start_date: string
  end_date: string
  teacher_name: string | null
  campus_label: string | null
  session_status: string
  enrollment_status: string
  course_count: number
}

export type StudentWorkspace = {
  student_code: string | null
  sessions: StudentWorkspaceSession[]
  total_sessions: number
  total_courses: number
}

export const getTeacherWorkspace = () =>
  request<TeacherWorkspace>('/workspace/teacher')

export const getStudentWorkspace = () =>
  request<StudentWorkspace>('/workspace/student')


export type CourseDay = {
  id: number
  session_id: number
  teacher_id: number | null
  teacher_name: string | null
  title: string
  scheduled_at: string
  duration_minutes: number
  status: 'planned' | 'cancelled'
  started_at: string | null
  delivery_status: 'held' | 'partial' | 'not_held' | 'interrupted' | null
  report_summary: string | null
  report_difficulties: string | null
  report_homework: string | null
  report_attendance_notes: string | null
  report_submitted_at: string | null
  feedback_count: number
  average_rating: number | null
  my_feedback: CourseDayFeedback | null
  can_edit: boolean
  created_at: string
}

export type SessionPlanning = {
  session_id: number
  formation_id: number
  formation_title: string
  format_type: 'ligne' | 'live' | 'presentiel'
  live_enabled: boolean
  session_label: string
  session_start_date: string
  session_end_date: string
  course_days: CourseDay[]
}

export const getSessionPlanning = (sessionId: number) =>
  request<SessionPlanning>(`/planning/sessions/${sessionId}/course-days`)

export type LiveRecording = {
  id: number
  session_id: number
  course_day_id: number
  title: string
  description: string | null
  status: 'processing' | 'ready' | 'failed' | 'archived'
  duration_seconds: number | null
  uploaded_at: string | null
  is_published: boolean
  download_allowed: boolean
  content_url: string | null
}

export const listLiveRecordings = (sessionId: number) =>
  request<LiveRecording[]>(`/live-recordings/sessions/${sessionId}`)

export const updateLiveRecording = (recordingId: number, payload: {
  title?: string
  description?: string
  is_published?: boolean
  download_allowed?: boolean
}) => request<LiveRecording>(`/live-recordings/${recordingId}`, {
  method: 'PATCH', body: JSON.stringify(payload),
})

export const retryLiveRecording = (recordingId: number) =>
  request<{ status: string }>(`/live-recordings/${recordingId}/retry`, { method: 'POST' })

export const archiveLiveRecording = (recordingId: number) =>
  request<void>(`/live-recordings/${recordingId}`, { method: 'DELETE' })

export const submitCourseDayReport = (courseDayId: number, payload: {
  delivery_status: 'held' | 'partial' | 'not_held' | 'interrupted'
  summary: string
  difficulties?: string
  homework?: string
  attendance_notes?: string
}) =>
  request<SessionPlanning>(`/planning/course-days/${courseDayId}/report`, { method: 'POST', body: JSON.stringify(payload) })

export type CourseDayFeedback = {
  id: number
  rating: number
  delivery_status: 'held' | 'partial' | 'not_held'
  comment: string | null
  created_at: string
  updated_at: string
}

export type CourseDayFeedbackReview = CourseDayFeedback & { student_name: string }

export const submitCourseDayFeedback = (courseDayId: number, payload: { rating: number; delivery_status: CourseDayFeedback['delivery_status']; comment: string }) =>
  request<SessionPlanning>(`/planning/course-days/${courseDayId}/feedback`, { method: 'POST', body: JSON.stringify(payload) })

export const listCourseDayFeedback = (courseDayId: number) =>
  request<CourseDayFeedbackReview[]>(`/planning/course-days/${courseDayId}/feedback`)

export type SchoolCourseDayReport = {
  course_day_id: number
  session_id: number
  formation_id?: number | null
  formation_title: string
  session_label: string
  teacher_id?: number | null
  teacher_name: string | null
  title: string
  scheduled_at: string
  delivery_status: 'held' | 'partial' | 'not_held' | 'interrupted'
  summary: string
  difficulties: string | null
  homework: string | null
  attendance_notes: string | null
  submitted_at: string
  feedback_count: number
  average_rating: number | null
}

export const listSchoolCourseDayReports = () => request<SchoolCourseDayReport[]>('/planning/reports')

/** A course day over whose teacher has not written the report yet. */
export type SchoolMissingCourseDayReport = {
  course_day_id: number
  session_id: number
  formation_id: number
  formation_title: string
  session_label: string
  teacher_id: number | null
  teacher_name: string | null
  title: string
  scheduled_at: string
  ends_at: string
}

export const listSchoolMissingCourseDayReports = () =>
  request<SchoolMissingCourseDayReport[]>('/planning/reports/missing')

export type LiveRoom = {
  course_day_id: number
  title: string
  school_name: string
  school_logo_url: string | null
  starts_at: string
  ends_at: string
  domain: string
  room_name: string
  external_api_url: string
  token: string
  moderator: boolean
  started_at: string | null
  /** When the room ends for everyone (4 h at most, the month's live hours); null: no forced end. */
  ends_by?: string | null
}

/** The live room before entering: waiting room until opens_at, then the welcome card. */
export type LiveRoomInfo = {
  course_day_id: number
  title: string
  formation_title: string
  session_label: string
  formation_image_url: string | null
  school_name: string
  school_logo_url: string | null
  school_primary_color: string | null
  starts_at: string
  ends_at: string
  opens_at: string
  closes_at: string
  started_at: string | null
  moderator: boolean
  responsible_teacher: boolean
  ends_by?: string | null
  /** The school's live minutes left this month, when its plan counts them (Découverte). */
  live_minutes_left?: number | null
}

export const fetchLiveRoomInfo = (courseDayId: number) =>
  request<LiveRoomInfo>(`/planning/course-days/${courseDayId}/live`)

/** This browser in live classes: a student keeps one device at a time, as on the mother site. */
export type LiveDevice = { id: string; label: string }

const liveDeviceHeaders = (device: LiveDevice) => ({ 'X-Live-Device-Id': device.id, 'X-Live-Device-Label': device.label })

export const joinLiveClass = (courseDayId: number, device: LiveDevice) =>
  request<LiveRoom>(`/planning/course-days/${courseDayId}/live/join`, { method: 'POST', headers: liveDeviceHeaders(device) })

/** The latest roll call: open for two minutes; the teacher also gets how many answered. */
export type LiveRollCall = {
  id: number
  started_at: string
  closes_at: string
  open: boolean
  answered: boolean
  answers_count: number | null
}

export const heartbeatLiveClass = (courseDayId: number, device: LiveDevice) =>
  request<{ roll_call: LiveRollCall | null; ends_by?: string | null }>(`/planning/course-days/${courseDayId}/live/heartbeat`, { method: 'POST', headers: liveDeviceHeaders(device) })

export const startLiveRollCall = (courseDayId: number) =>
  request<LiveRollCall>(`/planning/course-days/${courseDayId}/live/roll-call`, { method: 'POST' })

export const answerLiveRollCall = (courseDayId: number, rollCallId: number) =>
  request<void>(`/planning/course-days/${courseDayId}/live/roll-call/${rollCallId}/answer`, { method: 'POST' })

/** Frees the device at once; keepalive lets it leave with a closing page. */
export const leaveLiveClass = (courseDayId: number, device: LiveDevice) =>
  request<void>(`/planning/course-days/${courseDayId}/live/leave`, { method: 'POST', headers: liveDeviceHeaders(device), keepalive: true })

export const startLiveClass = (courseDayId: number) =>
  request<{ course_day_id: number; started_at: string; closes_at?: string | null; ends_by?: string | null }>(`/planning/course-days/${courseDayId}/live/start`, { method: 'POST' })

export const createSessionCourseDay = (
  sessionId: number,
  payload: {
    title: string
    scheduled_at: string
    duration_minutes: number
  },
) =>
  request<SessionPlanning>(`/planning/sessions/${sessionId}/course-days`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export const publishSessionCourseDayDraft = (
  sessionId: number,
  days: Array<{
    title: string
    scheduled_at: string
    duration_minutes: number
  }>,
) =>
  request<SessionPlanning>(
    `/planning/sessions/${sessionId}/course-days/publish-draft`,
    {
      method: 'POST',
      body: JSON.stringify({ days }),
    },
  )

export const updateSessionCourseDay = (
  courseDayId: number,
  payload: {
    title?: string
    scheduled_at?: string
    duration_minutes?: number
    status?: 'planned' | 'cancelled'
  },
) =>
  request<SessionPlanning>(`/planning/course-days/${courseDayId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })


export type AssignmentRubricCriterion = {
  label: string
  points: number
  description: string
}

export type AssignmentBrief = {
  context: string
  objective: string
  deliverables: string[]
  steps: string[]
  evaluation_criteria: AssignmentRubricCriterion[]
  submission_method: string
  tips: string[]
}

export type Assignment = {
  id: number
  session_id: number
  course_day_id: number | null
  teacher_id: number | null
  teacher_name: string | null
  title: string
  publication_status: 'draft' | 'published'
  instructions: string
  brief: AssignmentBrief | null
  due_date: string
  is_final_project: boolean
  submissions_count: number
  created_at: string
  can_manage: boolean
  delete_blocked_reason: string | null
}

export type AssignmentPayload = {
  title: string
  instructions: string
  brief?: AssignmentBrief | null
  due_date: string
  course_day_id?: number | null
  is_final_project?: boolean
}

export type StudentAssignmentStatus = 'pending' | 'submitted' | 'late' | 'reviewed'

export type StudentAssignment = {
  id: number
  enrollment_id: number
  session_id: number
  session_label: string
  formation_title: string
  teacher_name: string | null
  title: string
  instructions: string
  brief: AssignmentBrief | null
  is_locked: boolean
  available_at: string | null
  due_date: string
  is_final_project: boolean
  student_status: StudentAssignmentStatus
  submitted_at: string | null
  file_url: string | null
  is_reviewed: boolean
  review_score: number | null
  review_max_score: number
  comment_count: number
  /** Live and presentiel: the session is over, nothing more can be handed in. */
  submissions_closed?: boolean
}

export type AssignmentSubmission = {
  id: number
  enrollment_id: number
  student_name: string
  file_url: string
  submitted_at: string
  is_reviewed: boolean
  review_score: number | null
  review_max_score: number
  comment_count: number
}

export type AssignmentComment = {
  id: number
  assignment_id: number
  enrollment_id: number
  author_role: 'student' | 'teacher'
  author_name: string
  body: string
  attachment_url: string | null
  created_at: string
}

export const listTeacherAssignments = (sessionId: number) =>
  request<Assignment[]>('/assignments/teacher/sessions/' + sessionId)

export const createTeacherAssignment = (sessionId: number, payload: AssignmentPayload) =>
  request<Assignment>('/assignments/teacher/sessions/' + sessionId, {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export const updateTeacherAssignment = (assignmentId: number, payload: Partial<AssignmentPayload>) =>
  request<Assignment>('/assignments/teacher/' + assignmentId, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })

export const publishTeacherAssignment = (assignmentId: number) =>
  request<Assignment>('/assignments/teacher/' + assignmentId + '/publish', { method: 'POST' })

export const deleteTeacherAssignment = (assignmentId: number) =>
  request<void>('/assignments/teacher/' + assignmentId, { method: 'DELETE' })

export const listAssignmentSubmissions = (assignmentId: number) =>
  request<AssignmentSubmission[]>('/assignments/teacher/' + assignmentId + '/submissions')

export const reviewAssignmentSubmission = (
  assignmentId: number,
  submissionId: number,
  reviewScore: number,
) =>
  request<AssignmentSubmission>(
    '/assignments/teacher/' + assignmentId + '/submissions/' + submissionId,
    {
      method: 'PATCH',
      body: JSON.stringify({ review_score: reviewScore }),
    },
  )

export const listStudentAssignments = () =>
  request<StudentAssignment[]>('/assignments/student')

export const submitStudentAssignment = (
  assignmentId: number,
  fileUrl: string,
) =>
  request<StudentAssignment>('/assignments/student/' + assignmentId + '/submit', {
    method: 'POST',
    body: JSON.stringify({ file_url: fileUrl }),
  })

export const listAssignmentComments = (
  assignmentId: number,
  enrollmentId: number,
) =>
  request<AssignmentComment[]>(
    '/assignments/' + assignmentId + '/enrollments/' + enrollmentId + '/comments',
  )

export const createAssignmentComment = (
  assignmentId: number,
  enrollmentId: number,
  payload: { body?: string; attachment_url?: string | null },
) =>
  request<AssignmentComment>(
    '/assignments/' + assignmentId + '/enrollments/' + enrollmentId + '/comments',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )

export async function uploadAssignmentAsset(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request<{
    filename: string
    public_url: string
    size: number
    content_type: string
  }>('/assignments/assets', {
    method: 'POST',
    body: form,
  })
}

export async function uploadSubmissionAsset(file: File) {
  const body = new FormData()
  body.append('file', file)
  return request<{ filename: string; public_url: string; size: number; content_type: string }>(
    '/assignments/submission-assets',
    { method: 'POST', body },
  )
}

export async function openAssignmentSubmission(url: string) {
  const parsed = new URL(url, window.location.origin)
  const marker = '/assignments/submission-assets/'
  const index = parsed.pathname.indexOf(marker)
  const legacyMatch = parsed.pathname.match(/\/schools\/\d+\/assignments\/([a-f0-9]{32}\.[a-z0-9]+)$/)
  const legacyPrivateMatch = parsed.pathname.match(/\/assignments\/legacy-submissions\/([a-f0-9]{32}\.[a-z0-9]+)$/)
  if (index < 0 && !legacyMatch && !legacyPrivateMatch) {
    window.open(url, '_blank', 'noopener,noreferrer')
    return
  }
  const path = index >= 0 ? parsed.pathname.slice(index) : '/assignments/legacy-submissions/' + (legacyMatch || legacyPrivateMatch)![1]
  const blob = await requestBlob(path)
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = parsed.pathname.split('/').pop() || 'devoir'
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
}

export async function openTeacherResource(url: string) {
  const parsed = new URL(url, window.location.origin)
  const privateMatch = parsed.pathname.match(/\/assignments\/resource-assets\/([a-f0-9]{32}\.[a-z0-9]+)$/)
  const legacyMatch = parsed.pathname.match(/\/schools\/\d+\/assignments\/([a-f0-9]{32}\.[a-z0-9]+)$/)
  const filename = privateMatch?.[1] || legacyMatch?.[1]
  if (!filename) {
    window.open(url, '_blank', 'noopener,noreferrer')
    return
  }
  const blob = await requestBlob('/assignments/resource-assets/' + filename)
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
}


export type AcademicResource = {
  id: number
  session_id: number
  course_day_id: number | null
  teacher_id: number | null
  teacher_name: string | null
  formation_title: string
  session_label: string
  title: string
  resource_type: 'link' | 'pdf' | 'image' | 'video' | 'file'
  url: string
  published_at: string | null
  created_at: string
}

export const listTeacherResources = (sessionId: number) =>
  request<AcademicResource[]>('/academic/teacher/sessions/' + sessionId + '/resources')

export const createTeacherResource = (
  sessionId: number,
  payload: {
    title: string
    resource_type: AcademicResource['resource_type']
    url: string
    course_day_id?: number | null
    publish_now?: boolean
  },
) =>
  request<AcademicResource>('/academic/teacher/sessions/' + sessionId + '/resources', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export const listStudentResources = () =>
  request<AcademicResource[]>('/academic/student/resources')

export type TeacherQuizQuestion = {
  id: number
  order_index: number
  text: string
  options: string[]
  correct_index: number
  selection_mode?: 'single' | 'multiple'
  correct_indices?: number[]
  points?: number
}

export type TeacherQuiz = {
  id: number
  session_id: number
  course_day_id: number | null
  teacher_id: number | null
  teacher_name: string | null
  title: string
  assessment_type: 'quiz' | 'exam'
  duration_minutes: number | null
  scheduled_at: string | null
  status: 'draft' | 'active' | 'closed'
  pass_pct: number
  questions: TeacherQuizQuestion[]
  attempts_count: number
  created_at: string
}

export type StudentQuizQuestion = {
  id: number
  order_index: number
  text: string
  options: string[]
  selection_mode?: 'single' | 'multiple'
  points?: number
}

export type QuizAttempt = {
  id: number
  attempt_number: number
  score_pct: number
  submitted_at: string
  /** Options ticked per question, in the student's order; empty when unanswered. */
  submitted_answers: number[][]
  /** Right options per question: one, or several for a multiple-answer question. */
  correct_answers: number[][]
}

export type StudentQuiz = {
  id: number
  session_id: number
  enrollment_id: number
  formation_title: string
  session_label: string
  teacher_name: string | null
  title: string
  assessment_type: 'quiz' | 'exam'
  duration_minutes: number | null
  scheduled_at: string | null
  available_at: string | null
  is_locked: boolean
  pass_pct: number
  questions: StudentQuizQuestion[]
  attempts: QuizAttempt[]
  best_score_pct: number | null
  passed: boolean
  can_attempt: boolean
  attempts_remaining: number
  next_attempt_available_at: string | null
  pdf_reading_pct: number | null
  pdf_reading_locked: boolean
  /** Live and presentiel: the session is over, no more attempts. */
  work_closed?: boolean
}

export type TeacherQuizResults = {
  quiz_id: number
  title: string
  total_students: number
  attempts: Array<{
    enrollment_id: number
    student_name: string
    attempt_number: number
    score_pct: number
    submitted_at: string
  }>
}

export const listTeacherQuizzes = (sessionId: number) =>
  request<TeacherQuiz[]>('/academic/teacher/sessions/' + sessionId + '/quizzes')

export const createTeacherQuiz = (
  sessionId: number,
  payload: {
    title: string
    assessment_type: 'quiz' | 'exam'
    duration_minutes?: number | null
    scheduled_at?: string | null
    course_day_id?: number | null
    pass_pct?: number
    questions: Array<{
      text: string
      options: string[]
      correct_index: number
      selection_mode?: 'single' | 'multiple'
      correct_indices?: number[]
      points?: number
    }>
  },
) =>
  request<TeacherQuiz>('/academic/teacher/sessions/' + sessionId + '/quizzes', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export const updateTeacherQuizStatus = (
  quizId: number,
  status: 'draft' | 'active' | 'closed',
) =>
  request<TeacherQuiz>('/academic/teacher/quizzes/' + quizId, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })

export const getTeacherQuizResults = (quizId: number) =>
  request<TeacherQuizResults>('/academic/teacher/quizzes/' + quizId + '/results')

export const listStudentQuizzes = () =>
  request<StudentQuiz[]>('/academic/student/quizzes')

/** One entry per question: an option (-1 when unanswered), or the options ticked for a multiple-answer question. */
export const submitStudentQuizAttempt = (quizId: number, answers: Array<number | number[]>) =>
  request<StudentQuiz>('/academic/student/quizzes/' + quizId + '/attempt', {
    method: 'POST',
    body: JSON.stringify({ answers }),
  })

export type LearningLesson = {
  id: number
  title: string
  order_index: number
  lesson_type: string
  content: string | null
  video_url: string | null
  file_url: string | null
  quiz_id: number | null
  assignment_id: number | null
  resource_id: number | null
  available_at: string | null
  is_locked: boolean
  completed: boolean
  video_watched_pct: number
}

export type LearningChapter = {
  id: number
  title: string
  order_index: number
  lessons: LearningLesson[]
}

export type LearningCourse = {
  id: number
  title: string
  description: string
  teacher_name: string | null
  chapters: LearningChapter[]
}

export type LearningSession = {
  enrollment_id: number
  session_id: number
  formation_id: number
  formation_title: string
  format_type: 'ligne' | 'live' | 'presentiel'
  dashboard_type: 'classic' | 'guided'
  session_label: string
  is_locked: boolean
  available_at: string | null
  courses: LearningCourse[]
}

export const listStudentLearning = () =>
  request<LearningSession[]>('/academic/student/learning')

export type PdfLessonProgress = {
  page_count: number
  viewed_pages: number[]
  viewed_pct: number
  last_page: number
  quiz_unlocked: boolean
  is_completed: boolean
}

export const uploadLessonPdf = (file: File) => {
  const body = new FormData()
  body.append('file', file)
  return request<{ source_url: string; page_count: number }>('/academic/teacher/pdf-assets', { method: 'POST', body })
}

export const fetchLessonPdf = (lessonId: number) =>
  requestBlob('/academic/student/lessons/' + lessonId + '/pdf-file')

export const getLessonPdfProgress = (lessonId: number) =>
  request<PdfLessonProgress>('/academic/student/lessons/' + lessonId + '/pdf-progress')

export const reportLessonPdfPage = (lessonId: number, page: number, event: 'open' | 'confirm') =>
  request<PdfLessonProgress>('/academic/student/lessons/' + lessonId + '/pdf-progress', {
    method: 'POST', body: JSON.stringify({ page, event }),
  })

export const completeStudentLesson = (lessonId: number) =>
  request<LearningSession>('/academic/student/lessons/' + lessonId + '/complete', {
    method: 'POST',
  })

export const reportStudentLessonVideoProgress = (
  lessonId: number,
  payload: {
    current_time_seconds: number
    duration_seconds: number
    playback_rate: number
    event: 'heartbeat' | 'seek' | 'ended'
  },
) => request<LearningSession>('/academic/student/lessons/' + lessonId + '/video-progress', {
  method: 'POST',
  body: JSON.stringify(payload),
})

export type AttendanceCourseDay = {
  course_day_id: number
  session_id: number
  title: string
  scheduled_at: string
  teacher_id: number | null
  teacher_name: string | null
  can_edit: boolean
  edit_blocked_reason: string | null
  locks_at: string | null
  delivery_status: 'held' | 'partial' | 'not_held' | 'interrupted' | null
  report_submitted_at: string | null
  rows: Array<{
    enrollment_id: number
    student_id: number
    student_name: string
    student_avatar_url?: string | null
    status: AttendanceStatus | null
    /** Live classes: minutes in the room and roll calls answered, to check the prefilled attendance. */
    live_minutes?: number | null
    live_roll_calls_answered?: number | null
  }>
  live_roll_calls?: number | null
}

export type AttendanceStatus = 'present' | 'late' | 'absent' | 'excused'

export const ATTENDANCE_LABELS: Record<AttendanceStatus, string> = {
  present: 'Présent',
  late: 'En retard',
  absent: 'Absent',
  excused: 'Excusé',
}

export type StudentAttendance = {
  course_day_id: number
  title: string
  scheduled_at: string
  status: AttendanceStatus | null
}

export const getTeacherAttendance = (sessionId: number) =>
  request<AttendanceCourseDay[]>('/academic/teacher/sessions/' + sessionId + '/attendance')

export const markTeacherAttendance = (
  courseDayId: number,
  enrollmentId: number,
  status: AttendanceStatus,
) =>
  request<AttendanceCourseDay>('/academic/teacher/course-days/' + courseDayId + '/attendance', {
    method: 'PUT',
    body: JSON.stringify({ enrollment_id: enrollmentId, status }),
  })

export const listStudentAttendance = () =>
  request<StudentAttendance[]>('/academic/student/attendance')

export type StudentGrade = {
  id: number
  session_id: number
  label: string
  source_type: string
  score: number
  max_score: number
  note: string
  created_at: string
}

export const listStudentGrades = () =>
  request<StudentGrade[]>('/academic/student/grades')

export type TeacherGradebook = {
  session_id: number
  can_grade_session: boolean
  students: Array<{ enrollment_id: number; student_name: string; student_avatar_url?: string | null }>
  course_days: Array<{ id: number; title: string; scheduled_at: string; can_grade: boolean }>
  grades: Array<{
    id: number
    enrollment_id: number
    student_name: string
    student_avatar_url?: string | null
    course_day_id: number | null
    course_day_title: string | null
    teacher_name: string | null
    is_own: boolean
    source_type: string
    label: string
    score: number
    max_score: number
    note: string
  }>
}

export const getTeacherGradebook = (sessionId: number) =>
  request<TeacherGradebook>('/academic/teacher/sessions/' + sessionId + '/grades')

export const saveTeacherGrades = (
  sessionId: number,
  entries: Array<{
    enrollment_id: number
    course_day_id: number | null
    label: string
    score: number
    max_score: number
  }>,
) =>
  request<TeacherGradebook>('/academic/teacher/sessions/' + sessionId + '/grades', {
    method: 'PUT',
    body: JSON.stringify(entries),
  })

export type StudentBadge = {
  level: 'aventurier' | 'debutant' | 'intermediaire' | 'semi_pro' | 'professionnel'
  label: string
  score_pct: number
  next_level: string | null
  lesson_progress_pct: number
  assignment_progress_pct: number | null
  quiz_progress_pct: number | null
  attendance_pct: number | null
  grade_average_pct: number | null
  final_project_validated: boolean
  missing_requirements: string[]
  ring_pct: number
  /** What the badge rests on while quizzes or TPs are still few. */
  basis_note?: string | null
  /** Open work not due yet: done in time, it counts for the badge. */
  upcoming?: Array<{ kind: 'quiz' | 'assignment'; title: string; due_at: string; overdue?: boolean }>
}

export type StudentProgress = {
  enrollment_id: number
  session_id: number
  formation_title: string
  session_label: string
  completed_lessons: number
  total_lessons: number
  lesson_progress_pct: number
  submitted_assignments: number
  total_assignments: number
  attempted_quizzes: number
  total_quizzes: number
  attendance_present: number
  attendance_total: number
  grade_average_pct: number | null
  badge: StudentBadge
}

export const listStudentProgress = () =>
  request<StudentProgress[]>('/academic/student/progress')

export type TeacherPerformance = {
  total_sessions: number
  total_students: number
  attendance_rate_pct: number | null
  pending_reviews_count: number
  sessions: Array<{
    session_id: number
    formation_title: string
    session_label: string
    enrolled_count: number
    progress_pct: number
    attendance_rate_pct: number | null
    quiz_average_score_pct: number | null
    badge_hint?: string | null
    low_attendance_count?: number
    pending_reviews_count: number
  }>
}

export const getTeacherPerformance = () =>
  request<TeacherPerformance>('/academic/teacher/performance')

export type StudentClass = {
  session_id: number
  formation_title: string
  session_label: string
  classmates: Array<{
    user_id: number
    enrollment_id: number
    full_name: string
    avatar_url: string | null
    student_code: string | null
    is_current_user: boolean
    badge: Pick<StudentBadge, 'level' | 'label' | 'ring_pct'>
  }>
}

export type DiscussionPost = {
  id: number
  author: {
    user_id: number
    full_name: string
    avatar_url: string | null
    role: string
    is_current_user: boolean
  }
  body: string
  image_url: string | null
  created_at: string
  replies: Array<{
    id: number
    author: {
      user_id: number
      full_name: string
      avatar_url: string | null
      role: string
      is_current_user: boolean
    }
    body: string
    image_url: string | null
    created_at: string
  }>
}

export const listStudentClasses = () =>
  request<StudentClass[]>('/academic/student/classes')

export const listClassDiscussion = (sessionId: number) =>
  request<DiscussionPost[]>('/academic/classes/' + sessionId + '/discussion')

export async function uploadClassDiscussionImage(sessionId: number, file: File) {
  const body = new FormData()
  body.append('file', file)
  return request<{ filename: string; public_url: string; size: number; content_type: string }>(
    '/academic/classes/' + sessionId + '/discussion/assets',
    { method: 'POST', body },
  )
}

export const createClassDiscussionPost = (
  sessionId: number,
  payload: { body?: string; image_url?: string | null },
) =>
  request<DiscussionPost>('/academic/classes/' + sessionId + '/discussion', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export const createClassDiscussionReply = (
  sessionId: number,
  postId: number,
  payload: { body?: string; image_url?: string | null },
) =>
  request<DiscussionPost['replies'][number]>(
    '/academic/classes/' + sessionId + '/discussion/' + postId + '/replies',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )

export type CertificateInfo = {
  enrollment_id: number
  certificate_number: string
  student_name: string
  formation_title: string
  issued_at: string
  status: string
  verification_token: string
  school_name: string | null
  logo_url: string | null
  primary_color: string | null
  secondary_color: string | null
  student_code: string | null
  session_label: string | null
}

export type CertificateEligibility = {
  enrollment_id: number
  eligible: boolean
  reason: string | null
  certificate: CertificateInfo | null
}

export const getCertificateEligibility = (enrollmentId: number) =>
  request<CertificateEligibility>('/academic/student/enrollments/' + enrollmentId + '/certificate')

export const issueStudentCertificate = (enrollmentId: number) =>
  request<CertificateInfo>('/academic/student/enrollments/' + enrollmentId + '/certificate', {
    method: 'POST',
  })

export const verifyCertificate = (token: string) =>
  request<CertificateInfo>('/academic/certificates/verify/' + encodeURIComponent(token), {
    organizationId: null,
  })

export const downloadStudentCertificatePdf = (enrollmentId: number) =>
  requestBlob('/academic/student/enrollments/' + enrollmentId + '/certificate.pdf')

export const downloadVerifiedCertificatePdf = (token: string) =>
  requestBlob('/academic/certificates/' + encodeURIComponent(token) + '/download', {
    organizationId: null,
  })


export type PublicSiteConfig = {
  site_name: string
  tagline: string
  seo_description: string
  logo_url: string | null
  favicon_url: string | null
  primary_color: string
  secondary_color: string
  accent_color: string
  font_heading: string
  font_body: string
  font_size_scale: number
  heading_size_scale?: number
  subtitle_size_scale?: number
  hero_title: string
  hero_subtitle: string
  hero_cta_label: string
  hero_image_url: string | null
  announcement_enabled: boolean
  announcement_text: string
  announcement_background_color: string
  announcement_text_color: string
  about_title: string
  about_text: string
  contact_phone: string | null
  contact_email: string | null
  contact_address: string | null
  social_links: Record<string, string>
  footer_text: string
  legal_notice: string
  sales_terms: string
  privacy_policy: string
  refund_policy: string
  student_code_prefix: string
  student_code_prefix_confirmed: boolean
  is_published: boolean
}

export type SchoolIdentity = {
  organization_id: number
  organization_name: string
  slug: string
  subdomain: string | null
  public_site: PublicSiteConfig
  legal: {
    legal_name: string
    legal_address: string
    registration_number: string
    tax_number: string
    invoice_email: string | null
    invoice_phone: string | null
    default_currency: string
    invoice_footer: string
  }
  communications: {
    sender_name: string
    reply_to_email: string | null
    email_signature: string
    whatsapp_signature: string
    whatsapp_phone: string | null
  }
  certification: {
    signer_name: string
    signer_title: string
    signature_url: string | null
    stamp_url: string | null
    certificate_footer: string
  }
}

export type PublicSchool = {
  organization_id: number
  slug: string
  subdomain: string | null
  default_currency: string
  name: string
  site_name: string
  tagline: string
  seo_description: string
  logo_url: string | null
  favicon_url: string | null
  primary_color: string
  secondary_color: string
  accent_color: string
  font_heading: string
  font_body: string
  font_size_scale: number
  heading_size_scale?: number
  subtitle_size_scale?: number
  hero_title: string
  hero_subtitle: string
  hero_cta_label: string
  hero_image_url: string | null
  announcement_enabled: boolean
  announcement_text: string
  announcement_background_color: string
  announcement_text_color: string
  about_title: string
  about_text: string
  contact_phone: string | null
  contact_email: string | null
  contact_address: string | null
  social_links: Record<string, string>
  footer_text: string
  legal_notice: string
  sales_terms: string
  privacy_policy: string
  refund_policy: string
  /** Business plans hide the platform's "Powered by" signature. */
  white_label?: boolean
  /** The read-only demonstration school: its site takes no order. */
  is_demo?: boolean
  /** The platform's landing page, where the "Powered by" signature leads. */
  platform_url?: string
}

export type PublicSession = {
  id: number
  label: string
  start_date: string
  end_date: string
  campus_label: string | null
  seat_capacity: number
  seats_remaining: number | null
  enrollment_open_at: string | null
  enrollment_close_at: string | null
  price_cents: number
  currency: string
  current_price_cents: number
  promotion_label: string | null
  promotion_discount_cents: number
  can_purchase: boolean
  unavailable_reason: string | null
  /** How it is paid when bought today, as the checkout will create it. */
  deposit_cents: number | null
  deposit_percent: number | null
  balance_cents: number | null
  balance_due_date: string | null
  schedule_installments: PaymentScheduleLine[]
}

export type PublicFormationCard = {
  id: number
  slug: string
  title: string
  short_description: string
  cover_image_url: string | null
  category: string
  level: string
  format_type: string
  training_hours: number | null
  price_cents: number
  currency: string
  current_price_cents: number
  promotion_label: string | null
  promotion_discount_cents: number
  is_featured: boolean
  featured_order: number
  available_session_count: number
  next_session: PublicSession | null
  can_purchase: boolean
}

export type PublicProgramModule = {
  title: string
  chapters: string[]
}

export type PublicFormationDetail = PublicFormationCard & {
  description: string
  presentation_video_url: string | null
  objectives: string
  prerequisites: string
  public_program: string
  allow_installments: boolean
  installment_count: number
  reservation_deposit_percent: number | null
  modules: PublicProgramModule[]
  sessions: PublicSession[]
  teacher_names: string[]
  /** The teachers' names and photos, for the formation's page. */
  teachers?: Array<{ full_name: string; avatar_url: string | null }>
}

export type PublicHome = {
  school: PublicSchool
  featured_formations: PublicFormationCard[]
}

export const getPublicSchoolHome = (schoolKey: string) =>
  request<PublicHome>('/public/schools/' + encodeURIComponent(schoolKey), {
    organizationId: null,
  })

export const getPublicSchoolIdentity = (schoolKey: string) =>
  request<PublicSchool>('/public/schools/' + encodeURIComponent(schoolKey) + '/identity', {
    organizationId: null,
  })

export const listPublicSchoolFormations = (schoolKey: string) =>
  request<PublicFormationCard[]>('/public/schools/' + encodeURIComponent(schoolKey) + '/formations', {
    organizationId: null,
  })

export const listSchoolFavorites = (schoolKey: string) =>
  request<PublicFormationCard[]>('/public/schools/' + encodeURIComponent(schoolKey) + '/favorites', { organizationId: null })

export const addSchoolFavorite = (schoolKey: string, formationSlug: string) =>
  request<PublicFormationCard[]>('/public/schools/' + encodeURIComponent(schoolKey) + '/favorites/' + encodeURIComponent(formationSlug), {
    method: 'POST', organizationId: null,
  })

export const removeSchoolFavorite = (schoolKey: string, formationSlug: string) =>
  request<PublicFormationCard[]>('/public/schools/' + encodeURIComponent(schoolKey) + '/favorites/' + encodeURIComponent(formationSlug), {
    method: 'DELETE', organizationId: null,
  })

export type SchoolMessageRecipient = { id: number; full_name: string; role: string; avatar_url: string | null }
export type SchoolMessage = { id: number; thread_id: number; sender_user_id: number; sender_name: string; body: string; created_at: string }
export type SchoolMessageThread = { id: number; subject: string; participants: SchoolMessageRecipient[]; last_message: SchoolMessage | null; unread_count: number; last_message_at: string | null }
export type SchoolMessageThreadDetail = SchoolMessageThread & { messages: SchoolMessage[] }

export const listMessageRecipients = () => request<SchoolMessageRecipient[]>('/messages/recipients')
export const listMessageThreads = () => request<SchoolMessageThread[]>('/messages/threads')

export type SchoolMessageStreamEvent =
  | { type: 'messages.summary'; unread_count: number }
  | { type: 'messages.changed'; unread_count: number }

export function subscribeSchoolMessages(onEvent: (event: SchoolMessageStreamEvent) => void): () => void {
  let closed = false
  let socket: WebSocket | null = null
  let retryTimer: number | null = null
  const connect = async () => {
    try {
      const { ticket } = await request<{ ticket: string }>('/messages/ws-ticket')
      if (closed) return
      const url = new URL(`${API_BASE}/messages/ws`, window.location.origin)
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
      socket = new WebSocket(url, ['school-messages', ticket])
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data) as SchoolMessageStreamEvent
          if (event.type === 'messages.summary' || event.type === 'messages.changed') onEvent(event)
        } catch { /* Ignore malformed events and keep the polling fallback. */ }
      }
      socket.onclose = () => {
        socket = null
        if (!closed) retryTimer = window.setTimeout(() => void connect(), 5000)
      }
    } catch {
      if (!closed) retryTimer = window.setTimeout(() => void connect(), 5000)
    }
  }
  void connect()
  return () => {
    closed = true
    if (retryTimer !== null) window.clearTimeout(retryTimer)
    socket?.close()
  }
}

export const getMessageThread = (id: number) => request<SchoolMessageThreadDetail>('/messages/threads/' + id)
export const createMessageThread = (payload: { participant_ids: number[]; subject: string; body: string }) =>
  request<SchoolMessageThreadDetail>('/messages/threads', { method: 'POST', body: JSON.stringify(payload) })
export const sendSchoolMessage = (threadId: number, body: string) =>
  request<SchoolMessage>('/messages/threads/' + threadId + '/messages', { method: 'POST', body: JSON.stringify({ body }) })

export const getPublicSchoolFormation = (schoolKey: string, formationSlug: string) =>
  request<PublicFormationDetail>(
    '/public/schools/' + encodeURIComponent(schoolKey) + '/formations/' + encodeURIComponent(formationSlug),
    { organizationId: null },
  )

export const getSchoolIdentity = () =>
  request<SchoolIdentity>('/commerce/identity')

export const updateSchoolIdentity = (payload: SchoolIdentity) =>
  request<SchoolIdentity>('/commerce/identity', {
    method: 'PUT',
    body: JSON.stringify({
      public_site: payload.public_site,
      legal: payload.legal,
      communications: payload.communications,
      certification: payload.certification,
    }),
  })

export type Promotion = {
  id: number
  name: string
  formation_id: number | null
  session_id: number | null
  discount_type: 'percentage' | 'fixed'
  discount_value: number
  starts_at: string | null
  ends_at: string | null
  max_uses: number | null
  uses_count: number
  is_active: boolean
  created_at: string
}

export type Coupon = {
  id: number
  code: string
  name: string
  discount_type: 'percentage' | 'fixed'
  discount_value: number
  valid_from: string | null
  valid_until: string | null
  max_uses: number | null
  max_uses_per_customer: number
  uses_count: number
  minimum_order_cents: number
  eligible_formation_ids: number[]
  eligible_session_ids: number[]
  allow_on_promotions: boolean
  is_active: boolean
  created_at: string
}

export const listPromotions = () => request<Promotion[]>('/commerce/promotions')
export const createPromotion = (payload: Omit<Promotion, 'id'|'uses_count'|'created_at'>) =>
  request<Promotion>('/commerce/promotions', { method: 'POST', body: JSON.stringify(payload) })
export const setPromotionActive = (id: number, active: boolean) =>
  request<Promotion>('/commerce/promotions/' + id + '?active=' + active, { method: 'PATCH' })

export const listCoupons = () => request<Coupon[]>('/commerce/coupons')
export const createCoupon = (payload: Omit<Coupon, 'id'|'uses_count'|'created_at'>) =>
  request<Coupon>('/commerce/coupons', { method: 'POST', body: JSON.stringify(payload) })
export const setCouponActive = (id: number, active: boolean) =>
  request<Coupon>('/commerce/coupons/' + id + '?active=' + active, { method: 'PATCH' })

export type PricePreview = {
  base_price_cents: number
  promotion_discount_cents: number
  coupon_discount_cents: number
  total_discount_cents: number
  final_price_cents: number
  currency: string
  promotion_label: string | null
  coupon_code: string | null
  installments_allowed: boolean
  installment_count: number
  deposit_cents: number | null
  deposit_percent: number | null
  balance_cents: number | null
  balance_due_date: string | null
  /** The payments each choice creates, the first one today. */
  schedule_full: PaymentScheduleLine[]
  schedule_installments: PaymentScheduleLine[]
  /** A school account sees the plans but cannot buy. */
  purchase_blocked_reason: string | null
}

export type PaymentScheduleLine = {
  amount_cents: number
  due_date: string
}

export type Checkout = {
  order_id: number
  order_number: string
  status: string
  access_status: string
  formation_id: number
  formation_title: string
  session_id: number
  session_label: string
  base_price_cents: number
  discount_amount_cents: number
  final_price_cents: number
  paid_cents: number
  currency: string
  payment_mode: string
  installment_count: number
  deposit_cents: number | null
  checkout_url: string | null
  provider_reference: string | null
}

export type OrderInstallment = {
  id: number
  order_id: number
  sequence: number
  amount_cents: number
  due_at: string
  grace_until: string
  status: string
  provider_reference: string | null
  checkout_url: string | null
  paid_at: string | null
}

export type SchoolOrder = Checkout & {
  student_name: string
  student_email: string
  student_code: string | null
  coupon_code: string | null
  created_at: string
  paid_at: string | null
  installments: OrderInstallment[]
}

export const previewPublicPrice = (
  schoolKey: string,
  sessionId: number,
  couponCode?: string | null,
) => request<PricePreview>(
  '/commerce/public/' + encodeURIComponent(schoolKey) + '/price-preview',
  {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, coupon_code: couponCode || null }),
    organizationId: null,
  },
)

export const createPublicCheckout = (
  schoolKey: string,
  sessionId: number,
  paymentMode: 'full'|'installments',
  couponCode?: string | null,
  acceptDepositTerms = false,
) => request<Checkout>(
  '/commerce/public/' + encodeURIComponent(schoolKey) + '/checkout',
  {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      payment_mode: paymentMode,
      coupon_code: couponCode || null,
      accept_deposit_terms: acceptDepositTerms,
    }),
    organizationId: null,
  },
)

export const getPublicOrder = (schoolKey: string, orderId: number) =>
  request<SchoolOrder>(
    '/commerce/public/' + encodeURIComponent(schoolKey) + '/orders/' + orderId,
    { organizationId: null },
  )

export const cancelPublicOrder = (schoolKey: string, orderId: number) =>
  request<Checkout>(
    '/commerce/public/' + encodeURIComponent(schoolKey) + '/orders/' + orderId + '/cancel',
    { method: 'POST', organizationId: null },
  )

export const listPublicOrders = (schoolKey: string) =>
  request<SchoolOrder[]>(
    '/commerce/public/' + encodeURIComponent(schoolKey) + '/orders',
    { organizationId: null },
  )

export const confirmPublicDemoCheckout = (schoolKey: string, orderId: number, paymentRef?: string | null) =>
  request<Checkout>(
    '/commerce/public/' + encodeURIComponent(schoolKey) + '/orders/' + orderId + '/demo-confirm' + (paymentRef ? '?payment_ref=' + encodeURIComponent(paymentRef) : ''),
    { method: 'POST', organizationId: null },
  )

export const reconcilePublicTaraCheckout = (schoolKey: string, providerReference: string) =>
  request<Checkout>(
    '/commerce/public/' + encodeURIComponent(schoolKey) + '/tara/reconcile/' + encodeURIComponent(providerReference),
    { method: 'POST', organizationId: null },
  )

export const payPublicInstallment = (schoolKey: string, installmentId: number) =>
  request<{ checkout_url: string | null }>(
    '/commerce/public/' + encodeURIComponent(schoolKey) + '/installments/' + installmentId + '/pay',
    { method: 'POST', organizationId: null },
  )

export type SchoolInvoice = {
  id: number
  order_id: number
  installment_id: number | null
  invoice_number: string
  status: string
  amount_cents: number
  currency: string
  branding_snapshot: Record<string, unknown>
  issued_at: string
  paid_at: string | null
}

export type ManagedStudent = {
  user_id: number
  full_name: string
  email: string
  phone: string | null
  avatar_url: string | null
  student_code: string
  status: string
  active_enrollments: number
  completed_enrollments: number
  totals_by_currency: {
    currency: string
    gross_sales_cents: number
    collected_cents: number
    outstanding_cents: number
  }[]
  last_purchase_at: string | null
}

export type CommercialDashboard = {
  order_count: number
  paid_order_count: number
  totals_by_currency: {
    currency: string
    gross_sales_cents: number
    collected_cents: number
    outstanding_cents: number
  }[]
  late_installments: number
  active_students: number
}

export const getCommercialDashboard = () =>
  request<CommercialDashboard>('/commerce/dashboard')
export type CommunicationNeedsReview = {
  id: number
  channel: string
  recipient: string
  event_key: string
  attempts_count: number
  last_error: string | null
  claimed_at: string | null
}
export const listCommunicationsNeedingReview = () =>
  request<CommunicationNeedsReview[]>('/commerce/communications/needs-review')
export const retryCommunicationAfterReview = (messageId: number) =>
  request<void>(`/commerce/communications/${messageId}/retry`, { method: 'POST' })
export const listSchoolOrders = () => request<SchoolOrder[]>('/commerce/orders')
export const listSchoolInvoices = () => request<SchoolInvoice[]>('/commerce/invoices')
export const downloadSchoolInvoicePdf = (invoiceId: number) =>
  requestBlob('/commerce/invoices/' + invoiceId + '/pdf')
export const listPublicOrderInvoices = (schoolKey: string, orderId: number) =>
  request<SchoolInvoice[]>(
    '/commerce/public/' + encodeURIComponent(schoolKey) + '/orders/' + orderId + '/invoices',
    { organizationId: null },
  )
export const downloadPublicInvoicePdf = (schoolKey: string, invoiceId: number) =>
  requestBlob(
    '/commerce/public/' + encodeURIComponent(schoolKey) + '/invoices/' + invoiceId + '/pdf',
    { organizationId: null },
  )
export const listManagedStudents = () => request<ManagedStudent[]>('/commerce/students')


export const uploadSchoolAsset = (file: File) => {
  const body = new FormData()
  body.append('file', file)
  return request<{
    filename: string
    public_url: string
    size: number
    content_type: string
  }>('/commerce/assets', {
    method: 'POST',
    body,
  })
}

export const uploadFormationVideo = (file: File) => {
  const body = new FormData()
  body.append('file', file)
  return request<{
    filename: string
    public_url: string
    size: number
    content_type: string
    duration_seconds: number
  }>('/commerce/formation-videos', {
    method: 'POST',
    body,
  })
}


export type SchoolPedagogyStudent = {
  enrollment_id: number
  session_id: number
  student_id: number
  student_name: string
  student_code: string | null
  formation_id?: number | null
  formation_title: string
  session_label: string
  enrollment_status: string
  progress_pct: number
  attendance_pct: number | null
  grade_average_pct: number | null
  submitted_assignments: number
  total_assignments: number
  attempted_quizzes: number
  total_quizzes: number
  alert_level: 'good' | 'warning' | 'danger'
  alert_reasons: string[]
}

export type SchoolPedagogySession = {
  session_id: number
  formation_id?: number | null
  formation_title: string
  session_label: string
  teacher_ids?: number[]
  status: string
  enrolled_count: number
  seat_capacity: number
  fill_rate_pct: number
  progress_pct: number
  attendance_rate_pct: number | null
  pending_reviews_count: number
  at_risk_count: number
}

export type SchoolTeacherPerformance = {
  teacher_id: number
  teacher_name: string
  teacher_code: string | null
  sessions_count: number
  students_count: number
  progress_pct: number
  attendance_rate_pct: number | null
  pending_reviews_count: number
}

export type SchoolPedagogyOverview = {
  generated_at: string
  active_students: number
  active_sessions: number
  average_progress_pct: number
  average_attendance_pct: number | null
  at_risk_students: number
  pending_reviews_count: number
  students: SchoolPedagogyStudent[]
  sessions: SchoolPedagogySession[]
  teachers: SchoolTeacherPerformance[]
}

export const getSchoolPedagogyOverview = () =>
  request<SchoolPedagogyOverview>('/academic/manage/overview')

export type SchoolNotification = {
  id: number
  audience: WorkspaceSpace
  title: string
  message: string
  category: string
  tone: 'info' | 'success' | 'warning'
  action_label: string | null
  action_path: string | null
  created_at: string
  read_at: string | null
}

export const listSchoolNotifications = (space: WorkspaceSpace) =>
  request<SchoolNotification[]>(`/notifications?space=${space}`)

export const markSchoolNotificationsRead = (ids: number[]) =>
  request<void>('/notifications/read', { method: 'POST', body: JSON.stringify({ ids }) })

export const dismissSchoolNotifications = (ids: number[]) =>
  request<void>('/notifications/dismiss', { method: 'POST', body: JSON.stringify({ ids }) })


/** The read-only demo offered on the landing page (docs/DEMO.md). */
export type DemoInfo = { enabled: boolean; school_name: string | null; organization_slug: string | null }
export type DemoSpace = 'manage' | 'teacher' | 'student'
export type DemoSession = { access_token: string; organization_id: number; space: DemoSpace; user: AuthUser }

export const getDemoInfo = () => request<DemoInfo>('/auth/demo', { organizationId: null })

export const startDemoSession = (space: DemoSpace) =>
  request<DemoSession>('/auth/demo', { method: 'POST', body: JSON.stringify({ space }), organizationId: null })

/* The student's transcript, for one enrollment (backend app/services/transcripts.py). */
export type TranscriptLine = {
  label: string
  date: string | null
  score: number
  max_score: number
  score_20: number
  note: string
  /** False for the automatic quiz grades, left out of the average. */
  counted: boolean
}

export type TranscriptGroup = {
  key: 'assignments' | 'exams' | 'session_grades' | 'teacher_grades' | 'quizzes'
  label: string
  lines: TranscriptLine[]
}

export type Transcript = {
  enrollment_id: number
  status: 'provisional' | 'final'
  issued_at: string
  school_name: string
  logo_url: string | null
  legal_name: string | null
  legal_address: string | null
  signer_name: string | null
  signer_title: string | null
  white_label: boolean
  student_name: string
  student_code: string | null
  formation_title: string
  format_label: string
  training_hours: number | null
  session_label: string
  session_start: string
  session_end: string
  groups: TranscriptGroup[]
  average_20: number | null
  mention: string | null
  counted_sessions: number
  attended_sessions: number
  attendance_pct: number | null
  badge_label: string | null
}

export type TranscriptSummary = {
  enrollment_id: number
  formation_title: string
  session_label: string
  status: 'provisional' | 'final'
  average_20: number | null
}

export const listMyTranscripts = () => request<TranscriptSummary[]>('/transcripts/mine')

export const getTranscript = (enrollmentId: number) => request<Transcript>('/transcripts/' + enrollmentId)

export const downloadTranscriptPdf = (enrollmentId: number) => requestBlob('/transcripts/' + enrollmentId + '/pdf')
