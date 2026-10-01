export type AuthUser = {
  id: number
  full_name: string
  email: string
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
  role: 'admin' | 'manager' | 'teacher' | 'student'
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
  entitlements: PlanEntitlement[]
}

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
  plan: Plan
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const TOKEN_KEY = 'academie_saas_access_token'
const ORGANIZATION_KEY = 'academie_saas_organization_id'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setAccessToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(ORGANIZATION_KEY)
}

export function getStoredOrganizationId(): number | null {
  const raw = localStorage.getItem(ORGANIZATION_KEY)
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isInteger(parsed) ? parsed : null
}

export function setStoredOrganizationId(id: number | null) {
  if (id === null) {
    localStorage.removeItem(ORGANIZATION_KEY)
    return
  }
  localStorage.setItem(ORGANIZATION_KEY, String(id))
}

async function request<T>(
  path: string,
  options: RequestInit & { organizationId?: number | null } = {},
): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')

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
    let message = 'Une erreur est survenue.'
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') message = body.detail
    } catch {
      // Keep generic message.
    }
    throw new ApiError(response.status, message)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
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

export const listOrganizations = () =>
  request<Organization[]>('/organizations', { organizationId: null })

export const createOrganization = (payload: { name: string; slug: string }) =>
  request<Organization>('/organizations', {
    method: 'POST',
    body: JSON.stringify(payload),
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

export const listMembers = () =>
  request<Member[]>('/organizations/current/members')

export const updateMember = (
  memberId: number,
  payload: { role?: Member['role']; status?: Member['status'] },
) =>
  request<Member>(`/organizations/current/members/${memberId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })

export const listInvitations = () =>
  request<Invitation[]>('/organizations/current/invitations')

export const createInvitation = (payload: {
  email: string
  role: Invitation['role']
}) =>
  request<Invitation>('/organizations/current/invitations', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

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

export type AdminOrganizationDetail = AdminOrganization & {
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
