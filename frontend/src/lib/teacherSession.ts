export function initialTeacherSessionId(sessions: Array<{ session_id: number }>): number | null {
  const requested = Number(new URLSearchParams(window.location.search).get('session'))
  return sessions.find((item) => item.session_id === requested)?.session_id ?? sessions[0]?.session_id ?? null
}
