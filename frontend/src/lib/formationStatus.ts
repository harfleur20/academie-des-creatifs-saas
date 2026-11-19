import type { FormationSummary } from './api'

/**
 * Published and complete, but no session open to enrollment: the formation stays on the
 * school's site, nobody can buy it until a session opens.
 */
export function publishedWithoutSale(formation: Pick<FormationSummary, 'status' | 'publication_issues' | 'content_issues'>) {
  return formation.status === 'published'
    && (formation.content_issues ?? []).length === 0
    && formation.publication_issues.length > 0
}
