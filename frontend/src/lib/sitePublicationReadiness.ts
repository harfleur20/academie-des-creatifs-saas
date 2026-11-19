import type { SchoolIdentity } from './api'

export type PublicationDestination = 'school' | 'domains' | 'legal'

export type SchoolPublicationRequirement = {
  id: string
  label: string
  destination: PublicationDestination
  complete: boolean
}

type PublicationOrganization = {
  contact_email?: string | null
  subdomain?: string | null
} | null

/** Mirrors the server-side site publication requirements and points to their settings tab. */
export function getSchoolPublicationRequirements(
  identity: SchoolIdentity | null,
  organization: PublicationOrganization,
): SchoolPublicationRequirement[] {
  if (!identity || !organization) return []

  const { public_site: site, legal } = identity
  return [
    {
      id: 'contact-email',
      label: 'Email de contact de l’école',
      destination: 'school',
      complete: Boolean(organization.contact_email?.trim()),
    },
    {
      id: 'subdomain',
      label: 'Sous-domaine de l’école',
      destination: 'domains',
      complete: Boolean(organization.subdomain?.trim()),
    },
    {
      id: 'student-code-prefix',
      label: 'Préfixe des matricules confirmé',
      destination: 'school',
      complete: Boolean(site.student_code_prefix.trim() && site.student_code_prefix_confirmed),
    },
    {
      id: 'legal-notice',
      label: 'Mentions légales',
      destination: 'legal',
      complete: Boolean(site.legal_notice.trim()),
    },
    {
      id: 'sales-terms',
      label: 'Conditions générales de vente',
      destination: 'legal',
      complete: Boolean(site.sales_terms.trim()),
    },
    {
      id: 'privacy-policy',
      label: 'Politique de confidentialité',
      destination: 'legal',
      complete: Boolean(site.privacy_policy.trim()),
    },
    {
      id: 'refund-policy',
      label: 'Politique de remboursement',
      destination: 'legal',
      complete: Boolean(site.refund_policy.trim()),
    },
    {
      id: 'billing-name',
      label: 'Raison sociale des factures',
      destination: 'legal',
      complete: Boolean(legal.legal_name.trim()),
    },
    {
      id: 'billing-address',
      label: 'Adresse légale des factures',
      destination: 'legal',
      complete: Boolean(legal.legal_address.trim()),
    },
    {
      id: 'billing-email',
      label: 'Email de facturation',
      destination: 'legal',
      complete: Boolean(legal.invoice_email?.trim()),
    },
    {
      id: 'billing-currency',
      label: 'Devise de facturation',
      destination: 'legal',
      complete: /^[a-z]{3}$/i.test(legal.default_currency.trim()),
    },
  ]
}
