import { ApiError, getAccessToken, getStoredOrganizationId } from './api'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

async function deleteDiscussionResource(path: string) {
  const headers = new Headers()
  const token = getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const organizationId = getStoredOrganizationId()
  if (organizationId !== null) {
    headers.set('X-Organization-Id', String(organizationId))
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers,
  })

  if (!response.ok) {
    let message = `La suppression a échoué (HTTP ${response.status}).`
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') message = body.detail
    } catch {
      // Keep the generic message when the backend does not return JSON.
    }
    throw new ApiError(response.status, message)
  }
}

export const deleteClassDiscussionPost = (sessionId: number, postId: number) =>
  deleteDiscussionResource(`/academic/classes/${sessionId}/discussion/${postId}`)

export const deleteClassDiscussionReply = (
  sessionId: number,
  postId: number,
  replyId: number,
) =>
  deleteDiscussionResource(
    `/academic/classes/${sessionId}/discussion/${postId}/replies/${replyId}`,
  )
