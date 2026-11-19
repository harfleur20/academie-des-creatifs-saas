const ORGANIZATION_SELECTION_KEY = 'academie_saas_organization_selection_required'

export const ORGANIZATION_SELECTION_REQUESTED_EVENT = 'academie-saas:organization-selection-requested'

export function requestOrganizationSelection() {
  try {
    window.sessionStorage.setItem(ORGANIZATION_SELECTION_KEY, '1')
    window.dispatchEvent(new Event(ORGANIZATION_SELECTION_REQUESTED_EVENT))
  } catch {
    // The tenant context also checks the flag when it loads the organization list.
  }
}

export function isOrganizationSelectionRequested() {
  try {
    return window.sessionStorage.getItem(ORGANIZATION_SELECTION_KEY) === '1'
  } catch {
    return false
  }
}

export function clearOrganizationSelectionRequest() {
  try {
    window.sessionStorage.removeItem(ORGANIZATION_SELECTION_KEY)
  } catch {
    // Storage may be unavailable in restricted browser contexts.
  }
}
