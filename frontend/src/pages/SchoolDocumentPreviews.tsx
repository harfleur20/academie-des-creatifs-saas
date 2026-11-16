import { activeSchoolLocale } from '../app/schoolLocale'
import type { CSSProperties, ReactNode } from 'react'
import { ChevronDown, Eye } from 'lucide-react'
import { SchoolLogo } from '../brand/SchoolLogo'
import type { SchoolIdentity } from '../lib/api'
import { formatSchoolMoney } from '../public/publicHelpers'

type PreviewProps = { identity: SchoolIdentity; contactEmail?: string | null; logoUrl?: string | null }

function previewStyle(identity: SchoolIdentity): CSSProperties {
  return {
    '--document-primary': identity.public_site.primary_color || '#1F2559',
    '--document-secondary': identity.public_site.secondary_color || '#18A7A3',
    '--document-accent': identity.public_site.accent_color || '#131735',
  } as CSSProperties
}

function PreviewToggle({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <details className="school-document-preview">
      <summary>
        <span className="school-document-preview__heading"><Eye size={18}/><span><strong>{title}</strong><small>{description}</small></span></span>
        <span className="school-document-preview__toggle">Afficher l’aperçu <ChevronDown size={16}/></span>
      </summary>
      <div className="school-document-preview__body">{children}</div>
    </details>
  )
}

function SchoolLogoPreview({ identity, className = '', logoUrl }: { identity: SchoolIdentity; className?: string; logoUrl?: string | null }) {
  const resolvedLogoUrl = identity.public_site.logo_url || logoUrl
  return <SchoolLogo logoUrl={resolvedLogoUrl} className={className} alt={`Logo de ${identity.public_site.site_name || identity.organization_name || 'votre école'}`}/>
}

export function SchoolInvoicePreview({ identity, contactEmail, logoUrl }: PreviewProps) {
  const { public_site: site, legal } = identity
  const schoolName = site.site_name || identity.organization_name || 'Votre école'
  const issuedAt = new Intl.DateTimeFormat(activeSchoolLocale()).format(new Date())

  return (
    <PreviewToggle title="Aperçu de la facture" description="Valeurs d’exemple · reflète votre identité visuelle et vos informations de facturation">
      <article className="school-invoice-preview" style={previewStyle(identity)}>
        <header className="school-invoice-preview__header">
          <SchoolLogoPreview identity={identity} className="school-invoice-preview__logo" logoUrl={logoUrl}/>
          <div><strong>{schoolName}</strong>{(site.contact_email || contactEmail) && <span>{site.contact_email || contactEmail}</span>}{site.contact_phone && <span>{site.contact_phone}</span>}</div>
        </header>
        <div className="school-invoice-preview__content">
          <div className="school-invoice-preview__title"><h3>FACTURE / REÇU</h3><strong>FAC-2026-0042</strong></div>
          <div className="school-invoice-preview__meta"><span>Émise le {issuedAt}</span><span>Commande CMD-2026-0042</span></div>
          <section className="school-invoice-preview__parties">
            <div><strong>ÉTUDIANT</strong><span>Camille Ndom</span><span>camille.ndom@exemple.com</span><span>Matricule : ND-2026-042</span></div>
            <div><strong>FORMATION</strong><span>Design graphique : les fondamentaux</span><span>Session : Cohorte octobre 2026</span><span>07/10/2026 – 10/03/2027</span></div>
          </section>
          <div className="school-invoice-preview__table-head"><span>LIBELLÉ</span><span>MONTANT</span></div>
          <div className="school-invoice-preview__line"><strong>Design graphique : les fondamentaux</strong><strong>{formatSchoolMoney(65000, 'XAF')}</strong></div>
          <div className="school-invoice-preview__total"><strong>PAYÉ</strong><strong>{formatSchoolMoney(65000, 'XAF')}</strong></div>
          <div className="school-invoice-preview__legal">
            <strong>{legal.legal_name || schoolName}</strong>
            {legal.legal_address && <span>{legal.legal_address}</span>}
            {legal.registration_number && <span>Immatriculation : {legal.registration_number}</span>}
            {legal.tax_number && <span>Identifiant fiscal : {legal.tax_number}</span>}
            {legal.invoice_footer && <p>{legal.invoice_footer}</p>}
          </div>
        </div>
        <footer className="school-invoice-preview__footer">Document émis par {schoolName} · Powered by Académie des Créatifs</footer>
        <span className="school-document-preview__sample">APERÇU · DONNÉES FICTIVES</span>
      </article>
    </PreviewToggle>
  )
}

function SampleQr() {
  const cells = [
    '1111111001011111111', '1000001011011000001', '1011101001011011101', '1011101011011011101',
    '1011101000011011101', '1000001011111000001', '1111111010101111111', '0000000011010000000',
    '1101011110010110101', '0110100011111001010', '1011111010010111101', '0000000011101010000',
    '1111111010011010111', '1000001001100011001', '1011101010111110101', '1011101001010010110',
    '1011101011101111001', '1000001010010010101', '1111111011101011101',
  ]
  return <span className="school-certificate-preview__qr" aria-label="Exemple de QR code de vérification">{cells.join('').split('').map((cell, index) => <i key={index} className={cell === '1' ? 'is-dark' : ''}/>)}</span>
}

export function SchoolCertificatePreview({ identity, logoUrl }: PreviewProps) {
  const { public_site: site, certification } = identity
  const schoolName = site.site_name || identity.organization_name || 'Votre école'
  const issuedAt = new Intl.DateTimeFormat(activeSchoolLocale()).format(new Date())

  return (
    <PreviewToggle title="Aperçu du certificat" description="Valeurs d’exemple · reflète votre logo, vos couleurs, votre signature et votre cachet">
      <article className="school-certificate-preview" style={previewStyle(identity)}>
        <div className="school-certificate-preview__inner">
          <svg className="school-certificate-preview__ornament" viewBox="0 0 1200 820" preserveAspectRatio="none" aria-hidden="true">
            <g fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M-20 115 C100 16 198 232 350 154 S456 90 505 117"/>
              <path d="M-20 139 C112 40 205 255 362 177 S466 112 517 139"/>
              <path d="M-20 163 C124 64 214 278 374 201 S478 136 529 163"/>
              <path d="M1220 115 C1100 16 1002 232 850 154 S744 90 695 117"/>
              <path d="M1220 139 C1088 40 995 255 838 177 S734 112 683 139"/>
              <path d="M1220 163 C1076 64 986 278 826 201 S722 136 671 163"/>
              <path d="M-20 705 C100 804 198 588 350 666 S456 730 505 703"/>
              <path d="M-20 681 C112 780 205 565 362 643 S466 708 517 681"/>
              <path d="M-20 657 C124 756 214 542 374 619 S478 684 529 657"/>
              <path d="M1220 705 C1100 804 1002 588 850 666 S744 730 695 703"/>
              <path d="M1220 681 C1088 780 995 565 838 643 S734 708 683 681"/>
              <path d="M1220 657 C1076 756 986 542 826 619 S722 684 671 657"/>
            </g>
          </svg>
          <header><SchoolLogoPreview identity={identity} className="school-certificate-preview__logo" logoUrl={logoUrl}/><strong>{schoolName}</strong></header>
          <span className="school-certificate-preview__eyebrow">ATTESTATION DE RÉUSSITE</span>
          <h3>CERTIFICAT DE FIN DE FORMATION</h3>
          <span className="school-certificate-preview__divider" aria-hidden="true"><i/></span>
          <p>Nous certifions que</p>
          <strong className="school-certificate-preview__student">CAMILLE NDOM</strong>
          <p>a suivi et validé avec succès la formation</p>
          <strong className="school-certificate-preview__formation">Design graphique : les fondamentaux</strong>
          <span className="school-certificate-preview__session">Cohorte octobre 2026 · 07/10/2026 – 10/03/2027</span>
          <div className="school-certificate-preview__bottom">
            <div className="school-certificate-preview__details">
              <strong>N° certificat : CERT-2026-0042</strong>
              <span>Matricule : ND-2026-042</span>
              <span>Volume de formation : 120 h</span>
              <span>Émis le {issuedAt}</span>
              {certification.certificate_footer && <span className="school-certificate-preview__footer-note">{certification.certificate_footer}</span>}
            </div>
            <div className="school-certificate-preview__verification"><SampleQr/><span>Scanner pour vérifier l’authenticité</span></div>
            <div className="school-certificate-preview__signatures">
              <div className="school-certificate-preview__signature-art">
                {certification.stamp_url && <img className="school-certificate-preview__stamp" src={certification.stamp_url} alt="Cachet de l’école"/>}
                {certification.signature_url && <img className="school-certificate-preview__signature-image" src={certification.signature_url} alt="Signature"/>}
              </div>
              <strong>{certification.signer_name || 'Nom du signataire'}</strong>
              <span>{certification.signer_title || 'Fonction'}</span>
            </div>
          </div>
          <small className="school-certificate-preview__powered">Powered by Académie des Créatifs</small>
        </div>
        <span className="school-document-preview__sample">APERÇU · DONNÉES FICTIVES</span>
      </article>
    </PreviewToggle>
  )
}
