import { ApiError, getAccessToken, getStoredOrganizationId } from '../lib/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export type CharterAudience = 'teacher' | 'student'

export type TeacherProfessionalProfile = {
  organization_id: number
  organization_name: string
  user_id: number
  full_name: string
  email: string
  phone: string | null
  avatar_url: string | null
  teacher_code: string | null
  professional_title: string
  experience_years: number
  activity_domains: string[]
  bio: string
  skills: string[]
  portfolio_url: string | null
  portfolio_file_name: string | null
  cv_file_name: string | null
  linkedin_url: string | null
  behance_url: string | null
  github_url: string | null
  website_url: string | null
  city: string | null
  country: string | null
  languages: string[]
  profile_completed_at: string | null
  is_complete: boolean
}

export type TeacherProfessionalProfilePayload = {
  professional_title: string
  experience_years: number
  activity_domains: string[]
  bio: string
  skills: string[]
  portfolio_url?: string | null
  linkedin_url?: string | null
  behance_url?: string | null
  github_url?: string | null
  website_url?: string | null
  city?: string | null
  country?: string | null
  languages: string[]
}

export type SchoolCharter = {
  id: number
  organization_id: number
  audience: CharterAudience
  title: string
  content: string
  is_enabled: boolean
  version: number
  accepted_current_version: boolean
  accepted_at: string | null
}

export type SchoolCharterPayload = {
  title: string
  content: string
  is_enabled: boolean
}

function headers(contentType = true) {
  const result = new Headers()
  if (contentType) result.set('Content-Type', 'application/json')
  const token = getAccessToken()
  const organizationId = getStoredOrganizationId()
  if (token) result.set('Authorization', `Bearer ${token}`)
  if (organizationId !== null) result.set('X-Organization-Id', String(organizationId))
  return result
}

async function readError(response: Response) {
  let message = `La demande a échoué (HTTP ${response.status}).`
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string') message = body.detail
  } catch {
    // Keep the generic message.
  }
  return new ApiError(response.status, message)
}

async function request<T>(path: string, init: RequestInit = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    ...init,
    headers: init.headers || headers(),
  })
  if (!response.ok) throw await readError(response)
  return response.json() as Promise<T>
}

export function getTeacherProfessionalProfile() {
  return request<TeacherProfessionalProfile>('/workspace-onboarding/teacher-profile')
}

export function saveTeacherProfessionalProfile(payload: TeacherProfessionalProfilePayload) {
  return request<TeacherProfessionalProfile>('/workspace-onboarding/teacher-profile', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function uploadTeacherProfessionalDocument(kind: 'portfolio' | 'cv', file: File) {
  const form = new FormData()
  form.set('file', file)
  const response = await fetch(`${API_BASE}/workspace-onboarding/teacher-profile/documents/${kind}`, {
    method: 'POST',
    credentials: 'include',
    headers: headers(false),
    body: form,
  })
  if (!response.ok) throw await readError(response)
  return response.json() as Promise<TeacherProfessionalProfile>
}

export function getSchoolCharter(audience: CharterAudience) {
  return request<SchoolCharter>(`/workspace-onboarding/charters/${audience}`)
}

export function saveSchoolCharter(audience: CharterAudience, payload: SchoolCharterPayload) {
  return request<SchoolCharter>(`/workspace-onboarding/charters/${audience}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function acceptSchoolCharter(audience: CharterAudience) {
  return request<SchoolCharter>(`/workspace-onboarding/charters/${audience}/accept`, {
    method: 'POST',
  })
}
