import { ApiError, getAccessToken, getStoredOrganizationId } from '../lib/api'
import { getCurrentSchoolBranding } from '../brand/schoolBrandingApi'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export type CharterAudience = 'teacher' | 'student'
export type TeacherDocumentKind = 'portfolio' | 'cv'

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
  whatsapp_phone: string | null
  whatsapp_country: string | null
  whatsapp_phone_legacy: boolean
  whatsapp_phone_verified_at: string | null
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
  city: string
  country: string
  languages: string[]
  whatsapp_phone: string
  whatsapp_country: string
}

export type PhoneCountryOption = {
  code: string
  dial_code: string
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

async function withCurrentSchoolName(profile: TeacherProfessionalProfile) {
  try {
    const branding = await getCurrentSchoolBranding(profile.organization_id)
    if (branding.organization_id !== profile.organization_id) return profile
    return { ...profile, organization_name: branding.school_name || profile.organization_name }
  } catch {
    return profile
  }
}

export async function getTeacherProfessionalProfile() {
  return withCurrentSchoolName(await request<TeacherProfessionalProfile>('/workspace-onboarding/teacher-profile'))
}

export async function getTeacherProfessionalProfileForAdmin(userId: number) {
  return withCurrentSchoolName(await request<TeacherProfessionalProfile>(`/workspace-onboarding/teacher-profiles/${userId}`))
}

export function getPhoneCountries() {
  return request<PhoneCountryOption[]>('/workspace-onboarding/phone-countries')
}

export async function saveTeacherProfessionalProfile(payload: TeacherProfessionalProfilePayload) {
  return withCurrentSchoolName(await request<TeacherProfessionalProfile>('/workspace-onboarding/teacher-profile', {
    method: 'PUT',
    body: JSON.stringify(payload),
  }))
}

export async function uploadTeacherProfessionalDocument(kind: TeacherDocumentKind, file: File) {
  const form = new FormData()
  form.set('file', file)
  const response = await fetch(`${API_BASE}/workspace-onboarding/teacher-profile/documents/${kind}`, {
    method: 'POST',
    credentials: 'include',
    headers: headers(false),
    body: form,
  })
  if (!response.ok) throw await readError(response)
  const profile = await response.json() as TeacherProfessionalProfile
  return withCurrentSchoolName(profile)
}

export async function previewTeacherProfessionalDocument(userId: number, kind: TeacherDocumentKind) {
  const previewWindow = window.open('about:blank', '_blank')
  try {
    const response = await fetch(`${API_BASE}/workspace-onboarding/teacher-profiles/${userId}/documents/${kind}`, {
      credentials: 'include',
      headers: headers(false),
    })
    if (!response.ok) throw await readError(response)
    const blob = await response.blob()
    const objectUrl = URL.createObjectURL(blob)
    if (previewWindow) {
      previewWindow.location.href = objectUrl
    } else {
      const anchor = document.createElement('a')
      anchor.href = objectUrl
      anchor.target = '_blank'
      anchor.rel = 'noopener noreferrer'
      anchor.click()
    }
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 120_000)
  } catch (error) {
    previewWindow?.close()
    throw error
  }
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
