const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const TOKEN_KEY = 'academie_saas_access_token'
const ORGANIZATION_KEY = 'academie_saas_organization_id'

export class TenantIntegrationApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function tenantRequest<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = 30000,
): Promise<T> {
  const headers = new Headers(options.headers)
  if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')

  const token = sessionStorage.getItem(TOKEN_KEY)
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const organizationId = sessionStorage.getItem(ORGANIZATION_KEY)
  if (organizationId) headers.set('X-Organization-Id', organizationId)

  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      credentials: 'include',
      signal: controller.signal,
    })
    if (!response.ok) {
      let message = `La requête a échoué (HTTP ${response.status}).`
      try {
        const body = await response.json()
        if (typeof body?.detail === 'string') message = body.detail
      } catch {
        // Keep generic message.
      }
      throw new TenantIntegrationApiError(response.status, message)
    }
    if (response.status === 204) return undefined as T
    return response.json() as Promise<T>
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new TenantIntegrationApiError(408, 'La requête a pris trop de temps. Réessayez.')
    }
    throw error
  } finally {
    window.clearTimeout(timer)
  }
}

export type OpenAIIntegrationStatus = {
  provider: 'openai'
  connected: boolean
  status: string
  model: string | null
  connected_at: string | null
  last_tested_at: string | null
  last_error: string | null
}

export type AiGenerationBasePayload = {
  session_id: number
  topic: string
  level?: string | null
  objectives?: string | null
}

export type AiCourseDraftPayload = AiGenerationBasePayload & {
  chapters_count?: number
  lessons_per_chapter?: number
}

export type AiCourseDraft = {
  title: string
  description: string
  chapters: Array<{
    title: string
    lessons: Array<{ title: string; content: string }>
  }>
}

export type AiQuizDraftPayload = AiGenerationBasePayload & {
  course_day_id?: number | null
  questions_count?: number
  options_per_question?: number
}

export type AiQuizDraft = {
  title: string
  duration_minutes: number | null
  questions: Array<{
    text: string
    options: string[]
    correct_index: number
  }>
}

export type AiAssignmentDraftPayload = AiGenerationBasePayload & {
  course_day_id?: number | null
  duration_days?: number
  is_final_project?: boolean
  assignment_type?: string | null
}

export type AiAssignmentBrief = {
  context: string
  objective: string
  deliverables: string[]
  steps: string[]
  evaluation_criteria: Array<{
    label: string
    points: number
    description: string
  }>
  submission_method: string
  tips: string[]
}

export type AiAssignmentDraft = {
  title: string
  brief: AiAssignmentBrief
  instructions: string
  is_final_project: boolean
  duration_days: number
}

export const getOpenAIIntegration = () =>
  tenantRequest<OpenAIIntegrationStatus>('/integrations/openai')

export const connectOpenAI = (apiKey: string, model: string) =>
  tenantRequest<OpenAIIntegrationStatus>('/integrations/openai', {
    method: 'PUT',
    body: JSON.stringify({ api_key: apiKey, model }),
  }, 45000)

export const testOpenAIIntegration = () =>
  tenantRequest<OpenAIIntegrationStatus>('/integrations/openai/test', { method: 'POST' }, 45000)

export const disconnectOpenAI = () =>
  tenantRequest<void>('/integrations/openai', { method: 'DELETE' })

export const getTeacherAIStatus = () =>
  tenantRequest<OpenAIIntegrationStatus>('/teacher/ai/status')

export const generateTeacherCourseDraft = (payload: AiCourseDraftPayload) =>
  tenantRequest<AiCourseDraft>('/teacher/ai/course-draft', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, 180000)

export const generateTeacherQuizDraft = (payload: AiQuizDraftPayload) =>
  tenantRequest<AiQuizDraft>('/teacher/ai/quiz-draft', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, 180000)

export const generateTeacherAssignmentDraft = (payload: AiAssignmentDraftPayload) =>
  tenantRequest<AiAssignmentDraft>('/teacher/ai/assignment-draft', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, 180000)
