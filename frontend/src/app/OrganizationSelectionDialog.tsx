import { ArrowRight, Building2 } from 'lucide-react'
import { createPortal } from 'react-dom'
import { SchoolLogo } from '../brand/SchoolLogo'
import type { Organization } from '../lib/api'

export function OrganizationSelectionDialog({
  organizations,
  onSelect,
}: {
  organizations: Organization[]
  onSelect: (organizationId: number) => void
}) {
  return createPortal(
    <div className="organization-selection-overlay">
      <section
        className="organization-selection-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="organization-selection-title"
        aria-describedby="organization-selection-description"
      >
        <span className="section-label">VOTRE ESPACE</span>
        <h1 id="organization-selection-title">Dans quelle école souhaitez-vous entrer ?</h1>
        <p id="organization-selection-description">
          Votre compte est associé à plusieurs écoles. Choisissez celle dont vous souhaitez ouvrir l’espace.
        </p>
        <div className="organization-selection-list">
          {organizations.map((organization) => (
            <button
              key={organization.id}
              type="button"
              className="organization-selection-option"
              onClick={() => onSelect(organization.id)}
            >
              <SchoolLogo logoUrl={organization.logo_url} alt="" className="organization-selection-logo" />
              <span className="organization-selection-copy">
                <strong>{organization.name}</strong>
                <small>{organization.public_site_url || 'Espace école'}</small>
              </span>
              <ArrowRight size={20} aria-hidden="true" />
            </button>
          ))}
        </div>
        <div className="organization-selection-note">
          <Building2 size={17} aria-hidden="true" />
          Vous pourrez changer d’école à tout moment depuis le menu de votre espace.
        </div>
      </section>
    </div>,
    document.body,
  )
}
